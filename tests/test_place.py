"""The placement: where the number goes, and then the fact that secures it.

One play is a placement followed by the answer that confirms it. Neither can be
traded for the other, which is the whole reason the mode exists.
"""

import random
from dataclasses import replace

import pytest

from mathr.domain.round import (
    FOOTBALL,
    PLACE_PENALTY,
    RETRY_GAP,
    SACK_BY,
    PLACE_GAIN_MIN,
    PLACE_LIVES,
    PLACE_MAX,
    PLACE_TOLERANCE,
    Outcome,
    apply,
    dismiss,
    new_round,
    place,
    tick,
)
from mathr.domain.facts import LEVELS_BY_ID

# The marker is the line: `FOOTBALL.target` is `PLACE_MAX`, so `parts` is a
# position on it and a catch on the 27 spots the ball on the 27.


def drive(level_id="small", timed=True):
    return new_round(
        LEVELS_BY_ID[level_id],
        random.Random(0),
        timed=timed,
        rules=FOOTBALL,
        mode_id="football",
    )


def right(round_):
    return apply(round_, round_.current.answer)


def wrong(round_):
    return apply(round_, round_.current.answer + 1)


def thrown(round_=None, error: int = 0):
    """A drive with a placement taken `error` yards off the called one."""
    round_ = round_ or drive()
    return place(round_, round_.placing + error)


# --- the cycle ---------------------------------------------------------------


def test_a_placement_is_due_before_the_first_question():
    """The placement comes first: the answer is what confirms it."""
    assert drive().placing is not None


def test_the_cycle_alternates_placement_and_answer():
    round_, _ = thrown()
    assert round_.placing is None and round_.pending is not None
    round_, outcome = right(round_)
    assert outcome is Outcome.SECURED
    assert round_.placing is not None


def test_a_wide_placement_comes_straight_back_from_the_same_spot():
    round_ = drive()
    after, outcome = thrown(round_, error=PLACE_TOLERANCE + 20)
    assert outcome is Outcome.ADRIFT
    assert after.pending is None
    assert after.parts == round_.parts  # nothing advanced
    assert after.current == round_.current  # and no question went by
    assert after.placing is not None


def test_a_new_call_comes_with_each_attempt():
    """From the same spot, but not the same number: an attempt he can repeat by
    muscle memory is not a second estimate."""
    round_ = drive()
    first = round_.placing
    after, _ = thrown(round_, error=PLACE_TOLERANCE + 20)
    assert after.placing != first


def test_three_wide_placements_are_a_turnover():
    round_ = drive()
    for expected in [Outcome.ADRIFT] * (PLACE_LIVES - 1) + [Outcome.LOST]:
        round_, outcome = thrown(round_, error=PLACE_TOLERANCE + 20)
        assert outcome is expected
    assert round_.failed and round_.adrift == PLACE_LIVES
    assert not round_.launched and round_.placing is None


def test_a_good_placement_costs_no_attempt():
    taken, _ = thrown()
    assert taken.adrift == 0
    secured, _ = right(taken)
    wide, _ = thrown(secured, error=PLACE_TOLERANCE + 1)
    assert wide.adrift == 1


def test_every_call_is_ahead_of_the_marker():
    """A target behind the marker plays as a pass thrown backwards: the
    mechanic works and the metaphor around it is a lie."""
    # Sacks are the one call behind him, and one is overdue past halfway.
    round_ = replace(drive(), sacks=(8,), sack_at=(False,), sacks_taken=1)
    for _ in range(12):
        if round_.over:
            break
        called = round_.placing
        assert called >= round_.parts + PLACE_GAIN_MIN or called >= PLACE_MAX - 1
        round_, _ = place(round_, called)
        round_, _ = right(round_)



def test_a_target_sits_on_the_line():
    assert 0 <= drive().placing <= PLACE_MAX


def test_the_last_call_is_the_end_zone():
    """Close in there is no honest target left ahead of him, so the call is the
    end of the line itself — the one easy placement, and the one that wins."""
    close = replace(drive(), parts=PLACE_MAX - PLACE_GAIN_MIN, sacks_taken=1)
    assert close.placing == PLACE_MAX
    taken, outcome = place(close, PLACE_MAX)
    assert outcome is Outcome.PLACED
    won, outcome = right(taken)
    assert outcome is Outcome.WON and won.parts == PLACE_MAX


def test_placing_twice_over_raises():
    taken, _ = thrown()
    with pytest.raises(ValueError):
        place(taken, 50)


# --- the placement, and the answer that secures it ---------------------------


def test_a_good_placement_moves_nothing_on_its_own():
    round_ = drive()
    taken, outcome = thrown(round_)
    assert outcome is Outcome.PLACED
    assert taken.parts == round_.parts
    assert taken.pending == round_.placing


