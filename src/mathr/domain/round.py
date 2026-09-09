"""One run of a level, as a pure reducer.

Knows about `parts: int`, a bank of seconds, and a `Rules` bundle that says how
both behave; it does not know that the parts are a rocket or that the clock is
an alien. A game mode picks a rule set, consumes the stream of outcomes, and
renders progress however it likes.
"""

import random
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Mapping

from .facts import Level, Question, shuffled

PARTS_TO_LAUNCH = 10
RETRY_GAP = 3  # far enough that he must retrieve the fact, not echo it

GRACE_PARTS = 5  # the rocket round opens with this many problems' worth of time
BANK_PARTS = 4  # and can never bank more than this many afterwards

BALL_FLIGHT = 1.5  # how many problems' worth of time a served ball takes to land

#: A placement: a number is named and he points at where it goes on a bare line.
#: The domain knows a span and a tolerance, never a football.
#:
#: In a placement mode the line and the parts bar are **the same axis**: one
#: part covers `PLACE_MAX / rules.target` of the line, the marker sits at
#: `parts` along it, and a good placement moves the marker to where it landed.
#: That is what makes the target meaningful rather than a number to be scored
#: against — and it is why the target is always drawn *ahead* of the marker.
PLACE_MAX = 100  # the span of the line, in whatever the mode calls units
PLACE_TOLERANCE = 6  # how far off still counts
PLACE_LIVES = 3  # incomplete placements the round survives
PLACE_GAIN_MIN = 10  # how far ahead of the marker the nearest target can be
PLACE_GAIN_MAX = 40  # and the furthest
#: A good placement is a *claim*, not a gain: it has to be confirmed by an
#: answer before it lapses. Two skills, one play — where the number goes, and
#: then the fact — and neither can be traded for the other.
CATCH_PARTS = 1.5  # how long the confirmation has, in problems
#: Offsets, drawn once per round and cycled. `asked` has no upper bound — the
#: deck replays — so a long enough round reaches the end of any fixed draw.
#: Cycling is invisible here because the target is the offset *plus wherever
#: the marker has got to*, which is never twice the same.
PLACE_DRAWS = 20

#: A fact is weighted by how long he takes on it, against the pace its level
#: asks for. Clamped, because one 24-second stall on a 5-second fact would
#: otherwise crowd the deck around a single bad morning.
WEIGHT_FLOOR = 0.5
WEIGHT_CEILING = 4.0


class Outcome(Enum):
    CORRECT = "correct"
    WRONG = "wrong"
    POINT = "point"  # the clock ran out but the round goes on
    # A placement, near enough or not. Named for what the domain knows — a
    # value on a line — because CAUGHT/INCOMPLETE would put a football in here.
    PLACED = "placed"  # near enough; now awaiting its confirming answer
    ADRIFT = "adrift"  # too far off, and there is nothing to confirm
    SECURED = "secured"  # the answer landed in time and the marker moved
    LAPSED = "lapsed"  # it did not, and the placement came to nothing
    WON = "won"
    LOST = "lost"


@dataclass(frozen=True)
class Rules:
    """What a mode changes about the round. Modes differ in rules, not only art.

    The rocket's clock is a shared bank; tennis's is a deadline per rally, and
    football stops both to ask for a placement. A dial covers each difference,
    and every one of them would otherwise be a silent wrong answer: a mode
    built as a pure renderer over the rocket's rules compiles, draws, and plays
    as a different game.
    """

    opening_parts: float  # bank at the start, in problems
    bank_parts: float  # ceiling on the bank, in problems
    credit_parts: float  # what a correct answer pays back, in problems
    wrong_costs_part: bool  # does a wrong answer take a part back
    wrong_advances: bool  # does a wrong answer move on to the next question
    lives: int | None  # empty-clock events survivable; None ends the round
    target: int  # parts needed to win
    places: bool = False  # does this mode ask for a placement whenever one is free
    confirm_parts: float | None = None  # None: a placement is never on the clock
    place_lives: int | None = None  # wide placements survivable; None is endless


