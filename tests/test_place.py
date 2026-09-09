"""The placement: where the number goes, and then the fact that secures it.

One play is a placement followed by the answer that confirms it. Neither can be
traded for the other, which is the whole reason the mode exists.
"""

import random
from dataclasses import replace

import pytest

from mathr.domain.round import (
    FOOTBALL,
    RETRY_GAP,
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

SPOT = PLACE_MAX // FOOTBALL.target  # what one part covers, on the line


def drive(level_id="fives", timed=True):
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
    round_ = drive()
    for _ in range(12):
        if round_.over:
            break
        called = round_.placing
        if called is None:  # inside the last spot there is nowhere left to aim
            round_, _ = right(round_)
            continue
        assert called >= round_.parts * SPOT + PLACE_GAIN_MIN or called == PLACE_MAX - 1
        round_, _ = place(round_, called)
        round_, _ = right(round_)



def test_a_target_sits_on_the_line():
    assert 0 <= drive().placing <= PLACE_MAX


def test_a_call_near_the_end_asks_for_no_placement():
    """Within one part of the end there is nowhere ahead to aim, so the last
    stretch has to be covered by answers."""
    close = replace(drive(), parts=FOOTBALL.target - 1)
    assert close.placing is None
    won, outcome = right(close)
    assert outcome is Outcome.WON and won.parts == FOOTBALL.target


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
    round_ = drive()
    called = round_.placing
    taken, _ = thrown(round_)
    after, outcome = right(taken)
    assert outcome is Outcome.SECURED
    assert after.parts == called // SPOT
    assert after.pending is None and after.pending_left is None


def test_exactly_on_the_tolerance_is_good_and_one_past_it_is_not():
    near, outcome = thrown(error=PLACE_TOLERANCE)
    assert outcome is Outcome.PLACED and near.pending is not None
    wide, outcome = thrown(error=-(PLACE_TOLERANCE + 1))
    assert outcome is Outcome.ADRIFT and wide.pending is None


def test_a_wide_placement_costs_no_parts_and_no_time():  # only an attempt
    round_ = drive()
    after, _ = thrown(round_, error=40)
    assert after.parts == round_.parts
    assert after.seconds_left == round_.seconds_left
    assert after.queue == round_.queue


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
    rocket = new_round(LEVELS_BY_ID["fives"], random.Random(0))
    assert rocket.placing is None and rocket.gains == ()
    after, _ = right(rocket)
    assert after.placing is None and after.pending is None


def test_the_offsets_are_deterministic_per_seed():
    assert drive().gains == drive().gains