def test_the_confirming_answer_moves_the_marker_to_where_it_was_called():
    """Exactly there — a catch on the 27 is the ball on the 27. Rounding it down
    to the nearest ten makes the number he estimated not the number he gets."""
    round_ = drive()
    called = round_.placing
    taken, _ = thrown(round_)
    after, outcome = right(taken)
    assert outcome is Outcome.SECURED
    assert after.parts == called
    assert after.pending is None and after.pending_left is None


def test_exactly_on_the_tolerance_is_good_and_one_past_it_is_not():
    near, outcome = thrown(error=PLACE_TOLERANCE)
    assert outcome is Outcome.PLACED and near.pending is not None
    wide, outcome = thrown(error=-(PLACE_TOLERANCE + 1))
    assert outcome is Outcome.ADRIFT and wide.pending is None


def test_a_wide_throw_gives_up_ground_as_well_as_an_attempt():
    """Holding on the play. Without it a miss at the top of the field costs
    nothing he can see, and clicking until one sticks is the cheapest drive."""
    round_ = replace(drive(), parts=40, sacks_taken=1)
    after, _ = thrown(round_, error=40)
    assert after.parts == 40 - PLACE_PENALTY
    assert after.seconds_left == round_.seconds_left
    assert after.queue == round_.queue


def test_the_penalty_cannot_push_the_marker_off_the_line():
    round_ = replace(drive(), parts=4)
    after, _ = thrown(round_, error=40)
    assert after.parts == 0


def test_a_missed_sack_spot_is_not_penalised_twice():
    """The play has already taken its ground; the spot being wrong costs the
    attempt and nothing more."""
    round_ = sack(loss=8, parts=40)
    after, _ = place(round_, round_.placing + 30)
    assert after.parts == 32


