import random

import pytest

from mathr.domain.facts import (
    FRACTION_LEVELS,
    LEVELS,
    LEVELS_BY_ID,
    SPAN,
    Question,
    Strategy,
    Target,
    shuffled,
    targets,
)

TIMES = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "×": lambda a, b: a * b,
    "÷": lambda a, b: a // b,
}


def test_every_fact_is_true():
    for level in LEVELS:
        for fact in level.facts:
            assert TIMES[fact.op](fact.a, fact.b) == fact.result, fact.key


def test_answer_is_the_blank_slot():
    for level in LEVELS:
        for fact in level.facts:
            slots = {"a": fact.a, "b": fact.b, "result": fact.result}
            assert fact.answer == slots[fact.blank]


def test_exactly_one_blank_in_either_orientation():
    for level in LEVELS:
        for fact in level.facts:
            for flipped in (False, True):
                question = Question(fact, flipped)
                assert question.prompt.count("?") == 1, question.prompt
                assert question.answer == fact.answer
                assert question.key == fact.key


def test_flipping_moves_the_equals_sign():
    fact = LEVELS_BY_ID["fives"].facts[0]
    assert Question(fact, False).prompt == "0 + 5 = ?"
    assert Question(fact, True).prompt == "? = 0 + 5"


def test_a_deck_carries_both_orientations():
    deck = shuffled(LEVELS_BY_ID["bridge"].facts, random.Random(3))
    assert {question.flipped for question in deck} == {False, True}


def test_pool_sizes():
    assert {level.id: len(level.facts) for level in LEVELS} == {
        "fives": 24,
        "tens": 44,
        "bridge": 144,
        "twos": 22,
        "fives_times": 22,
        "tens_times": 22,
        "divide_two": 20,
        "divide_five": 20,
        "divide_ten": 20,
        "everything": 338,
    }


def test_everything_is_every_other_pool():
    others = [level for level in LEVELS if level.id != "everything"]
    assert LEVELS_BY_ID["everything"].facts == tuple(
        fact for level in others for fact in level.facts
    )


def test_both_blank_forms_in_every_pool():
    for level in LEVELS:
        assert {fact.blank for fact in level.facts} == {"b", "result"}


def test_each_topic_asks_its_own_operations():
    for level_id in ("fives", "tens", "bridge"):
        assert {fact.op for fact in LEVELS_BY_ID[level_id].facts} == {"+", "-"}
    for level_id in ("twos", "fives_times", "tens_times"):
        assert {fact.op for fact in LEVELS_BY_ID[level_id].facts} == {"×"}
    for level_id in ("divide_two", "divide_five", "divide_ten"):
        assert {fact.op for fact in LEVELS_BY_ID[level_id].facts} == {"÷"}
    assert {fact.op for fact in LEVELS_BY_ID["everything"].facts} == {"+", "-", "×", "÷"}


def test_keys_are_unique_and_stable():
    for level in LEVELS:
        keys = [fact.key for fact in level.facts]
        assert len(keys) == len(set(keys))
    assert LEVELS_BY_ID["fives"].facts[1].key == "0+5=5@b"
    assert LEVELS_BY_ID["twos"].facts[6].key == "2×3=6@result"
    assert LEVELS_BY_ID["divide_two"].facts[1].key == "2÷2=1@b"


def test_bridge_facts_cross_ten():
    for fact in LEVELS_BY_ID["bridge"].facts:
        if fact.op == "+":
            assert fact.a < 10 and fact.b < 10 and fact.result > 10
        else:
            assert 10 < fact.a <= 18 and fact.b < 10


def test_times_tables_run_to_ten():
    for level_id, n in (("twos", 2), ("fives_times", 5), ("tens_times", 10)):
        facts = LEVELS_BY_ID[level_id].facts
        assert {fact.a for fact in facts} == {n}
        assert {fact.b for fact in facts} == set(range(11))


# --- the route drawn on a miss ----------------------------------------------

EVERY_FACT = LEVELS_BY_ID["everything"].facts


def test_every_strategy_lands_on_the_answer():
    """Every operation but one draws a route ending on its own answer.

    Division cannot: `12 ÷ 3 = 4` draws four hops of three and lands on *12*,
    because the answer is how many hops there were. Asserted per operation
    rather than universally, so the one that is different says so.
    """
    for fact in EVERY_FACT:
        if fact.op == "÷":
            assert fact.strategy.end == fact.a, fact.key
            assert len(fact.strategy.jumps) == fact.result, fact.key
        else:
            assert fact.strategy.end == fact.result, fact.key


def test_division_hops_count_the_answer():
    """The same picture `2 × 6 = 12` draws, which is the point of drawing it."""
    fact = next(f for f in EVERY_FACT if (f.a, f.op, f.b) == (12, "÷", 2))
    assert fact.strategy == Strategy(0, (2,) * 6)
    assert fact.result == len(fact.strategy.jumps) == 6


