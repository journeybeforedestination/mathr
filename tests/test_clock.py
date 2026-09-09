"""The time bank: a shared pool, not a stopwatch per problem."""

import random

import pytest

from mathr.domain.facts import LEVELS, LEVELS_BY_ID
from mathr.domain.round import (
    BANK_PARTS,
    GRACE_PARTS,
    PARTS_TO_LAUNCH,
    Outcome,
    apply,
    new_round,
    tick,
)


def started(level_id="fives", timed=True):
    return new_round(LEVELS_BY_ID[level_id], random.Random(0), timed=timed)


def right(round_):
    return apply(round_, round_.current.answer)


def wrong(round_):
    return apply(round_, round_.current.answer + 1)


def test_the_round_opens_with_grace_above_the_cap():
    round_ = started()
    assert round_.seconds_left == GRACE_PARTS * round_.seconds_per_part
    assert round_.seconds_left > round_.cap


def test_start_and_cap_scale_with_the_level():
    fives, bridge = started("fives"), started("bridge")
    assert (fives.seconds_left, fives.cap) == (15.0, 12.0)
    assert (bridge.seconds_left, bridge.cap) == (25.0, 20.0)
    for level in LEVELS:
        round_ = started(level.id)
        assert round_.seconds_left == GRACE_PARTS * level.seconds_per_part
        assert round_.cap == BANK_PARTS * level.seconds_per_part


def test_the_bank_drains_in_real_time():
    round_, outcome = tick(started(), 2.0)
    assert round_.seconds_left == pytest.approx(13.0)
    assert outcome is None


def test_a_correct_answer_credits_one_part_of_time():
    round_, _ = tick(started(), 6.0)  # 9.0 left, below the 12s cap
    after, _ = right(round_)
    assert after.seconds_left == pytest.approx(12.0)


def test_credit_never_exceeds_the_cap():
    round_, _ = tick(started(), 5.0)  # 10.0 left
    after, _ = right(round_)
    assert after.seconds_left == pytest.approx(after.cap)


def test_credit_never_pushes_the_bank_down_during_grace():
    round_, _ = tick(started(), 1.0)  # 14.0 left, still above the cap
    after, _ = right(round_)
    assert after.seconds_left == pytest.approx(14.0)


def test_a_wrong_answer_costs_a_part_but_no_extra_time():
    round_, _ = tick(started(), 6.0)
    after, outcome = wrong(round_)
    assert outcome is Outcome.WRONG
    assert after.seconds_left == pytest.approx(round_.seconds_left)


def test_the_bank_empties_into_an_abduction():
    round_, outcome = tick(started(), 15.0)
    assert outcome is Outcome.ABDUCTED
    assert round_.failed and round_.seconds_left == 0.0
    assert not round_.launched


def test_answers_after_an_abduction_are_rejected():
    dead, _ = tick(started(), 99.0)
    after, outcome = right(dead)
    assert after is dead and outcome is Outcome.ABDUCTED


def test_the_clock_stops_once_the_round_is_over():
    dead, _ = tick(started(), 99.0)
    after, outcome = tick(dead, 5.0)
    assert after is dead and outcome is None


def test_three_seconds_a_part_is_the_sustainable_pace():
    """Ten answers at exactly the per-part pace survives; any slower does not."""
    round_ = started()
    for _ in range(PARTS_TO_LAUNCH):
        round_, outcome = tick(round_, round_.seconds_per_part)
        assert outcome is None
        round_, outcome = right(round_)
    assert outcome is Outcome.LAUNCHED and not round_.failed


def test_a_slow_problem_is_paid_for_by_a_fast_one():
    round_ = started()
    round_, _ = tick(round_, 8.0)  # one long stall
    round_, _ = right(round_)
    for _ in range(6):
        round_, _ = tick(round_, 0.5)  # then a fast streak
        round_, _ = right(round_)
    assert round_.seconds_left > 8.0


def test_an_untimed_round_has_no_bank_and_never_fails():
    round_ = started(timed=False)
    assert round_.seconds_left is None and not round_.timed
    round_, outcome = tick(round_, 600.0)
    assert outcome is None and not round_.failed
    after, _ = right(round_)
    assert after.seconds_left is None


def test_response_time_is_recorded_per_fact_even_untimed():
    round_ = started(timed=False)
    key = round_.current.key
    round_, _ = tick(round_, 4.0)
    after, _ = right(round_)
    assert after.attempts[key].seconds == pytest.approx(4.0)
    assert after.on_current == 0.0


def test_the_next_question_starts_from_zero():
    round_, _ = tick(started(), 3.0)
    round_, _ = right(round_)
    round_, _ = tick(round_, 1.0)
    second = round_.current.key
    after, _ = right(round_)
    assert after.attempts[second].seconds == pytest.approx(1.0)


def test_elapsed_tracks_the_whole_round():
    round_ = started()
    for _ in range(4):
        round_, _ = tick(round_, 1.5)
        round_, _ = right(round_)
    assert round_.elapsed == pytest.approx(6.0)
