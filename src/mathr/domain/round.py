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

from .facts import Item, Level, Sentence, sentences, shuffled, targets

PARTS_TO_LAUNCH = 10
RETRY_GAP = 3  # far enough that he must retrieve the fact, not echo it

GRACE_PARTS = 5  # the rocket round opens with this many problems' worth of time
BANK_PARTS = 4  # and can never bank more than this many afterwards

BALL_FLIGHT = 1.5  # how many problems' worth of time a served ball takes to land

#: A code-breaking round is three locks, each longer than the last. The last
#: lock should not feel like the first, which is the one thing a flat run of ten
#: identical questions cannot do.
LOCKS = (4, 5, 6)
LINES_TO_CRACK = sum(LOCKS)
ALARMS = 3  # wrong answers before the vault locks down

#: A placement: a number is named and he points at where it goes on a bare line.
#: The domain knows a span and a tolerance, never a football.
#:
#: In a placement mode the marker **is** the line: `rules.target == PLACE_MAX`,
#: `parts` is the position along it, and a confirmed placement moves the marker
#: to exactly the value that was called. Anything coarser — parts as tens of
#: yards, say — makes a pass caught on the 27 land on the 20, and the number he
#: estimated stops being the number he gets, which is the whole mode.
PLACE_MAX = 100  # the span of the line, in whatever the mode calls units
PLACE_TOLERANCE = 6  # how far off still counts
PLACE_LIVES = 3  # incomplete placements the round survives
PLACE_GAIN_MIN = 10  # how far ahead of the marker the nearest target can be
PLACE_GAIN_MAX = 40  # and the furthest
#: A good placement is a *claim*, not a gain: it has to be confirmed by an
#: answer before it lapses. Two skills, one play — where the number goes, and
#: then the fact — and neither can be traded for the other.
CATCH_PARTS = 1.5  # how long the confirmation has, in problems
#: Some plays lose ground instead of gaining it, and the marker going backwards
#: is the point of them: without it he only ever estimates ahead of a marker
#: that marches up the line, and the low numbers come up once, at the start.
#: The yardage is *stated* and the new spot is not, so placing it is a
#: subtraction modelled on the line rather than a number to be read off.
SACK_CHANCE = 0.25  # how often a play is a sack rather than a throw
SACK_MIN = 4  # yards it costs
SACK_MAX = 12
#: And one is overdue past halfway if none has happened yet. Three long catches
#: can otherwise walk the length of the line without the marker ever going
#: backwards, which is the run of play this mode has least to teach in.
SACK_BY = PLACE_MAX // 2
#: A wide placement gives up ground as well as an attempt. Without it a miss at
#: the top of the field costs nothing he can see, and the cheapest way to finish
#: a drive is to keep clicking until one sticks.
PLACE_PENALTY = 10
#: Offsets, drawn once per round and cycled. `asked` has no upper bound — the
#: deck replays — so a long enough round reaches the end of any fixed draw.
#: Cycling is invisible here because the target is the offset *plus wherever
#: the marker has got to*, which is never twice the same.
PLACE_DRAWS = 20

#: A fraction placed on a partitioned line. The target is drawn from the *deck*
#: rather than from the marker, which is what makes it an item like any other:
#: a level can then say which fractions it asks, and the ticks under them are
#: the denominator he is reading. A target derived from the marker the way a
#: yard is would ask for `23/100` on a line ticked in sixths.
#:
#: `parts` therefore goes back to meaning what it means in the rocket — stones
#: in the house, out of eight — rather than a position on the line.
STONES = 8  # stones in an end
STONE_LIVES = 3  # wide ones before the end is lost

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
    SETBACK = "setback"  # the marker was driven back, and he placed where to
    # Named for what the domain knows — a run of lines finished — because
    # UNLOCKED would put a vault in here.
    CRACKED = "cracked"  # that line completed a lock
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
    #: How many lines each lock takes, in order. Non-empty means this mode's
    #: deck is sentences rather than facts, and that its target is grouped into
    #: locks that open one at a time. One dial rather than two: a mode that has
    #: locks has sentences in them, and there is no useful mode that has either
    #: without the other.
    locks: tuple[int, ...] = ()
    #: Where a placement's target comes from: the deck, or the marker.
    #:
    #: The placement is then the *question* — `queue[0]` names it — rather than
    #: an offset added to wherever the marker has got to. That is the difference
    #: between a mode whose level chooses what is asked and one whose previous
    #: throws do, and it is also what makes `place` this mode's `apply`: it
    #: advances the queue, writes the `Tally` and credits the part, because
    #: nothing else will.
    targets_from_deck: bool = False
    #: Does a wrong answer cost one of `lives`. Without it `lives` means only
    #: "empty-clock events survived" — `points` is incremented in `tick` and
    #: nowhere else — so a mode with lives and no clock has three of them that
    #: nothing can ever spend, and a round that can be neither won nor lost.
    wrong_costs_life: bool = False


