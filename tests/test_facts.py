import random

from mathr.domain.facts import LEVELS, LEVELS_BY_ID, Question, shuffled

TIMES = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "×": lambda a, b: a * b}


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
        "everything": 278,
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
    assert {fact.op for fact in LEVELS_BY_ID["everything"].facts} == {"+", "-", "×"}


def test_keys_are_unique_and_stable():
    for level in LEVELS:
        keys = [fact.key for fact in level.facts]
        assert len(keys) == len(set(keys))
    assert LEVELS_BY_ID["fives"].facts[1].key == "0+5=5@b"
    assert LEVELS_BY_ID["twos"].facts[6].key == "2×3=6@result"


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