def test_the_distance_is_recorded_by_decade_bucket():
    round_ = drive()
    called = round_.placing
    after, _ = thrown(round_, error=-3)
    aim = after.aims[str(called // 10 * 10)]
    assert (aim.attempts, aim.error) == (1, 3.0)


# --- the clock on a placement ------------------------------------------------


def test_no_clock_runs_while_a_placement_is_being_taken():
    round_ = drive()
    after, outcome = tick(round_, 10.0)
    assert outcome is None
    assert after.seconds_left == round_.seconds_left
    assert after.on_current == round_.on_current
    assert after.elapsed == round_.elapsed


def test_aiming_time_never_reaches_the_record():
    """`Tally.seconds` feeds the deck weighting; seconds spent aiming are not
    seconds spent on the question underneath."""
    round_ = drive()
    key = round_.current.key
    stared, _ = tick(round_, 30.0)
    taken, _ = thrown(stared)
    after, _ = right(taken)
    assert after.attempts[key].seconds == pytest.approx(0.0)


def test_the_pending_placement_drains_and_then_lapses():
    taken, _ = thrown()
    assert taken.pending_left == pytest.approx(taken.confirm_seconds)
    ticking, outcome = tick(taken, taken.pending_left - 0.1)
    assert outcome is None and ticking.pending is not None
    dropped, outcome = tick(ticking, 0.2)
    assert outcome is Outcome.LAPSED
    assert dropped.pending is None and dropped.pending_left is None
    assert dropped.parts == taken.parts  # it came to nothing
    assert dropped.placing is not None  # and the next call is another attempt


def test_a_dropped_ball_takes_its_question_with_it():
    """The next catch is confirmed by a fresh fact: the one that got away comes
    back later in the deck, and a half-typed answer to it has nothing to land on."""
    taken, _ = thrown()
    missed = taken.current
    dropped, _ = tick(taken, taken.pending_left + 0.1)
    assert dropped.current != missed
    assert dropped.queue[RETRY_GAP] == missed
    assert dropped.on_current == 0.0


def test_a_lapse_leaves_no_hint():
    """Every other way of running out of time explains itself with the number
    line. This one cannot: the next thing it asks for is a click on the field,
    and a click that dismissed a hint would also be a throw."""
    taken, _ = thrown()
    dropped, _ = tick(taken, taken.pending_left + 0.1)
    assert dropped.hint is None


def test_the_bank_still_drains_while_a_placement_is_pending():
    taken, _ = thrown()
    after, _ = tick(taken, 0.5)
    assert after.seconds_left == pytest.approx(taken.seconds_left - 0.5)


def test_losing_the_round_outranks_losing_the_placement():
    taken, _ = thrown()
    dead, outcome = tick(taken, 999.0)
    assert outcome is Outcome.LOST and dead.failed
    # And it takes the placement with it: the failure screen is not the place to
    # go on drawing a ball nobody can catch.
    assert dead.pending is None and dead.pending_left is None


def test_a_wrong_answer_costs_nothing_and_leaves_the_placement_in_the_air():
    taken, _ = thrown()
    after, outcome = wrong(taken)
    assert outcome is Outcome.WRONG
    assert after.pending == taken.pending
    assert after.parts == taken.parts
    assert after.current == taken.current and after.queue == taken.queue


def test_a_hint_freezes_the_placement_with_everything_else():
    """He reads the number line with the placement held exactly where it was —
    the same bargain a rally makes."""
    taken, _ = thrown()
    missed, _ = wrong(taken)
    assert missed.hint is not None
    after, outcome = tick(missed, 30.0)
    assert outcome is None
    assert after.pending_left == missed.pending_left
    resumed, _ = tick(dismiss(missed), 0.25)
    assert resumed.pending_left == pytest.approx(missed.pending_left - 0.25)


def test_an_untimed_drive_places_but_never_lapses():
    round_ = drive(timed=False)
    assert round_.placing is not None
    taken, _ = thrown(round_)
    assert taken.pending is not None and taken.pending_left is None
    after, outcome = tick(taken, 600.0)
    assert outcome is None and after.pending == taken.pending


# --- other modes are untouched -----------------------------------------------


def test_a_mode_without_placements_never_asks_for_one():
    rocket = new_round(LEVELS_BY_ID["small"], random.Random(0))
    assert rocket.placing is None and rocket.gains == ()
    after, _ = right(rocket)
    assert after.placing is None and after.pending is None


def test_the_offsets_are_deterministic_per_seed():
    assert drive().gains == drive().gains


# --- sacks -------------------------------------------------------------------


def sack(loss: int = 8, parts: int = 40):
    """A drive on the `parts`, with the next play losing `loss` yards."""
    return replace(drive(), parts=parts, sacks=(loss,), sack_at=(True,))


def no_sack(parts: int = 40):
    """A drive on the `parts` whose draw holds no sack at all."""
    return replace(drive(), parts=parts, sacks=(8,), sack_at=(False,))


def test_a_sack_asks_for_the_spot_it_leaves_him_on():
    """Told what it cost, not where it puts him: the target is a subtraction
    modelled on the line, which is the one placement he cannot read off."""
    round_ = sack(loss=8, parts=40)
    assert round_.sacked == 8
    assert round_.placing == 32


def test_placing_a_sack_moves_the_marker_back_and_asks_nothing_else():
    round_ = sack()
    after, outcome = place(round_, round_.placing)
    assert outcome is Outcome.SETBACK
    assert after.parts == round_.placing
    assert after.pending is None  # no pass to catch: the play is over
    assert after.placing is not None  # and the next call comes straight away


def test_a_sack_lands_where_it_lands_however_it_is_placed():
    """Spotting it at his click would make a sack the cheapest way up the field:
    a few yards forward of the truth, every time, inside the tolerance."""
    round_ = sack()
    near, _ = place(round_, round_.placing + PLACE_TOLERANCE)
    wide, outcome = place(round_, round_.placing + PLACE_TOLERANCE + 20)
    assert near.parts == wide.parts == round_.placing
    assert outcome is Outcome.ADRIFT


def test_a_badly_placed_sack_costs_an_attempt_like_any_other():
    round_ = sack()
    after, _ = place(round_, round_.placing + 30)
    assert after.adrift == 1


def test_a_sack_records_nothing_in_the_aims():
    """`aims` is how far off he is when he is *shown* a number. An error here is
    as much the subtraction as the line, and would read as estimation drift."""
    round_ = sack()
    after, _ = place(round_, round_.placing + 20)
    assert after.aims == {}


def test_there_is_no_sack_with_nothing_to_lose():
    round_ = sack(loss=12, parts=9)
    assert round_.sacked is None
    assert round_.placing > round_.parts  # an ordinary call, ahead of him


def test_sacks_are_deterministic_per_seed():
    assert (drive().sacks, drive().sack_at) == (drive().sacks, drive().sack_at)
    assert any(drive().sack_at) and not all(drive().sack_at)


def test_crossing_halfway_untouched_brings_one_on():
    """Three long catches can otherwise walk the line without the marker ever
    going backwards, which is the run of play there is least to learn in."""
    assert no_sack(parts=SACK_BY).sacked is None
    assert no_sack(parts=SACK_BY + 1).sacked == 8


def test_the_overdue_sack_comes_only_once():
    round_ = no_sack(parts=SACK_BY + 1)
    after, _ = place(round_, round_.placing)
    assert after.sacks_taken == 1
    assert after.sacked is None  # the draw is back in charge


def test_a_sack_that_was_drawn_counts_as_the_one():
    taken, _ = place(sack(parts=30), sack(parts=30).placing)
    assert taken.sacks_taken == 1
    assert replace(taken, parts=SACK_BY + 1, sack_at=(False,)).sacked is None
