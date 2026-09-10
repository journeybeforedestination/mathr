"""The complete question pool for every level.

Each level is enumerated rather than generated: the pools are small, and a
tuple built once is both simpler than a random generator and testable by
assertion.
"""

import random
from dataclasses import dataclass, replace
from typing import Mapping


@dataclass(frozen=True)
class Strategy:
    """The route to an answer, as numbers on a line: where to stand, and the
    hops from there.

    Numbers only — no span, no coordinates, no colours. What the line is drawn
    across is the shell's business, which is what lets one widget serve
    bridging, bonds and times tables alike.
    """

    start: int
    jumps: tuple[int, ...]

    @property
    def end(self) -> int:
        return self.start + sum(self.jumps)


@dataclass(frozen=True)
class Fact:
    """An equation with exactly one slot blank."""

    a: int
    op: str  # "+", "-" or "×"
    b: int
    result: int  # invariant: a op b == result
    blank: str  # "a" | "b" | "result"

    @property
    def answer(self) -> int:
        return {"a": self.a, "b": self.b, "result": self.result}[self.blank]

    @property
    def key(self) -> str:
        """Stable identity for the mastery record, which outlives this code.

        Derived only from the equation itself, never from pool position: the
        counts in progress.json are keyed by this string and cannot be
        reconstructed if the format changes.
        """
        return f"{self.a}{self.op}{self.b}={self.result}@{self.blank}"

    @property
    def sides(self) -> tuple[str, str]:
        def slot(name: str, value: int) -> str:
            return "?" if self.blank == name else str(value)

        return (f"{slot('a', self.a)} {self.op} {slot('b', self.b)}", slot("result", self.result))

    @property
    def prompt(self) -> str:
        left, right = self.sides
        return f"{left} = {right}"

    @property
    def strategy(self) -> Strategy:
        """How to get there, derived from the equation alone.

        `blank` is deliberately not an input: the picture shows the whole true
        equation, because showing the route *and* the answer is the point.
        """
        if self.op == "×":
            return Strategy(0, (self.a,) * self.b)
        if self.op == "÷":
            # The one operation whose answer is not a place on the line: this
            # draws `result` hops of `b` and lands on `a`, the dividend. It is
            # the same picture `b × result = a` draws, which is the whole of
            # how multiplication and division connect. The hop *count* is the
            # answer, so the renderer captions it — see `draw_number_line`.
            return Strategy(0, (self.b,) * self.result)
        if self.op == "+":
            if self.result > 10:
                # Bridging is the two-step move the level exists to teach, so
                # it is drawn as two hops rather than one long one.
                return Strategy(self.a, (10 - self.a, self.result - 10))
            return Strategy(0, (self.a, self.b))
        if self.a > 10 >= self.result:
            return Strategy(self.a, (-(self.a - 10), -(10 - self.result)))
        return Strategy(self.a, (-self.b,))


#: The line a fraction is placed on, in units of its own. Every denominator in
#: scope must divide this *and* leave an even quotient, or half a tick gap —
#: which is the tolerance — is not a whole number, and `place`, the click
#: conversion and the record all have to learn floats for one denominator.
#: 120 fails on eighths: `120 // 8` is 15, and half of that is 7.5. Before
#: adding a denominator, re-run
#: `[d for d in (2,3,4,5,6,8,10,12) if SPAN % d or (SPAN // d) % 2]` — it must
#: still be empty. Sevenths and ninths are in neither this span nor any span
#: that keeps the existing ones whole.
SPAN = 240


