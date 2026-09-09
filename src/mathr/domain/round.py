"""One run of a level, as a pure reducer.

Knows about `parts: int` and a bank of seconds; it does not know that the parts
are a rocket or that the clock is an alien. A game mode consumes the stream of
outcomes and renders progress however it likes.
"""

import random
from dataclasses import dataclass, replace
from enum import Enum
from typing import Mapping

from .facts import Fact, Level

PARTS_TO_LAUNCH = 10
RETRY_GAP = 3  # far enough that he must retrieve the fact, not echo it

GRACE_PARTS = 5  # the round opens with this many problems' worth of time
BANK_PARTS = 4  # and can never bank more than this many afterwards


class Outcome(Enum):
    CORRECT = "correct"
    WRONG = "wrong"
    LAUNCHED = "launched"
    ABDUCTED = "abducted"


@dataclass(frozen=True)
class Tally:
    """What is known about one fact. Written to disk, so it outlives the code."""

    right: int = 0
    wrong: int = 0
    answered: int = 0
    seconds: float = 0.0

    def record(self, correct: bool, seconds: float) -> "Tally":
        return Tally(
            right=self.right + correct,
            wrong=self.wrong + (not correct),
            answered=self.answered + 1,
            seconds=self.seconds + seconds,
        )


@dataclass(frozen=True)
class Round:
    level_id: str
    seconds_per_part: float
    deck: tuple[Fact, ...]  # the shuffled pool, replayed when the queue runs low
    queue: tuple[Fact, ...]  # upcoming; queue[0] is on screen
    parts: int
    asked: int
    missed: int
    attempts: Mapping[str, Tally]  # fact.key -> Tally
    launched: bool
    failed: bool
    seconds_left: float | None  # None is an untimed round
    on_current: float  # spent on the question showing now
    elapsed: float  # wall time in the round, for the best-time record

    @property
    def current(self) -> Fact:
        return self.queue[0]

    @property
    def over(self) -> bool:
        return self.launched or self.failed

    @property
    def cap(self) -> float:
        return self.seconds_per_part * BANK_PARTS

    @property
    def timed(self) -> bool:
        return self.seconds_left is not None


def new_round(level: Level, rng: random.Random, timed: bool = True) -> Round:
    deck = tuple(rng.sample(level.facts, len(level.facts)))
    return Round(
        level_id=level.id,
        seconds_per_part=level.seconds_per_part,
        deck=deck,
        queue=deck,
        parts=0,
        asked=0,
        missed=0,
        attempts={},
        launched=False,
        failed=False,
        seconds_left=level.seconds_per_part * GRACE_PARTS if timed else None,
        on_current=0.0,
        elapsed=0.0,
    )


def tick(round: Round, dt: float) -> tuple[Round, Outcome | None]:
    """Advance the clock. Returns ABDUCTED on the frame the bank empties.

    Time on the current question accumulates even in an untimed round: the
    per-fact response times are worth having either way, and practice is
    where the slowest facts actually surface.
    """
    if round.over:
        return round, None

    running = replace(
        round,
        elapsed=round.elapsed + dt,
        on_current=round.on_current + dt,
    )
    if round.seconds_left is None:
        return running, None

    left = round.seconds_left - dt
    if left <= 0:
        return replace(running, seconds_left=0.0, failed=True), Outcome.ABDUCTED
    return replace(running, seconds_left=left), None


def _credit(round: Round) -> float | None:
    """Pay for a part, without ever pushing the bank down.

    The round opens above the cap, so during that grace period a correct
    answer is simply worth nothing rather than a penalty.
    """
    if round.seconds_left is None:
        return None
    return max(round.seconds_left, min(round.seconds_left + round.seconds_per_part, round.cap))


def apply(round: Round, given: int) -> tuple[Round, Outcome]:
    if round.over:
        return round, Outcome.LAUNCHED if round.launched else Outcome.ABDUCTED

    fact = round.current
    correct = given == fact.answer
    rest = round.queue[1:]
    if not correct:
        # Slicing past the end appends, so a fact missed near the end of the
        # deck is still re-asked rather than quietly dropped.
        rest = rest[:RETRY_GAP] + (fact,) + rest[RETRY_GAP:]
    if len(rest) <= RETRY_GAP:
        rest = rest + round.deck

    parts = min(round.parts + 1, PARTS_TO_LAUNCH) if correct else max(round.parts - 1, 0)
    launched = parts >= PARTS_TO_LAUNCH
    tallied = round.attempts.get(fact.key, Tally()).record(correct, round.on_current)
    updated = replace(
        round,
        queue=rest,
        parts=parts,
        asked=round.asked + 1,
        missed=round.missed + (not correct),
        attempts={**round.attempts, fact.key: tallied},
        launched=launched,
        seconds_left=_credit(round) if correct else round.seconds_left,
        on_current=0.0,
    )
    if launched:
        return updated, Outcome.LAUNCHED
    return updated, Outcome.CORRECT if correct else Outcome.WRONG