#: A correct answer buys one problem's worth, up to a four-problem ceiling.
ROCKET = Rules(GRACE_PARTS, BANK_PARTS, 1.0, True, True, None, PARTS_TO_LAUNCH)

#: `credit_parts == bank_parts` is the rally reset: the bank is never above the
#: cap here, so crediting a full bank's worth always refills it exactly.
TENNIS = Rules(BALL_FLIGHT, BALL_FLIGHT, BALL_FLIGHT, False, False, 3, 10)

#: The rocket's clock and scoring, plus a placement after every answer. The
#: placement is the whole reason the mode exists, and the arithmetic around it
#: is what there are already two other modes for.
FOOTBALL = Rules(
    GRACE_PARTS, BANK_PARTS, 1.0, True, True, None, PLACE_MAX, True, CATCH_PARTS, PLACE_LIVES
)

#: No clock at all, and the lives are alarms a wrong answer trips. The skill
#: this mode measures is reasoning *faster than his own arithmetic*, and a
#: threat clock suppresses the very thing being measured — so the three timing
#: dials are dead here, and `tick` still accumulates the response times that
#: make the measurement, because it does that in an untimed round by design.
#:
#: A wrong answer does not advance: the line is still locked and he still has to
#: open it. What it costs is an alarm.
CODE = Rules(
    0.0,
    0.0,
    0.0,
    False,
    False,
    ALARMS,
    LINES_TO_CRACK,
    locks=LOCKS,
    wrong_costs_life=True,
)


