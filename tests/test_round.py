import random
from dataclasses import replace

import pytest

from mathr.domain.facts import LEVELS_BY_ID
from mathr.domain.round import PARTS_TO_LAUNCH, RETRY_GAP, Outcome, Tally, apply, new_round


@pytest.fixture
def round_():
    return new_round(LEVELS_BY_ID["fives"], random.Random(0))


def answer(round_, correct=True):
    return apply(round_, round_.current.answer if correct else round_.current.answer + 1)


def test_correct_adds_a_part(round_):
    after, outcome = answer(round_)
    assert (after.parts, outcome) == (1, Outcome.CORRECT)
    assert after.asked == 1 and after.missed == 0


def test_wrong_at_zero_parts_stays_at_zero(round_):
    after, outcome = answer(round_, correct=False)
    assert (after.parts, outcome) == (0, Outcome.WRONG)
    assert after.missed == 1


def test_wrong_removes_a_part(round_):
    after, _ = answer(round_)
    after, outcome = answer(after, correct=False)
    assert (after.parts, outcome) == (0, Outcome.WRONG)


def test_missed_fact_is_reasked(round_):
    missed = round_.current
    after, _ = answer(round_, correct=False)
    assert after.queue[RETRY_GAP] == missed
    assert missed not in after.queue[:RETRY_GAP]


def test_missed_fact_survives_a_short_queue(round_):
    short = replace(round_, queue=round_.queue[:1], deck=round_.queue[:1])
    after, _ = answer(short, correct=False)
    assert short.current in after.queue


def test_launch_after_ten_correct(round_):
    current = round_
    for _ in range(PARTS_TO_LAUNCH - 1):
        current, outcome = answer(current)
        assert outcome is Outcome.CORRECT
    current, outcome = answer(current)
    assert outcome is Outcome.LAUNCHED
    assert current.launched and current.parts == PARTS_TO_LAUNCH


def test_answers_after_launch_are_rejected(round_):
    current = round_
    for _ in range(PARTS_TO_LAUNCH):
        current, _ = answer(current)
    after, outcome = apply(current, 999)
    assert after is current and outcome is Outcome.LAUNCHED


def test_attempts_accumulate_for_right_and_wrong(round_):
    key = round_.current.key
    after, _ = answer(round_, correct=False)
    while after.current.key != key:
        after, _ = answer(after)
    after, _ = answer(after)
    assert (after.attempts[key].right, after.attempts[key].wrong) == (1, 1)
    assert after.attempts[key].answered == 2


def test_queue_never_empties(round_):
    current = round_
    for _ in range(500):
        current, _ = apply(current, current.current.answer if not current.launched else 0)
        assert current.queue


def test_shuffle_is_deterministic_per_seed():
    a = new_round(LEVELS_BY_ID["tens"], random.Random(7))
    b = new_round(LEVELS_BY_ID["tens"], random.Random(7))
    assert a.deck == b.deck
