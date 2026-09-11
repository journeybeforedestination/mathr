"""The lines a code panel is built from, and the pools they come out of."""

import random

from mathr.domain.facts import LEVELS, LEVELS_BY_ID, Sentence, Side, Strategy, sentences

EVERY = tuple(
    line
    for level in LEVELS
    for line in sentences(level.facts, random.Random(len(level.id)))
)


def test_a_side_knows_its_own_value():
    assert Side(8).value == 8
    assert Side(7, "+", 6).value == 13
    assert Side(12, "÷", 2).value == 6


def test_a_side_borrows_the_route_a_fact_would_draw():
    """One picture for `7 + 6`, whichever cabinet is asking."""
    assert Side(8, "+", 6).strategy == Strategy(8, (2, 4))
    assert Side(12, "÷", 2).strategy.jumps == (2,) * 6


def test_the_two_sides_always_agree():
    """A line holds its true numbers; `prompt` is the only thing that hides one.
    So there is nothing stored that could disagree with what he is reading."""
    for line in EVERY:
        assert line.left.value == line.right.value, line.filled


def test_the_answer_is_the_number_that_is_missing():
    for line in EVERY:
        assert getattr(line.right, line.slot) == line.answer, line.filled


def test_exactly_one_number_is_hidden():
    for line in EVERY:
        assert line.prompt.count("?") == 1, line.prompt
        assert "?" not in line.filled, line.filled


def test_every_side_is_a_number():
    """No divisor of nought, no division that stops being whole, no subtraction
    below zero — the sides come from real facts, and this pins that they do."""
    for line in EVERY:
        for side in (line.left, line.right):
            assert side.value >= 0, line.filled
            if side.op == "÷":
                assert side.b > 0 and side.a % side.b == 0, line.filled


#: The divisions of one table, on their own: a table's card holds its times
#: facts too, and this shape needs a pool that can build nothing else.
_DIVISIONS = tuple(fact for fact in LEVELS_BY_ID["table_2"].facts if fact.op == "÷")


def test_a_decomposition_never_splits_off_nought():
    """`18 ÷ 2 = 0 + ?` is not a decomposition, it is the bare fact with a
    nought stuck on the front of it."""
    # Only the decomposition shape is pinned: a pool expression may legitimately
    # hold a nought (`10 - 0` is a real fact), and a division level can build
    # nothing but decompositions, so its deck isolates the shape.
    made = [
        line
        for line in sentences(_DIVISIONS, random.Random(3), 60)
        if line.right.op == "+"
    ]
    assert made
    for line in made:
        assert line.right.a >= 1 and line.right.b >= 1, line.filled


def test_keys_are_the_filled_line():
    good = Sentence(Side(7, "+", 6), Side(8, "+", 5), "right.a", 8)
    assert good.key == "7+6=8+5@right.a"
    assert good.prompt == "7 + 6 = ? + 5"
    assert good.filled == "7 + 6 = 8 + 5"


def test_a_line_key_cannot_collide_with_a_fact_key():
    fact_keys = {fact.key for level in LEVELS for fact in level.facts}
    assert not fact_keys & {line.key for line in EVERY}


def test_a_deck_never_repeats_itself():
    for level in LEVELS:
        deck = sentences(level.facts, random.Random(4))
        assert len({line.prompt for line in deck}) == len(deck), level.id


def test_every_level_can_fill_a_deck():
    """Including the thin ones. A division level has no two expressions sharing
    a value and nothing to commute, so it leans entirely on decomposition —
    which is why that shape exists."""
    for level in LEVELS:
        assert len(sentences(level.facts, random.Random(2))) == 40, level.id


def test_a_seed_replays_a_deck_exactly():
    facts = LEVELS_BY_ID["everything"].facts
    assert sentences(facts, random.Random(9)) == sentences(facts, random.Random(9))
    assert sentences(facts, random.Random(9)) != sentences(facts, random.Random(10))


def test_most_lines_are_relational():
    """`7 + 6 = ?` is the question the other three cabinets already ask. It is
    the fallback, not the mode."""
    for level in LEVELS:
        deck = sentences(level.facts, random.Random(5))
        bare = sum(1 for line in deck if line.right.op is None)
        assert bare < len(deck) // 3, (level.id, bare)


def test_both_sides_lines_reach_the_addition_pools():
    """The purest shape: two expressions, and neither can be read off without
    the relation between them."""
    deck = sentences(LEVELS_BY_ID["small"].facts, random.Random(1))
    assert any(line.left.op is not None and line.right.op != "+" for line in deck)
