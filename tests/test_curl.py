"""The stone: a fraction placed on a line ticked into equal parts.

The mode with no keypad in it, so `place` is the only reducer a round goes
through — and therefore the one that has to advance the queue, write the tally
and credit the part.
"""

import random

import pytest

from mathr.domain.facts import LEVELS_BY_ID, SPAN, WIDEST, Target
from mathr.domain.round import (
    CURLING,
    ROCKET,
    STONES,
    STONE_LIVES,
    Outcome,
    Tally,
    new_round,
    place,
    tick,
)


def end(level_id="thirds"):
    return new_round(
        LEVELS_BY_ID[level_id],
        random.Random(0),
        timed=False,
        rules=CURLING,
        mode_id="curling",
    )


def throw(round, off_by=0):
    """One stone, off the true mark by `off_by` span units."""
    return place(round, round.current.value + off_by)


def test_the_call_is_the_question_not_a_walk_up_the_line():
    round = end()
    assert round.placing == round.current.value
    after, _ = throw(round)
    # The next call is the next item's, never an offset from where the last
    # stone landed: the level chooses what is asked, not the throws before it.
    assert after.placing == after.current.value
    assert after.current != round.current


def test_a_stone_in_the_house_scores_and_moves_on():
    round = end()
    asked = round.current
    after, outcome = throw(round, off_by=asked.tolerance)
    assert outcome is Outcome.PLACED
    assert after.parts == 1
    assert after.current is not asked
    assert after.attempts[asked.key] == Tally(right=1, wrong=0, answered=1, seconds=0.0)


def test_a_wide_stone_moves_on_too_and_scores_nothing():
    round = end()
    asked = round.current
    after, outcome = throw(round, off_by=asked.tolerance + 1)
    assert outcome is Outcome.ADRIFT
    assert after.parts == 0
    assert after.adrift == 1
    assert after.current is not asked
    assert after.attempts[asked.key].wrong == 1


def test_a_wide_stone_is_never_re_queued():
    """He has just been shown the true mark; re-asking is reproduction, not
    retrieval — and an end that fills with the one he missed reads as a broken
    shuffle."""
    round = end("fifths")
    asked = round.current
    after, _ = throw(round, off_by=asked.tolerance + 1)
    assert after.queue == round.queue[1:]


def test_three_wide_stones_end_it():
    round = end()
    for _ in range(STONE_LIVES - 1):
        round, outcome = throw(round, off_by=round.current.tolerance + 1)
        assert outcome is Outcome.ADRIFT
    round, outcome = throw(round, off_by=round.current.tolerance + 1)
    assert outcome is Outcome.LOST
    assert round.failed and round.over


def test_eight_in_the_house_win_the_end():
    round = end()
    for _ in range(STONES - 1):
        round, outcome = throw(round)
        assert outcome is Outcome.PLACED
    round, outcome = throw(round)
    assert outcome is Outcome.WON
    assert round.launched and round.parts == STONES


def test_the_tolerance_is_half_a_tick_gap_where_that_is_inside_the_cap():
    for den, gap in ((6, 20), (8, 15), (12, 10)):
        target = Target(1, den, den)
        assert target.tolerance == gap
        assert SPAN // den == gap * 2


def test_a_quarter_is_not_a_half():
    """The cap, named after what it stops. Half a tick gap says only that no
    other tick is nearer, and on a line with three marks on it that is half the
    line: `1/2` scored for a stone on the quarter mark, which is a fraction he
    can name and was not asked for."""
    half = Target(1, 2, 2)
    assert abs(SPAN // 4 - half.value) > half.tolerance
    for ticks in (2, 3, 4, 5):
        assert Target(1, ticks, ticks).tolerance == WIDEST


def test_a_finer_partition_is_a_tighter_shot():
    assert Target(1, 12, 12).tolerance < Target(1, 3, 3).tolerance


def test_an_end_can_be_lost_so_a_win_is_a_win():
    """`storage._fold` asks `losable`: without this a perfect end folds to
    practice forever and the level card never shows one."""
    assert end().losable
    untimed_rocket = new_round(LEVELS_BY_ID["small"], random.Random(0), timed=False, rules=ROCKET)
    assert not untimed_rocket.losable


def test_the_clock_can_never_end_an_end():
    round = end()
    for _ in range(200):
        round, outcome = tick(round, 0.5)
        assert outcome is None
    assert not round.over


def test_time_on_a_stone_is_recorded_even_though_nothing_is_timed():
    """The one clock a placement does *not* stop here: it is the only measure of
    how long he thought, and no deck weighting reads it to be corrupted."""
    round = end()
    asked = round.current
    round, _ = tick(round, 4.0)
    assert round.on_current == pytest.approx(4.0)
    round, _ = throw(round)
    assert round.attempts[asked.key].seconds == pytest.approx(4.0)
    # Zeroed on the way out, or the next stone is charged for this one too.
    assert round.on_current == 0.0


def test_an_end_draws_no_yardage_and_replays_from_its_seed():
    round = end()
    assert round.gains == () and round.sacks == () and round.sack_at == ()
    assert round.sacked is None
    assert end().queue == round.queue


def test_a_football_round_still_has_to_run_the_length_of_the_line():
    from dataclasses import replace as _replace

    from mathr.domain.round import FOOTBALL

    with pytest.raises(ValueError):
        new_round(
            LEVELS_BY_ID["small"], random.Random(0), rules=_replace(FOOTBALL, target=10)
        )


def test_every_fraction_level_can_fill_an_end():
    for level_id in ("halves", "thirds", "fifths", "eighths", "same_as", "fractions"):
        round = end(level_id)
        for _ in range(STONES):
            round, outcome = place(round, round.current.value)
        assert round.launched, level_id