@dataclass(frozen=True)
class Target:
    """A fraction, and the line it is to be placed on.

    `ticks` is how many equal parts the line is drawn in, and it is not always
    `den`: `2/3` on thirds is the plain reading, and `1/3` on a line ticked in
    sixths is equivalence, at no mechanical cost.

    There is deliberately no `.answer`. Anything reaching for one is code that
    thinks this question is typed, and it should raise at the attribute rather
    than quietly compare a keypad entry against a position on a line.
    """

    num: int
    den: int
    ticks: int  # a multiple of `den`, or the fraction has no mark to land on

    @property
    def value(self) -> int:
        """Where it truly lies, in span units."""
        return SPAN * self.num // self.den

    @property
    def tolerance(self) -> int:
        """Half a tick gap: near enough that no other tick is nearer.

        Derived rather than a constant, so halves are forgiving and twelfths are
        tight without a dial per level — and so the ring drawn at it is the only
        thing on screen that says the shot got harder.
        """
        return SPAN // (2 * self.ticks)

    @property
    def prompt(self) -> str:
        return f"{self.num}/{self.den}"

    @property
    def key(self) -> str:
        """The partition is part of the identity, because `1/3` on thirds and
        `1/3` on sixths are different questions and must not share a row."""
        return f"{self.num}/{self.den}|{self.ticks}"

    @property
    def strategy(self) -> Strategy:
        """The route, in *tick* units rather than span units: `1/3` on sixths is
        one hop of two, which is the equivalence said out loud."""
        return Strategy(0, (self.ticks // self.den,) * self.num)


@dataclass(frozen=True)
class Question:
    """A fact as it is asked: the same equation, with `=` on either side.

    `? = 3 + 2` and `3 + 2 = ?` are the same retrieval, so orientation stays
    off `Fact` and out of `Fact.key` — it is never written to disk.
    """

    fact: Fact
    flipped: bool = False

    @property
    def answer(self) -> int:
        return self.fact.answer

    @property
    def key(self) -> str:
        return self.fact.key

    @property
    def prompt(self) -> str:
        left, right = self.fact.sides
        return f"{right} = {left}" if self.flipped else f"{left} = {right}"

    @property
    def strategy(self) -> Strategy:
        return self.fact.strategy


_APPLY = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "×": lambda a, b: a * b,
    "÷": lambda a, b: a // b,
}


@dataclass(frozen=True)
class Side:
    """One side of a sentence: a bare number, or a binary expression."""

    a: int
    op: str | None = None
    b: int | None = None

    @property
    def value(self) -> int:
        return self.a if self.op is None else _APPLY[self.op](self.a, self.b)

    @property
    def strategy(self) -> Strategy:
        """The route this side takes, borrowed from `Fact` rather than rebuilt.

        The picture drawn for `7 + 6` inside a sentence is then the same picture
        drawn for `7 + 6 = ?` in every other cabinet — bridging still stops at
        ten, and a division side still counts its hops.
        """
        if self.op is None:
            return Strategy(0, (self.a,))
        return Fact(self.a, self.op, self.b, self.value, "result").strategy

    def text(self, blank: str | None = None) -> str:
        a = "?" if blank == "a" else str(self.a)
        if self.op is None:
            return a
        return f"{a} {self.op} {'?' if blank == 'b' else self.b}"


@dataclass(frozen=True)
class Sentence:
    """A number sentence with `=` between two sides and one number missing.

    The missing number is the one that makes the two sides agree — `7 + 6 = ? + 5`
    is 8 — which is the relational reading of `=` this mode exists for, and the
    thing a child who reads `=` as "write the answer here" cannot do.

    Both sides are built from a level's own facts and hold their *true* numbers,
    including the one that is missing; `prompt` is what hides it. So a sentence
    is always true once filled, and there is nothing to store that could
    disagree with what he is reading.

    `Fact` is the degenerate case — one expression, one bare number — but it
    stays its own type, because `Fact.key` is a storage format that outlives the
    code and this is a different one.
    """

    left: Side
    right: Side
    mark: str  # "right.a" or "right.b": which of the right side's numbers is gone
    answer: int

    @property
    def slot(self) -> str:
        return self.mark.split(".")[1]

    @property
    def prompt(self) -> str:
        return f"{self.left.text()} = {self.right.text(self.slot)}"

    @property
    def filled(self) -> str:
        """The sentence with its number back, for a panel line already cracked."""
        return f"{self.left.text()} = {self.right.text()}"

    @property
    def key(self) -> str:
        """Keyed by the filled sentence, never by the blank shown.

        No collision with a `Fact.key`: a fact key's right side is always a bare
        number and its suffix names a slot of the equation, not of a side.
        """
        return f"{self.filled.replace(' ', '')}@{self.mark}"

    @property
    def strategies(self) -> tuple[Strategy, Strategy]:
        """Both routes, so a miss shows the *relation* — 7 + 6 and 8 + 5 both
        landing on 13 — rather than restating one side's arithmetic."""
        return (self.left.strategy, self.right.strategy)


#: What a round's queue holds. A mode's deck is one of these, never mixed, but
#: the queue is typed for all three because everything downstream of it —
#: `_advance`, the `Tally` keyed by `.key`, the reducer that resolves it — only
#: ever touches the members they have in common: `.key`, `.prompt` and the
#: route. A *parallel* deck beside the queue is the trap: `tick` charges
#: `on_current` to `queue[0]`, so time spent on one kind of item lands in the
#: `Tally` of another.
#:
#: `Target` is the one with no `.answer`, which is why `apply` is not the
#: reducer that resolves it — see `place` in `round.py`.
Item = Question | Sentence | Target


#: One round replays this deck; longer than the fifteen lines a round needs, and
#: short enough that a thin level does not repeat inside a single draw.
SENTENCE_DECK = 40


def _expressions(facts: tuple[Fact, ...]) -> tuple[tuple[Side, int], ...]:
    """The distinct expressions a pool holds, with their values.

    Deduped: a pool carries each equation once per blank, and the two are the
    same expression asked two ways.
    """
    seen: dict[tuple[int, str, int], int] = {}
    for fact in facts:
        seen.setdefault((fact.a, fact.op, fact.b), fact.result)
    return tuple((Side(a, op, b), value) for (a, op, b), value in seen.items())


def _both_sides(sides, pairs, rng):
    """`7 + 6 = ? + 5` — the line the mode exists for, and the only shape where
    neither side can be read off without the relation."""
    if not pairs:
        return None
    left, right = rng.sample(rng.choice(pairs), 2)
    return left, right


def _commuted(sides, pairs, rng):
    """`3 + 5 = ? + 3` — and the only relational shape a times level can make,
    since one fact per product leaves it no two expressions sharing a value."""
    options = [side for side, _ in sides if side.op in ("+", "×")]
    if not options:
        return None
    side = rng.choice(options)
    return side, Side(side.b, side.op, side.a)


def _decomposed(sides, pairs, rng):
    """`12 ÷ 2 = ? + 4` — split the value into two parts and hide one.

    The shape that rescues a thin pool: it needs no second expression sharing a
    value and nothing to commute, so a division level can build it where it can
    build almost nothing else. It is also the classic missing-addend form, which
    is what makes it worth having everywhere and not only there.
    """
    side, value = rng.choice(sides)
    if value < 2:
        return None
    # Both parts at least one: `18 ÷ 2 = 0 + ?` is not a decomposition, it is
    # the bare fact with a nought stuck on the front of it.
    part = rng.randrange(1, min(9, value - 1) + 1)
    return side, Side(value - part, "+", part)


def _fact_shaped(sides, pairs, rng):
    """`7 + 6 = ?`. Not relational at all — it is the question the other three
    cabinets ask — and it is what keeps a thin pool from having nothing to give:
    a division level has no two expressions sharing a value and nothing to
    commute. Weighted low for that reason.
    """
    side, value = rng.choice(sides)
    return side, Side(value)


_SHAPES = ((_both_sides, 5), (_commuted, 3), (_decomposed, 3), (_fact_shaped, 1))


def sentences(
    facts: tuple[Fact, ...], rng: random.Random, count: int = SENTENCE_DECK
) -> tuple[Sentence, ...]:
    """A deck of number sentences derived from a level's own pool.

    Not enumerated the way facts are: the combinations explode, and what matters
    is the mix of shapes rather than exhaustive coverage. Drawn through the
    injected rng, so a seed replays a deck exactly.
    """
    sides = _expressions(facts)
    by_value: dict[int, list[Side]] = {}
    for side, value in sides:
        by_value.setdefault(value, []).append(side)
    pairs = tuple(group for group in by_value.values() if len(group) > 1)

    builders = [shape for shape, _ in _SHAPES]
    weights = [weight for _, weight in _SHAPES]
    deck: list[Sentence] = []
    seen: set[str] = set()
    # Bounded, because a thin pool cannot fill a deck of this size: `divide_two`
    # has no two expressions sharing a value and nothing to commute, so it runs
    # out of distinct lines well before `count`. A short deck is fine —
    # `_advance` replays it — and a `while` without a budget would not return.
    for _ in range(count * 40):
        if len(deck) == count:
            break
        built = rng.choices(builders, weights)[0](sides, pairs, rng)
        if built is None:
            continue
        left, right = built
        mark = "right.a" if right.op is None else rng.choice(("right.a", "right.b"))
        line = Sentence(left, right, mark, getattr(right, mark.split(".")[1]))
        if line.prompt not in seen:
            seen.add(line.prompt)
            deck.append(line)
    return tuple(deck)


def shuffled(
    facts: tuple[Fact, ...],
    rng: random.Random,
    weights: Mapping[str, float] | None = None,
) -> tuple[Question, ...]:
    """The pool as a deck, each question oriented by the injected rng.

    With no weights this is a flat shuffle, and stays byte-identical to what it
    always was: the weighted path is a separate branch rather than a
    generalisation, because the unweighted one interleaves the orientation flip
    with the sample and every seeded test pins the result.

    Weighted, it is the standard order statistic for sampling without
    replacement — key each fact by `random() ** (1 / w)` and take the largest.
    A heavier fact is only more likely to come early, never certain to, so a
    round is still a shuffle and the whole pool is still in the deck.
    """
    if weights is None:
        return tuple(
            Question(fact, rng.random() < 0.5) for fact in rng.sample(facts, len(facts))
        )
    keyed = sorted(
        facts, key=lambda fact: rng.random() ** (1.0 / weights.get(fact.key, 1.0)), reverse=True
    )
    return tuple(Question(fact, rng.random() < 0.5) for fact in keyed)


def targets(pool: tuple[Target, ...], rng: random.Random) -> tuple[Target, ...]:
    """A pool of fractions as a deck.

    A flat shuffle of the whole pool, never a route through `shuffled`: that
    returns `Question`s, and its unweighted branch interleaves the orientation
    flip with `rng.sample` in an order two seeded tests pin. A short pool simply
    replays — `_advance` tops the queue up — exactly as a thin fact pool does.
    """
    return tuple(rng.sample(pool, len(pool)))


def _from_pair(a: int, b: int) -> tuple[Fact, ...]:
    """The four questions a number bond answers.

    The missing-addend forms are the point: `3 + ? = 5` *is* the bond, and it
    is the mental move that bridging ten depends on.
    """
    total = a + b
    return (
        Fact(a, "+", b, total, "result"),
        Fact(a, "+", b, total, "b"),
        Fact(total, "-", a, b, "result"),
        Fact(total, "-", a, b, "b"),
    )


def _times_pair(a: int, b: int) -> tuple[Fact, ...]:
    """The two questions a times fact answers.

    Sibling of `_from_pair` rather than a parameterization of it: the two extra
    forms that pair yields are subtraction, and the multiplication equivalents
    are division, which is deliberately not built.
    """
    return (
        Fact(a, "×", b, a * b, "result"),
        Fact(a, "×", b, a * b, "b"),
    )


def _divide_pair(a: int, b: int) -> tuple[Fact, ...]:
    """The two questions a division pair answers — exactly the two forms
    `_times_pair` leaves out.

    Both share one equation and therefore one route, the way a bond's two
    subtraction forms do.
    """
    total = a * b
    return (
        Fact(total, "÷", a, b, "result"),
        Fact(total, "÷", a, b, "b"),
    )


def _pool(pairs: tuple[tuple[int, int], ...], forms=_from_pair) -> tuple[Fact, ...]:
    return tuple(fact for pair in pairs for fact in forms(*pair))


def _times(n: int) -> tuple[Fact, ...]:
    return _pool(tuple((n, b) for b in range(11)), _times_pair)


def _divided(n: int) -> tuple[Fact, ...]:
    """From one, not from nought, unlike `_times`: `0 ÷ ? = 0` is true of every
    divisor, and a question with no single answer sits in the deck being marked
    wrong forever."""
    return _pool(tuple((n, b) for b in range(1, 11)), _divide_pair)


@dataclass(frozen=True)
class Level:
    id: str
    name: str
    facts: tuple[Fact, ...]
    seconds_per_part: float
    #: What this level asks, where it asks for a fraction to be placed rather
    #: than for an answer to be typed. One type rather than two: a level is
    #: also a card on a screen, and a second level type would fork that screen
    #: as well as this file. A level has one or the other, never both — which
    #: is what `Rules.targets_from_deck` picks between.
    targets: tuple[Target, ...] = ()
    """The pace one part has to be earned at. Every other clock constant is
    derived from this, so a level is retuned by changing one number.

    Bridging ten is a two-step move (15 - 7 is 15 - 5 - 2), so it gets longer
    than the recall levels rather than the same bar applied to a harder task.
    """


#: `fives_times` and the rest cannot reuse the addition ids: a level id keys a
#: LevelRecord in progress.json.
_ADDITION: tuple[Level, ...] = (
    Level("fives", "Make Five", _pool(tuple((a, 5 - a) for a in range(6))), 3.0),
    Level("tens", "Make Ten", _pool(tuple((a, 10 - a) for a in range(11))), 3.0),
    Level(
        "bridge",
        "Over the Ten",
        _pool(tuple((a, b) for a in range(1, 10) for b in range(1, 10) if a + b > 10)),
        5.0,
    ),
)

_MULTIPLY: tuple[Level, ...] = (
    Level("twos", "Times Two", _times(2), 5.0),
    Level("fives_times", "Times Five", _times(5), 5.0),
    Level("tens_times", "Times Ten", _times(10), 5.0),
)

#: Twenty facts a level rather than the times column's twenty-two: the zero
#: pair is not askable as a division. See `_divided`.
_DIVIDE: tuple[Level, ...] = (
    Level("divide_two", "Divide by Two", _divided(2), 5.0),
    Level("divide_five", "Divide by Five", _divided(5), 5.0),
    Level("divide_ten", "Divide by Ten", _divided(10), 5.0),
)

#: Derived, never hand-listed: a copied list drifts silently the moment a level
#: is retuned, and a pool-size test would keep passing on the stale number.
EVERYTHING = Level(
    "everything",
    "Everything",
    tuple(fact for level in _ADDITION + _MULTIPLY + _DIVIDE for fact in level.facts),
    5.0,
)

LEVELS: tuple[Level, ...] = _ADDITION + _MULTIPLY + _DIVIDE + (EVERYTHING,)


def _targets(partitions: tuple[tuple[int, int], ...]) -> tuple[Target, ...]:
    """Every proper fraction with these (denominator, partition) pairs.

    `0/b` and `b/b` are left out on purpose: both are the labelled ends of the
    line, so they are free marks that measure nothing and inflate the record —
    the same reason `_divided` starts at one rather than nought.
    """
    return tuple(
        Target(num, den, ticks) for den, ticks in partitions for num in range(1, den)
    )


#: The pace dial below is dead in these levels — the mode that asks them has no
#: clock, and nothing credits a part — but `Level` is one type on purpose.
#:
#: Ticked in its own denominator, four families of it: this is `3.NF.A.2`,
#: locating `a/b` on a line partitioned into `b` equal parts.
_FRACTION: tuple[Level, ...] = (
    Level("halves", "Halves & Fourths", (), 5.0, _targets(((2, 2), (4, 4)))),
    Level("thirds", "Thirds & Sixths", (), 5.0, _targets(((3, 3), (6, 6)))),
    Level("fifths", "Fifths & Tenths", (), 5.0, _targets(((5, 5), (10, 10)))),
    Level("eighths", "Eighths & Twelfths", (), 5.0, _targets(((8, 8), (12, 12)))),
    #: And the one where the two numbers disagree: `1/3` called on a line ticked
    #: in sixths. `3.NF.A.3` — equivalence — for the price of one more pool.
    Level(
        "same_as",
        "Same As",
        (),
        5.0,
        _targets(((2, 4), (2, 6), (2, 8), (2, 12), (3, 6), (3, 12), (4, 8), (4, 12))),
    ),
)

FRACTIONS = Level(
    "fractions",
    "Every Fraction",
    (),
    5.0,
    tuple(target for level in _FRACTION for target in level.targets),
)

FRACTION_LEVELS: tuple[Level, ...] = _FRACTION + (FRACTIONS,)

#: One map, two kinds of level: the shell looks a level up by the id on a card
#: and never asks which family it came from. `LEVELS` stays what it was, so a
#: test that walks every fact pool does not walk a pool with no facts in it.
LEVELS_BY_ID = {level.id: level for level in LEVELS + FRACTION_LEVELS}