#: No clock, no keypad, and the placement is the whole question: eight stones,
#: each a fraction to be put on a ticked line, three wide ones and the end is
#: over. The three timing dials are dead here, as they are in `CODE` — a
#: stopwatch on a deliberate estimate measures the stopwatch.
CURLING = Rules(
    0.0,
    0.0,
    0.0,
    False,
    False,
    None,
    STONES,
    places=True,
    place_lives=STONE_LIVES,
    targets_from_deck=True,
)


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
    deck: tuple[Item, ...]  # the shuffled pool, replayed when the queue runs low
    queue: tuple[Item, ...]  # upcoming; queue[0] is on screen
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
    hint: Item | None  # the miss being explained; every clock stops while set
    """One field for both "the clock is stopped" and "this is the question being
    drawn", so the two can never disagree.

    Reading time must not reach `Tally.seconds`: that is what the deck weighting
    reads, and time spent staring at a hint would push the fact just explained to
    the front of the next deck, which shows the hint again. `tick` returning
    early is the only thing that guarantees it — no arrangement of the shell can.
    """

    gains: tuple[int, ...] = ()  # how far ahead each placement is, from `new_round`
    sacks: tuple[int, ...] = ()  # what a sack would cost, per play
    sack_at: tuple[bool, ...] = ()  # and which plays are one
    sacks_taken: int = 0  # how many have actually happened
    placed: int = 0  # how many placements have been resolved
    aims: Mapping[str, Aim] = field(default_factory=dict)  # bucket -> Aim
    pending: int | None = None  # a good placement, waiting on its answer
    pending_left: float | None = None  # seconds it has left; None never lapses
    adrift: int = 0  # placements thrown wide; `place_lives` of them end the round
    cracked: tuple[Sentence, ...] = ()  # lines already open in the lock he is on

    @property
    def current(self) -> Item:
        return self.queue[0]

    @property
    def over(self) -> bool:
        return self.launched or self.failed

    @property
    def sacked(self) -> int | None:
        """Ground this play loses, if it is a sack rather than a throw.

        Never when there is less on the field than the sack would take: a loss
        that would bury the marker at zero is arithmetic with nothing in it, and
        the first plays of a round are for driving.
        """
        if not self.rules.places or self.over or self.hint is not None:
            return None
        if self.pending is not None:
            return None
        if not self.sacks:
            return None
        slot = self.placed % len(self.sacks)
        loss = self.sacks[slot]
        if loss >= self.parts:
            return None  # nothing on the field to give up
        # Past halfway with none taken, the next play is one whatever the draw
        # said: a drive that never goes backwards is the easiest one to make.
        overdue = self.sacks_taken == 0 and self.parts > SACK_BY
        return loss if self.sack_at[slot] or overdue else None

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
        already pending. Every question he answers is one confirming a
        placement; there is no other kind of down in a mode that places.

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
        if self.rules.targets_from_deck:
            # The question itself, before any of the machinery that walks a
            # marker up a line: what is asked comes from the deck, so it is the
            # level that decides it and not the throws that came before.
            return self.current.value
        loss = self.sacked
        if loss is not None:
            # The one target that is *behind* the marker, and the one he is not
            # told: he is told what it cost, and has to say where that leaves him.
            return self.parts - loss
        here = self.parts
        if here + PLACE_GAIN_MIN > PLACE_MAX - 1:
            # Close enough that no honest target is left ahead of him, so the
            # call is the end of the line itself. It is the one easy placement
            # in a round, and it is the one that wins it.
            return PLACE_MAX
        return min(PLACE_MAX - 1, here + self.gains[self.placed % len(self.gains)])

    @property
    def lock(self) -> tuple[int, int, int]:
        """Which lock he is on, how many of its lines are open, how long it is.

        Derived from `parts` alone, so it cannot disagree with the score. A
        stored lock index would have to be written on every path that moves
        `parts`, and one missed path is a vault that opens twice or never.
        """
        return _lock_at(self.rules, self.parts)

    @property
    def losable(self) -> bool:
        """Whether this round has any way to end badly.

        What makes a win farmable is having no way to lose, not having no clock
        — which is why `storage._fold` asks this rather than asking `timed`.
        Three ways to lose now, and each arrived with a mode that had no other:
        an empty clock, an alarm, and a placement thrown wide.
        """
        return (
            self.timed
            or self.rules.wrong_costs_life
            or self.rules.place_lives is not None
        )

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


def _lock_at(rules: Rules, done: int) -> tuple[int, int, int]:
    """Where `done` lines in falls: (which lock, how many of it, how long it is)."""
    if not rules.locks:
        return 0, done, rules.target
    for index, size in enumerate(rules.locks):
        if done < size:
            return index, done, size
        done -= size
    last = len(rules.locks) - 1
    return last, rules.locks[last], rules.locks[last]


