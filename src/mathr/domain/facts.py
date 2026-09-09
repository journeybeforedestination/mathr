"""The complete question pool for every level.

Each level is enumerated rather than generated: the pools are small, and a
tuple built once is both simpler than a random generator and testable by
assertion.
"""

import random
from dataclasses import dataclass


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


def shuffled(facts: tuple[Fact, ...], rng: random.Random) -> tuple[Question, ...]:
    """The pool as a deck, each question oriented by the injected rng."""
    return tuple(
        Question(fact, rng.random() < 0.5) for fact in rng.sample(facts, len(facts))
    )


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


def _pool(pairs: tuple[tuple[int, int], ...], forms=_from_pair) -> tuple[Fact, ...]:
    return tuple(fact for pair in pairs for fact in forms(*pair))


def _times(n: int) -> tuple[Fact, ...]:
    return _pool(tuple((n, b) for b in range(11)), _times_pair)


@dataclass(frozen=True)
class Level:
    id: str
    name: str
    facts: tuple[Fact, ...]
    seconds_per_part: float
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

#: Derived, never hand-listed: a copied list drifts silently the moment a level
#: is retuned, and a pool-size test would keep passing on the stale number.
EVERYTHING = Level(
    "everything",
    "Everything",
    tuple(fact for level in _ADDITION + _MULTIPLY for fact in level.facts),
    5.0,
)

LEVELS: tuple[Level, ...] = _ADDITION + _MULTIPLY + (EVERYTHING,)

LEVELS_BY_ID = {level.id: level for level in LEVELS}