#: A correct answer buys one problem's worth, up to a four-problem ceiling.
ROCKET = Rules(GRACE_PARTS, BANK_PARTS, 1.0, True, True, None, PARTS_TO_LAUNCH)

#: `credit_parts == bank_parts` is the rally reset: the bank is never above the
#: cap here, so crediting a full bank's worth always refills it exactly.
TENNIS = Rules(BALL_FLIGHT, BALL_FLIGHT, BALL_FLIGHT, False, False, 3, 10)

#: The rocket's clock and scoring, plus a placement after every answer. The
#: placement is the whole reason the mode exists, and the arithmetic around it
#: is what there are already two other modes for.
FOOTBALL = Rules(
    GRACE_PARTS, BANK_PARTS, 1.0, True, True, None, PARTS_TO_LAUNCH, True, CATCH_PARTS, PLACE_LIVES
)


def _spot(rules: Rules) -> int:
    """How much of the line one part covers. Ten yards, for football."""
    return PLACE_MAX // rules.target


@dataclass(frozen=True)
class Aim:
    """Placements in one bucket of the line. Written to disk, like `Tally`.

    Bucketed by decade rather than kept per exact value: eleven buckets fill
    with usable data in a week, a hundred and one never do.
    """

    attempts: int = 0
    error: float = 0.0  # summed absolute distance, in units of the line

    def record(self, error: float) -> "Aim":
        return Aim(attempts=self.attempts + 1, error=self.error + error)


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
    mode_id: str  # which game this was, so the record can say so
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
    hint: Question | None  # the miss being explained; every clock stops while set
    """One field for both "the clock is stopped" and "this is the question being
    drawn", so the two can never disagree.

    Reading time must not reach `Tally.seconds`: that is what the deck weighting
    reads, and time spent staring at a hint would push the fact just explained to
    the front of the next deck, which shows the hint again. `tick` returning
    early is the only thing that guarantees it — no arrangement of the shell can.
    """

    gains: tuple[int, ...] = ()  # how far ahead each placement is, from `new_round`
    placed: int = 0  # how many placements have been resolved
    aims: Mapping[str, Aim] = field(default_factory=dict)  # bucket -> Aim
    pending: int | None = None  # a good placement, waiting on its answer
    pending_left: float | None = None  # seconds it has left; None never lapses
    adrift: int = 0  # placements thrown wide; `place_lives` of them end the round

    @property
    def current(self) -> Question:
        return self.queue[0]

    @property
    def over(self) -> bool:
        return self.launched or self.failed

    @property
    def placing(self) -> int | None:
        """The value waiting to be placed, or None.

        Derived, never stored. A stored field would have to be written on every
        path that could clear it, and one missed path is a placement that never
        appears or one that appears twice — with nothing raising. Derived, it
        cannot disagree with the state it is read from.

        One is due whenever none is in the air: a wide one comes straight back
        as another attempt from the same spot, and a confirmed one is followed
        by the answer that confirmed it and then by the next. The only reasons
        there is none are that the round is over, that a hint is up, that one is
        already pending, or that the marker is inside the last part — where
        there is nowhere ahead to aim and the rest has to be answered for.

        The hint wins: a wrong answer raises both at once, and settling it here
        keeps the shell free of the rule. `dismiss` then makes the placement
        live with no extra code.

        Always ahead of the marker, never behind it or on it. A target drawn
        across the whole line reads as a pass thrown backwards down the field —
        the mechanic works, and the metaphor it is wrapped in is a lie.
        """
        if not self.rules.places or self.over or self.hint is not None:
            return None
        if self.pending is not None:
            return None  # one is already in the air
        spot = _spot(self.rules)
        here = self.parts * spot
        target = min(PLACE_MAX - 1, here + self.gains[self.placed % len(self.gains)])
        # Within one part of the end there is nowhere ahead left to aim: the
        # last stretch has to be covered by answers.
        return target if target - here >= spot else None

    @property
    def confirm_seconds(self) -> float:
        """How long a placement gets, for a renderer that draws it closing in."""
        return self.seconds_per_part * (self.rules.confirm_parts or 0.0)

    @property
    def cap(self) -> float:
        return self.seconds_per_part * self.rules.bank_parts

    @property
    def timed(self) -> bool:
        return self.seconds_left is not None