def _opens_a_lock(rules: Rules, done: int) -> bool:
    """Whether the `done`th line was the one that swung a vault open."""
    total = 0
    for size in rules.locks:
        total += size
        if done == total:
            return True
    return False


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
    if not timed and rules.lives is not None and not rules.wrong_costs_life:
        # Lives are spent by the clock emptying unless a mode says otherwise, so
        # an untimed round with lives and nothing else to spend them has three
        # of them that nothing can touch, and a round that cannot be lost. For
        # tennis that is still exactly true — a rally has nowhere to put the
        # ball without a deadline to fly along.
        raise ValueError("a round with lives needs something that can spend one")
    if rules.locks and sum(rules.locks) != rules.target:
        # Otherwise the last vault never swings, or the round is won partway
        # through a lock with lines still showing on the panel.
        raise ValueError("the locks must add up to the target")
    if rules.places and not rules.targets_from_deck and rules.target != PLACE_MAX:
        # The marker is the line. A shorter bar would quietly round every catch
        # down to the nearest part instead of spotting it where it was called.
        # Only where the target is a function of the marker: a mode whose
        # targets come from the deck counts stones, and the line it places them
        # on is the item's own.
        raise ValueError("a placement mode must run the length of the line")
    # The whole pool stays in the deck and only its order is biased: a ten-part
    # round draws from the front, so ordering is selection, and no level can
    # ever empty itself into a "mastered" state the level screen would have to
    # show.
    # A judging mode's deck is sentences derived from the same pool, so every
    # arithmetic cabinet still leads to the same level cards. They are not
    # weighted: `_weights` reads a per-fact history, and a sentence is not a
    # fact — nor is a fraction.
    # A placing mode whose targets come from the deck is asking fractions, and
    # they are not weighted either: `_weights` reads a per-fact history against
    # a per-level pace, and a stone has neither.
    if rules.targets_from_deck:
        deck = targets(level.targets, rng)
    elif rules.locks:
        deck = sentences(level.facts, rng)
    else:
        deck = shuffled(level.facts, rng, _weights(level, history) if history else None)
    # Drawn here, never in a reducer: `tick`, `apply` and `place` take no rng,
    # and a round that cannot be replayed from its seed breaks the shuffle
    # tests in a way that reads as a shuffle bug. A mode without placements
    # draws nothing, so its consumption of the rng is exactly what it was.
    walks = rules.places and not rules.targets_from_deck
    gains = (
        tuple(rng.choices(range(PLACE_GAIN_MIN, PLACE_GAIN_MAX + 1), k=PLACE_DRAWS))
        if walks
        else ()
    )
    # What each play would cost and whether it is one are drawn apart, because
    # the halfway rule needs a yardage for a play the draw did not pick.
    sacks = (
        tuple(rng.randrange(SACK_MIN, SACK_MAX + 1) for _ in range(PLACE_DRAWS))
        if walks
        else ()
    )
    sack_at = (
        tuple(rng.random() < SACK_CHANCE for _ in range(PLACE_DRAWS)) if walks else ()
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
        sacks=sacks,
        sack_at=sack_at,
    )


