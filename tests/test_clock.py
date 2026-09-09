"""The time bank: a shared pool, not a stopwatch per problem."""

import random

import pytest

from mathr.domain.facts import LEVELS, LEVELS_BY_ID
from mathr.domain.round import (
    BALL_FLIGHT,
    BANK_PARTS,
    GRACE_PARTS,
    PARTS_TO_LAUNCH,
    RETRY_GAP,
    ROCKET,
    TENNIS,
    Outcome,
    apply,
    dismiss,
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


def test_start_and_cap_derive_from_the_level_under_either_rule_set():
    """The derivation, never the literals: retuning a level must not break this."""
    for rules in (ROCKET, TENNIS):
        for level in LEVELS:
            round_ = new_round(level, random.Random(0), rules=rules)
            assert round_.seconds_left == rules.opening_parts * level.seconds_per_part
            assert round_.cap == rules.bank_parts * level.seconds_per_part


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
    assert outcome is Outcome.LOST
    assert round_.failed and round_.seconds_left == 0.0
    assert not round_.launched


def test_answers_after_an_abduction_are_rejected():
    dead, _ = tick(started(), 99.0)
    after, outcome = right(dead)
    assert after is dead and outcome is Outcome.LOST


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
    assert outcome is Outcome.WON and not round_.failed


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


# --- the rally deadline -----------------------------------------------------


def rally(level_id="tens"):
    return new_round(LEVELS_BY_ID[level_id], random.Random(0), rules=TENNIS)


def test_a_rally_opens_at_its_own_cap():
    round_ = rally()
    assert round_.seconds_left == round_.cap == BALL_FLIGHT * round_.seconds_per_part


def test_a_return_refills_the_rally_rather_than_topping_it_up():
    round_, _ = tick(rally(), 4.0)
    after, outcome = right(round_)
    assert outcome is Outcome.CORRECT
    assert after.seconds_left == after.cap


def test_the_reset_never_shortens_a_rally():
    fresh = rally()
    after, _ = right(fresh)
    assert after.seconds_left == pytest.approx(fresh.seconds_left)


def test_a_ball_that_gets_past_him_scores_a_point_and_serves_again():
    round_ = rally()
    missed = round_.current
    after, outcome = tick(round_, 99.0)
    assert outcome is Outcome.POINT
    assert after.points == 1 and not after.failed
    assert after.seconds_left == after.cap and after.on_current == 0.0
    assert after.queue[RETRY_GAP] == missed
    assert after.current != missed


def test_three_points_lose_the_match():
    round_ = rally()
    for expected in (Outcome.POINT, Outcome.POINT, Outcome.LOST):
        # Each lost ball leaves a hint up, and the clock stays stopped until it
        # is dismissed — which is what the next keystroke does in the game.
        round_, outcome = tick(dismiss(round_), 99.0)
        assert outcome is expected
    assert round_.failed and round_.points == 3 and not round_.launched


def test_a_wrong_answer_leaves_the_ball_in_the_air():
    round_, _ = tick(rally(), 2.0)
    after, outcome = wrong(round_)
    assert outcome is Outcome.WRONG
    assert after.current == round_.current and after.queue == round_.queue
    assert after.seconds_left == round_.seconds_left
    assert after.parts == round_.parts
    assert after.missed == 1


def test_a_round_with_lives_cannot_be_untimed():
    with pytest.raises(ValueError):
        new_round(LEVELS_BY_ID["tens"], random.Random(0), timed=False, rules=TENNIS)


# --- the hint stops every clock ---------------------------------------------


def test_no_clock_runs_while_a_hint_shows():
    round_, _ = tick(started(), 2.0)
    missed, _ = wrong(round_)
    assert missed.hint is not None
    after, outcome = tick(missed, 10.0)
    assert outcome is None
    assert after.seconds_left == missed.seconds_left
    assert after.on_current == missed.on_current == 0.0
    assert after.elapsed == missed.elapsed


def test_dismissing_starts_them_again():
    missed, _ = wrong(started())
    resumed = dismiss(missed)
    assert resumed.hint is None
    after, _ = tick(resumed, 2.0)
    assert after.seconds_left == pytest.approx(missed.seconds_left - 2.0)
    assert after.on_current == pytest.approx(2.0)


def test_hint_reading_time_never_reaches_the_record():
    """The weighted deck reads Tally.seconds; time spent reading a hint about a
    fact would push that fact to the front of the next deck, hint and all."""
    round_, _ = tick(started(), 1.0)
    missed, _ = wrong(round_)
    stared, _ = tick(missed, 30.0)
    key = stared.current.key
    answered, _ = right(dismiss(stared))
    assert answered.attempts[key].seconds == pytest.approx(0.0)


def test_a_correct_answer_clears_the_hint():
    missed, _ = wrong(started())
    after, _ = right(dismiss(missed))
    assert after.hint is None


def test_a_ball_that_gets_past_him_explains_the_fact_he_never_answered():
    round_ = rally()
    missed = round_.current
    after, _ = tick(round_, 99.0)
    assert after.hint == missed


def test_a_wrong_answer_in_tennis_explains_without_touching_the_queue():
    after, _ = wrong(rally())
    assert after.hint == after.current


def test_an_abduction_leaves_no_hint():
    """The failure screen owns the display, and its animation runs on the clock
    a hint would stop."""
    dead, outcome = tick(started(), 99.0)
    assert outcome is Outcome.LOST and dead.hint is None