def _weights(level: Level, history: Mapping[str, Tally]) -> Mapping[str, float]:
    """Mean response time against the level's own pace, per fact.

    Computed here rather than in `facts.py` because `Tally` lives here and
    `round` already imports `facts`; reaching the other way closes an import
    cycle. A fact never answered is absent, and `shuffled` weighs it 1.0 — with
    most facts seen once or not at all there is no verdict to pass on them yet.

    The signal is time, not wrongness: his misses are few and half of them are
    typos, and a wrong answer's thinking time is folded into `Tally.seconds`
    regardless, so slow-and-wrong floats up without a second term.
    """
    return {
        key: min(
            WEIGHT_CEILING,
            max(WEIGHT_FLOOR, tally.seconds / tally.answered / level.seconds_per_part),
        )
        for key, tally in history.items()
        if tally.answered
    }


def new_round(
    level: Level,
    rng: random.Random,
    timed: bool = True,
    rules: Rules = ROCKET,
    history: Mapping[str, Tally] | None = None,
    mode_id: str = "rocket",
) -> Round:
    if not timed and rules.lives is not None:
        # A rally has nowhere to put the ball without a deadline to fly along.
        raise ValueError("a round with lives cannot be untimed")
    # The whole pool stays in the deck and only its order is biased: a ten-part
    # round draws from the front, so ordering is selection, and no level can
    # ever empty itself into a "mastered" state the level screen would have to
    # show.
    deck = shuffled(level.facts, rng, _weights(level, history) if history else None)
    # Drawn here, never in a reducer: `tick`, `apply` and `place` take no rng,
    # and a round that cannot be replayed from its seed breaks the shuffle
    # tests in a way that reads as a shuffle bug. A mode without placements
    # draws nothing, so its consumption of the rng is exactly what it was.
    gains = (
        tuple(rng.choices(range(PLACE_GAIN_MIN, PLACE_GAIN_MAX + 1), k=PLACE_DRAWS))
        if rules.places
        else ()
    )
    return Round(
        level_id=level.id,
        mode_id=mode_id,
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
        hint=None,
        gains=gains,
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
    """Advance the clock. Returns LOST or POINT on the frame the bank empties,
    or LAPSED on the frame a pending placement runs out of time.

    Time on the current question accumulates even in an untimed round: the
    per-fact response times are worth having either way, and practice is
    where the slowest facts actually surface. The one exception is a hint, and
    it is the whole reason the hint lives in the domain: `seconds_left`,
    `on_current` and `elapsed` all stop together here, by construction, rather
    than wherever the shell happened to put its skip.

    A pending placement drains alongside the bank rather than instead of it —
    both are running against him, which is what makes the confirmation a race.
    The bank wins a tie: losing the round outranks losing one placement.

    A lapse carries no hint, unlike every other way of running out of time. The
    next thing it asks for is a *click on the field*, and a hint can only be put
    away by typing — a click that dismissed one would also be a throw, aimed
    wherever he happened to be reading.
    """
    if round.over or round.hint is not None or round.placing is not None:
        return round, None

    running = replace(
        round,
        elapsed=round.elapsed + dt,
        on_current=round.on_current + dt,
    )
    lapsed = False
    if round.pending_left is not None:
        left = round.pending_left - dt
        lapsed = left <= 0
        running = (
            replace(
                running,
                pending=None,
                pending_left=None,
                # A dropped ball takes its question with it. He never answered
                # it, so it comes back later in the deck exactly as a missed one
                # does — and the next placement is confirmed by a fresh fact
                # rather than by the one he was halfway through typing.
                queue=_advance(round, retry=round.current),
                on_current=0.0,
            )
            if lapsed
            else replace(running, pending_left=left)
        )

    def settled(state: Round) -> tuple[Round, Outcome | None]:
        return (state, Outcome.LAPSED) if lapsed else (state, None)

    if round.seconds_left is None:
        return settled(running)

    left = round.seconds_left - dt
    if left > 0:
        return settled(replace(running, seconds_left=left))

    lives = round.rules.lives
    points = round.points + 1
    if lives is None or points >= lives:
        # No hint on the way out: the failure screen owns the display, and a
        # hint here would stop the very clock the failure animation runs on.
        # A placement still in the air is void for the same reason — the failure
        # screen is not the place to keep drawing a ball nobody can catch.
        return (
            replace(
                running,
                seconds_left=0.0,
                points=points,
                failed=True,
                pending=None,
                pending_left=None,
            ),
            Outcome.LOST,
        )
    # The ball got past him: it counts against him, the fact comes back three
    # questions later exactly as a missed one does, and the opponent serves again.
    return (
        replace(
            running,
            queue=_advance(round, retry=round.current),
            points=points,
            seconds_left=round.cap,
            on_current=0.0,
            hint=round.current,
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


def dismiss(round: Round) -> Round:
    """Put the hint away and start every clock again. Only the shell calls this:
    the hint is self-paced, and the domain has no idea how long a read takes."""
    return replace(round, hint=None) if round.hint is not None else round


def place(round: Round, value: int) -> tuple[Round, Outcome]:
    """Take the placement. A good one becomes a *claim*, not a gain.

    It moves nothing yet: it goes to `pending`, and the next answer either
    confirms it (`apply` → SECURED, and the marker jumps to where it was
    called) or fails to before `pending_left` runs out (`tick` → LAPSED, and it
    comes to nothing). Two skills in one play — where the number goes, and then
    the fact — and neither can be traded for the other.

    The distance is thresholded into a boolean here, at the boundary, so
    `Outcome` stays a flat enum every mode can consume. The raw distance is not
    lost: it accumulates in `aims`, which is what a later reading of how his
    estimation is moving will want.
    """
    called = round.placing
    if called is None:
        raise ValueError("no placement is pending")
    error = abs(value - called)
    good = error <= PLACE_TOLERANCE
    bucket = str(called // 10 * 10)
    # A wide one advances nothing at all — not the marker, not the queue, not
    # the question under it. It costs an attempt, and `place_lives` of them end
    # the round; that is the whole price of a miss, and it is why the next call
    # comes from the same spot.
    adrift = round.adrift + (not good)
    lives = round.rules.place_lives
    turnover = not good and lives is not None and adrift >= lives
    taken = replace(
        round,
        placed=round.placed + 1,
        adrift=adrift,
        failed=turnover,
        aims={**round.aims, bucket: round.aims.get(bucket, Aim()).record(error)},
        pending=called if good else None,
        # An untimed round has no deadline to put on the confirmation either:
        # the Timer toggle takes every clock away, not most of them.
        pending_left=(
            round.confirm_seconds if good and round.timed and round.rules.confirm_parts else None
        ),
    )
    if turnover:
        return taken, Outcome.LOST
    return taken, Outcome.PLACED if good else Outcome.ADRIFT


def _secure(round: Round) -> tuple[int, bool]:
    """The marker, moved to the placement being confirmed.

    `max`, not assignment: the target is always ahead, and floor division must
    never be able to walk the marker backwards.
    """
    parts = max(round.parts, round.pending // _spot(round.rules))
    return parts, parts >= round.rules.target


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
        # Written on every path, right or wrong, so a stale hint cannot survive
        # an answer.
        hint=None if correct else question,
    )
    if round.pending is not None:
        # This answer is the confirmation, so it plays by the rally's rules
        # rather than this mode's: the question stays up and costs nothing until
        # either it is right or the placement lapses under it. The hint `counted`
        # carries stops every clock, the pending one included, so he reads it
        # with the placement frozen exactly as a rally freezes.
        if not correct:
            return counted, Outcome.WRONG
        parts, launched = _secure(round)
        secured = replace(
            counted,
            queue=_advance(round),
            parts=parts,
            launched=launched,
            pending=None,
            pending_left=None,
            seconds_left=_credit(round),
        )
        return secured, Outcome.WON if launched else Outcome.SECURED

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