def _advance(round: Round, retry: Item | None = None) -> tuple[Item, ...]:
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
    if round.over or round.hint is not None:
        return round, None
    if round.placing is not None and not round.rules.targets_from_deck:
        # A called yard stops every clock, the way a hint does — the time spent
        # aiming must not reach `Tally.seconds`, which is the deck weighting's
        # input. Where the placement *is* the question there is always one due,
        # so the same early return would stop the round's only clock forever and
        # record every stone as having taken no time at all. Nothing weights
        # that deck, so there is nothing to corrupt by letting it run.
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
    """Take the placement. Two modes place, and they place differently.

    Where the target came from the deck it is the *question*, thrown once, and
    `_slide` below does the whole of it — including everything `apply` would
    have done, because that mode never calls `apply`.

    Where the marker named it, a good one becomes a *claim*, not a gain.
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
    if round.rules.targets_from_deck:
        return _slide(round, value)
    error = abs(value - called)
    good = error <= PLACE_TOLERANCE
    lost = round.sacked
    if lost is not None:
        return _take_the_loss(round, called, good)
    bucket = str(called // 10 * 10)
    # A wide one touches neither the queue nor the question under it: there is
    # nothing to re-ask, and the next call comes from wherever the penalty
    # leaves him. What it costs is an attempt and `PLACE_PENALTY` of ground —
    # `place_lives` attempts end the round.
    adrift = round.adrift + (not good)
    lives = round.rules.place_lives
    turnover = not good and lives is not None and adrift >= lives
    taken = replace(
        round,
        placed=round.placed + 1,
        adrift=adrift,
        failed=turnover,
        # Floored here rather than in the renderer: a negative marker indexes
        # the line from the far end.
        parts=round.parts if good else max(0, round.parts - PLACE_PENALTY),
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


def _slide(round: Round, value: int) -> tuple[Round, Outcome]:
    """The stone, thrown once. This is the mode's `apply`, not its `place`.

    A football placement comes straight back as another attempt from the same
    spot, and the question under it is untouched because a *later answer* is
    what confirms it. A stone is thrown once: wide or not, the next fraction
    comes up. So this branch does what `apply` does everywhere else — advances
    the queue, writes the `Tally`, credits the part — because in this mode
    `apply` is never called. A fourth reducer would be three copies of that,
    and they would drift the first time `Tally` changed.

    No re-queue. A missed *fact* has to come back — retrieval, not echo — but
    the ghost has just shown him the true mark, so re-asking the same fraction
    three stones later is asking him to reproduce a picture he is looking at.

    `on_current` is zeroed here for the same reason `apply` zeroes it: nothing
    else does, and without it every stone after the first is recorded as having
    taken the whole end.
    """
    target = round.current
    good = abs(value - target.value) <= target.tolerance
    adrift = round.adrift + (not good)
    lives = round.rules.place_lives
    lost = not good and lives is not None and adrift >= lives
    parts = round.parts + good
    won = parts >= round.rules.target
    thrown = replace(
        round,
        queue=_advance(round),
        parts=parts,
        asked=round.asked + 1,
        missed=round.missed + (not good),
        attempts={
            **round.attempts,
            target.key: round.attempts.get(target.key, Tally()).record(good, round.on_current),
        },
        on_current=0.0,
        adrift=adrift,
        placed=round.placed + 1,
        launched=won,
        failed=lost,
    )
    if lost:
        return thrown, Outcome.LOST
    if won:
        return thrown, Outcome.WON
    return thrown, Outcome.PLACED if good else Outcome.ADRIFT


def _take_the_loss(round: Round, spot: int, good: bool) -> tuple[Round, Outcome]:
    """A sack, placed. The marker goes back whichever way it was placed.

    Spotting it at his click instead would make a sack the cheapest way up the
    field — a few yards forward of the truth, every time, inside the tolerance.
    The yardage is a fact of the play; only saying where it leaves him is his.

    Nothing goes into `aims` either. That record is how far off he is when he is
    *shown* a number, and an error here is as much the subtraction as the line.
    """
    adrift = round.adrift + (not good)
    lives = round.rules.place_lives
    turnover = not good and lives is not None and adrift >= lives
    # No `PLACE_PENALTY` here: the play has already taken its ground, and a
    # missed spot would otherwise cost twice for one mistake.
    taken = replace(
        round,
        parts=spot,
        placed=round.placed + 1,
        adrift=adrift,
        failed=turnover,
        sacks_taken=round.sacks_taken + 1,
    )
    if turnover:
        return taken, Outcome.LOST
    return taken, Outcome.SETBACK if good else Outcome.ADRIFT


def _secure(round: Round) -> tuple[int, bool]:
    """The marker, moved to exactly the value that was placed.

    `max` rather than assignment so that nothing here can ever walk the marker
    backwards, whatever a later rule does to the targets.
    """
    parts = max(round.parts, round.pending)
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

    if not correct and rules.wrong_costs_life:
        # An alarm, not a part. The line is still locked and he still has to
        # open it, so the queue does not move and nothing is taken away — what
        # it costs is one of three tries at being wrong in the whole round. The
        # hint `counted` carries shows both sides, which is how he gets it next
        # time rather than guessing again.
        points = round.points + 1
        lives = rules.lives
        caught = lives is not None and points >= lives
        tripped = replace(
            counted,
            points=points,
            failed=caught,
            # No hint on the way out: the failure screen owns the display, for
            # the reason `tick` gives on the same path.
            hint=None if caught else question,
        )
        return tripped, Outcome.LOST if caught else Outcome.WRONG

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
    opened = correct and _opens_a_lock(rules, parts)
    updated = replace(
        counted,
        queue=_advance(round, retry=None if correct else question),
        parts=parts,
        launched=launched,
        seconds_left=_credit(round) if correct else round.seconds_left,
        # The lines of the lock he is on, so the panel can show what he has
        # already opened. Cleared as each vault swings, because the next lock
        # starts empty and a panel that kept growing would run off the screen.
        cracked=() if opened else (*round.cracked, question) if correct and rules.locks else round.cracked,
    )
    if launched:
        return updated, Outcome.WON
    if opened:
        return updated, Outcome.CRACKED
    return updated, Outcome.CORRECT if correct else Outcome.WRONG