def test_no_division_by_nought():
    """`0 ÷ ? = 0` is true of every divisor, so the pair is not askable."""
    for level_id in ("divide_two", "divide_five", "divide_ten"):
        for fact in LEVELS_BY_ID[level_id].facts:
            assert fact.a > 0 and fact.b > 0 and fact.result > 0, fact.key


def test_a_bridging_fact_stops_at_ten():
    for fact in LEVELS_BY_ID["bridge"].facts:
        strategy = fact.strategy
        assert len(strategy.jumps) == 2, fact.key
        assert strategy.start + strategy.jumps[0] == 10, fact.key


def test_a_bond_is_drawn_whole():
    """Make Five and Make Ten are about the pair, so the line starts at nought
    and shows both parts rather than counting on from one of them."""
    assert LEVELS_BY_ID["tens"].facts[0].strategy.jumps == (0, 10)
    fact = next(f for f in LEVELS_BY_ID["fives"].facts if (f.a, f.op) == (3, "+"))
    assert fact.strategy == Strategy(0, (3, 2))


def test_times_facts_are_equal_hops():
    for fact in LEVELS_BY_ID["fives_times"].facts:
        strategy = fact.strategy
        assert strategy.start == 0
        assert strategy.jumps == (fact.a,) * fact.b, fact.key


def test_the_worked_examples():
    def strategy(a, op, b, result):
        return next(
            f.strategy for f in EVERY_FACT if (f.a, f.op, f.b, f.result) == (a, op, b, result)
        )

    assert strategy(8, "+", 6, 14).jumps == (2, 4)
    assert strategy(15, "-", 7, 8).jumps == (-5, -2)
    assert strategy(5, "×", 7, 35).jumps == (5,) * 7


def test_orientation_does_not_change_the_route():
    fact = LEVELS_BY_ID["bridge"].facts[0]
    assert Question(fact, True).strategy == Question(fact, False).strategy == fact.strategy


def test_fraction_pool_sizes():
    assert {level.id: len(level.targets) for level in FRACTION_LEVELS} == {
        "halves": 4,
        "thirds": 7,
        "fifths": 13,
        "eighths": 18,
        "same_as": 14,
        "fractions": 56,
    }


def test_every_fraction_pool_is_derived_from_the_others():
    families = [level for level in FRACTION_LEVELS if level.id != "fractions"]
    assert LEVELS_BY_ID["fractions"].targets == tuple(
        target for level in families for target in level.targets
    )


def test_a_fraction_level_has_no_facts_and_a_fact_level_has_no_targets():
    for level in FRACTION_LEVELS:
        assert level.facts == ()
    for level in LEVELS:
        assert level.targets == ()


def test_every_target_has_a_tick_to_land_on():
    for level in FRACTION_LEVELS:
        for target in level.targets:
            assert target.ticks % target.den == 0, target.key
            assert 0 < target.num < target.den, target.key


def test_no_target_is_an_end_of_the_line():
    """0/b and b/b are labelled already, so they measure nothing."""
    for level in FRACTION_LEVELS:
        for target in level.targets:
            assert 0 < target.value < SPAN


def test_the_span_keeps_every_tolerance_whole():
    """The check that chose 240 over 120. Re-run it before adding a level."""
    denominators = {target.ticks for level in FRACTION_LEVELS for target in level.targets}
    assert not [d for d in denominators if SPAN % d or (SPAN // d) % 2]
    for level in FRACTION_LEVELS:
        for target in level.targets:
            assert target.tolerance * 2 * target.ticks == SPAN


def test_a_route_is_hops_of_one_tick_and_lands_on_the_fraction():
    for level in FRACTION_LEVELS:
        for target in level.targets:
            route = target.strategy
            assert len(route.jumps) == target.num
            # In tick units: the route ends on the mark, and the mark scaled by
            # the tick gap is the value on the span.
            assert route.end * (SPAN // target.ticks) == target.value


def test_equivalence_says_the_same_place_in_a_different_partition():
    thirds = Target(1, 3, 3)
    sixths = Target(1, 3, 6)
    assert thirds.value == sixths.value
    assert thirds.key != sixths.key  # different questions, different rows
    assert sixths.strategy == Strategy(0, (2,))


def test_a_target_deck_is_the_whole_pool_and_replays_by_seed():
    pool = LEVELS_BY_ID["thirds"].targets
    deck = targets(pool, random.Random(4))
    assert sorted(deck, key=lambda t: t.key) == sorted(pool, key=lambda t: t.key)
    assert deck == targets(pool, random.Random(4))


def test_a_target_has_no_answer_to_type():
    """Anything reaching for one is a keypad path that must raise, not compare."""
    with pytest.raises(AttributeError):
        _ = Target(1, 2, 2).answer
