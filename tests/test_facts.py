from mathr.domain.facts import LEVELS, LEVELS_BY_ID


def test_every_fact_is_true():
    for level in LEVELS:
        for fact in level.facts:
            expected = fact.a + fact.b if fact.op == "+" else fact.a - fact.b
            assert expected == fact.result, fact.key


def test_answer_is_the_blank_slot():
    for level in LEVELS:
        for fact in level.facts:
            slots = {"a": fact.a, "b": fact.b, "result": fact.result}
            assert fact.answer == slots[fact.blank]
            assert fact.prompt.count("?") == 1


def test_pool_sizes():
    assert {level.id: len(level.facts) for level in LEVELS} == {
        "fives": 24,
        "tens": 44,
        "bridge": 144,
    }


def test_both_blank_forms_in_every_pool():
    for level in LEVELS:
        blanks = {fact.blank for fact in level.facts}
        assert blanks == {"b", "result"}
        assert {fact.op for fact in level.facts} == {"+", "-"}


def test_keys_are_unique_and_stable():
    for level in LEVELS:
        keys = [fact.key for fact in level.facts]
        assert len(keys) == len(set(keys))
    assert LEVELS_BY_ID["fives"].facts[1].key == "0+5=5@b"


def test_bridge_facts_cross_ten():
    for fact in LEVELS_BY_ID["bridge"].facts:
        if fact.op == "+":
            assert fact.a < 10 and fact.b < 10 and fact.result > 10
        else:
            assert 10 < fact.a <= 18 and fact.b < 10
