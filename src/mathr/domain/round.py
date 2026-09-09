"""One run of a level, as a pure reducer.

Knows about `parts: int`, a bank of seconds, and a `Rules` bundle that says how
both behave; it does not know that the parts are a rocket or that the clock is
an alien. A game mode picks a rule set, consumes the stream of outcomes, and
renders progress however it likes.
"""

import random
from dataclasses import dataclass, replace
from enum import Enum
from typing import Mapping

from .facts import Level, Question, shuffled

PARTS_TO_LAUNCH = 10
RETRY_GAP = 3  # far enough that he must retrieve the fact, not echo it

GRACE_PARTS = 5  # the rocket round opens with this many problems' worth of time
BANK_PARTS = 4  # and can never bank more than this many afterwards

BALL_FLIGHT = 1.5  # how many problems' worth of time a served ball takes to land


class Outcome(Enum):
    CORRECT = "correct"
    WRONG = "wrong"
    POINT = "point"  # the clock ran out but the round goes on
    WON = "won"
    LOST = "lost"


@dataclass(frozen=True)
class Rules:
    """What a mode changes about the round. Modes differ in rules, not only art.

    The rocket's clock is a shared bank; tennis's is a deadline per rally. Five
    dials cover the difference, and every one of them would otherwise be a
    silent wrong answer: a mode built as a pure renderer over the rocket's rules
    compiles, draws, and plays as a different game.
    """

    opening_parts: float  # bank at the start, in problems
    bank_parts: float  # ceiling on the bank, in problems
    credit_parts: float  # what a correct answer pays back, in problems
    wrong_costs_part: bool  # does a wrong answer take a part back
    wrong_advances: bool  # does a wrong answer move on to the next question
    lives: int | None  # empty-clock events survivable; None ends the round
    target: int  # parts needed to win


#: A correct answer buys one problem's worth, up to a four-problem ceiling.
ROCKET = Rules(GRACE_PARTS, BANK_PARTS, 1.0, True, True, None, PARTS_TO_LAUNCH)

#: `credit_parts == bank_parts` is the rally reset: the bank is never above the
#: cap here, so crediting a full bank's worth always refills it exactly.
TENNIS = Rules(BALL_FLIGHT, BALL_FLIGHT, BALL_FLIGHT, False, False, 3, 10)


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
    rules: Rules
    seconds_per_part: float
    deck: tuple[Question, ...]  # the shuffled pool, replayed when the queue runs low
    queue: tuple[Question, ...]  # upcoming; queue[0] is on screen
    parts: int
    points: int  # empty-clock events survived
    asked: int
    missed: int
    attempts: Mapping[str, Tally]  # fact.key -> Tally
    launched: bool
    failed: bool
    seconds_left: float | None  # None is an untimed round
    on_current: float  # spent on the question showing now
    elapsed: float  # wall time in the round, for the best-time record

    @property
    def current(self) -> Question:
        return self.queue[0]

    @property
    def over(self) -> bool:
        return self.launched or self.failed

    @property
    def cap(self) -> float:
        return self.seconds_per_part * self.rules.bank_parts

    @property
    def timed(self) -> bool:
        return self.seconds_left is not None


def new_round(
    level: Level, rng: random.Random, timed: bool = True, rules: Rules = ROCKET
) -> Round:
    if not timed and rules.lives is not None:
        # A rally has nowhere to put the ball without a deadline to fly along.
        raise ValueError("a round with lives cannot be untimed")
    deck = shuffled(level.facts, rng)
    return Round(
        level_id=level.id,
        rules=rules,
        seconds_per_part=level.seconds_per_part,
        deck=deck,
        queue=deck,
        parts=0,
        points=0,
        asked=0,
        missed=0,
        attempts={},
        launched=False,
        failed=False,
        seconds_left=level.seconds_per_part * rules.opening_parts if timed else None,
        on_current=0.0,
        elapsed=0.0,
    )


def _advance(round: Round, retry: Question | None = None) -> tuple[Question, ...]:
    rest = round.queue[1:]
    if retry is not None:
        # Slicing past the end appends, so a fact missed near the end of the
        # deck is still re-asked rather than quietly dropped.
        rest = rest[:RETRY_GAP] + (retry,) + rest[RETRY_GAP:]
    if len(rest) <= RETRY_GAP:
        rest = rest + round.deck
    return rest


def tick(round: Round, dt: float) -> tuple[Round, Outcome | None]:
    """Advance the clock. Returns LOST or POINT on the frame the bank empties.

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
    if left > 0:
        return replace(running, seconds_left=left), None

    lives = round.rules.lives
    points = round.points + 1
    if lives is None or points >= lives:
        return replace(running, seconds_left=0.0, points=points, failed=True), Outcome.LOST
    # The ball got past him: it counts against him, the fact comes back three
    # questions later exactly as a missed one does, and the opponent serves again.
    return (
        replace(
            running,
            queue=_advance(round, retry=round.current),
            points=points,
            seconds_left=round.cap,
            on_current=0.0,
        ),
        Outcome.POINT,
    )


def _credit(round: Round) -> float | None:
    """Pay for a part, without ever pushing the bank down.

    A rocket round opens above its cap, so during that grace period a correct
    answer is simply worth nothing rather than a penalty.
    """
    if round.seconds_left is None:
        return None
    paid = round.seconds_left + round.seconds_per_part * round.rules.credit_parts
    return max(round.seconds_left, min(paid, round.cap))


def apply(round: Round, given: int) -> tuple[Round, Outcome]:
    if round.over:
        return round, Outcome.WON if round.launched else Outcome.LOST

    rules = round.rules
    question = round.current
    correct = given == question.answer
    tallied = round.attempts.get(question.key, Tally()).record(correct, round.on_current)
    counted = replace(
        round,
        asked=round.asked + 1,
        missed=round.missed + (not correct),
        attempts={**round.attempts, question.key: tallied},
        on_current=0.0,
    )
    if not correct and not rules.wrong_advances:
        # The ball is still in the air; he may retype while it falls. Touching
        # the queue here would put the same fact in the deck twice.
        return counted, Outcome.WRONG

    if correct:
        parts = min(round.parts + 1, rules.target)
    elif rules.wrong_costs_part:
        parts = max(round.parts - 1, 0)
    else:
        parts = round.parts
    launched = parts >= rules.target
    updated = replace(
        counted,
        queue=_advance(round, retry=None if correct else question),
        parts=parts,
        launched=launched,
        seconds_left=_credit(round) if correct else round.seconds_left,
    )
    if launched:
        return updated, Outcome.WON
    return updated, Outcome.CORRECT if correct else Outcome.WRONG
