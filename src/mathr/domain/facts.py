"""The complete question pool for every level.

Each level is enumerated rather than generated: the pools are small, and a
tuple built once is both simpler than a random generator and testable by
assertion.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    """An equation with exactly one slot blank."""

    a: int
    op: str  # "+" or "-"
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
    def prompt(self) -> str:
        def slot(name: str, value: int) -> str:
            return "?" if self.blank == name else str(value)

        return f"{slot('a', self.a)} {self.op} {slot('b', self.b)} = {slot('result', self.result)}"


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


def _pool(pairs: tuple[tuple[int, int], ...]) -> tuple[Fact, ...]:
    return tuple(fact for pair in pairs for fact in _from_pair(*pair))


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


LEVELS: tuple[Level, ...] = (
    Level("fives", "Make Five", _pool(tuple((a, 5 - a) for a in range(6))), 3.0),
    Level("tens", "Make Ten", _pool(tuple((a, 10 - a) for a in range(11))), 3.0),
    Level(
        "bridge",
        "Over the Ten",
        _pool(tuple((a, b) for a in range(1, 10) for b in range(1, 10) if a + b > 10)),
        5.0,
    ),
)

LEVELS_BY_ID = {level.id: level for level in LEVELS}
