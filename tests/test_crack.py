"""The code panel: lines that open locks, and alarms that end the round."""

import random

import pytest

from mathr.domain.facts import LEVELS_BY_ID, Sentence
from mathr.domain.round import (
    ALARMS,
    CODE,
    LINES_TO_CRACK,
    LOCKS,
    TENNIS,
    Outcome,
    Rules,
    apply,
    new_round,
    tick,
)

LEVEL = LEVELS_BY_ID["tens"]


def code(seed=0):
    return new_round(LEVEL, random.Random(seed), timed=False, rules=CODE, mode_id="code")


def solve(round_, lines=1):
    for _ in range(lines):
        round_, outcome = apply(round_, round_.current.answer)
    return round_, outcome


# --- a line, and a lock -----------------------------------------------------


def test_a_solved_line_opens_one_of_the_lock():
    after, outcome = solve(code())
    assert (after.parts, outcome) == (1, Outcome.CORRECT)
    assert after.lock == (0, 1, LOCKS[0])


def test_the_lock_swings_on_its_last_line():
    after, outcome = solve(code(), LOCKS[0])
    assert outcome is Outcome.CRACKED
    assert after.lock == (1, 0, LOCKS[1])


def test_each_lock_is_longer_than_the_last():
    """The last lock must not feel like the first, which a flat run of ten
    identical questions is exactly what cannot do."""
    assert list(LOCKS) == sorted(LOCKS)
    assert len(set(LOCKS)) == len(LOCKS)


def test_the_panel_holds_the_lines_already_open():
    round_, _ = solve(code(), 2)
    assert len(round_.cracked) == 2
    assert all(isinstance(line, Sentence) for line in round_.cracked)


def test_a_swung_lock_clears_the_panel():
    """The next lock starts empty; a panel that kept growing would run off the
    bottom of the screen by the third one."""
    round_, _ = solve(code(), LOCKS[0])
    assert round_.cracked == ()


def test_the_last_line_of_the_last_lock_wins_it():
    round_, outcome = solve(code(), LINES_TO_CRACK)
    assert outcome is Outcome.WON
    assert round_.launched and round_.parts == LINES_TO_CRACK


def test_the_locks_have_to_add_up_to_the_target():
    """Otherwise the last vault never swings, or the round is won partway
    through a lock with lines still on the panel."""
    with pytest.raises(ValueError):
        new_round(LEVEL, random.Random(0), timed=False, rules=Rules(
            0.0, 0.0, 0.0, False, False, ALARMS, 99, locks=LOCKS, wrong_costs_life=True
        ))


# --- the alarms -------------------------------------------------------------


def test_a_wrong_answer_trips_an_alarm_and_leaves_the_line_up():
    """He still has to open it: nothing is taken away and the queue does not
    move. What it costs is one of three tries at being wrong all round."""
    round_ = code()
    line = round_.current
    after, outcome = apply(round_, line.answer + 1)
    assert (after.points, after.parts, outcome) == (1, 0, Outcome.WRONG)
    assert after.current == line
    assert after.hint == line


def test_three_alarms_lock_it_down():
    round_ = code()
    for expected in range(1, ALARMS + 1):
        round_, outcome = apply(round_, round_.current.answer + 1)
        assert round_.points == expected
    assert outcome is Outcome.LOST
    assert round_.failed and round_.over


def test_no_hint_on_the_way_out():
    """The failure screen owns the display, exactly as it does in `tick`."""
    round_ = code()
    for _ in range(ALARMS - 1):
        round_, _ = apply(round_, round_.current.answer + 1)
    after, outcome = apply(round_, round_.current.answer + 1)
    assert (outcome, after.hint) == (Outcome.LOST, None)


def test_an_alarm_survives_being_shown_the_answer():
    """The hint is the way back in, not a second chance at being wrong for
    free: reading it and then typing the number costs nothing more."""
    round_ = code()
    tripped, _ = apply(round_, round_.current.answer + 1)
    after, outcome = apply(tripped, tripped.current.answer)
    assert (after.points, after.parts, outcome) == (1, 1, Outcome.CORRECT)


# --- the clock that is not there --------------------------------------------


def test_no_clock_but_he_is_still_timed():
    """Response time is the measurement the mode exists to take: it is what
    separates seeing the relation from computing it."""
    round_ = code()
    assert round_.seconds_left is None
    after, outcome = tick(round_, 0.5)
    assert outcome is None
    assert after.on_current == 0.5 and after.elapsed == 0.5


def test_a_code_round_can_be_lost_and_so_counts():
    assert code().losable
    assert not new_round(LEVEL, random.Random(0), timed=False).losable


def test_lives_still_need_something_that_can_spend_them():
    """Untimed tennis is three lives nothing can touch, and a match that can be
    neither won nor lost."""
    with pytest.raises(ValueError):
        new_round(LEVEL, random.Random(0), timed=False, rules=TENNIS)


def test_a_deck_of_lines_replays_by_seed():
    assert all(isinstance(item, Sentence) for item in code().deck)
    assert code(3).deck == code(3).deck
    assert code(3).deck != code(4).deck


def test_every_line_is_missing_exactly_one_number():
    for item in code().deck:
        assert item.prompt.count("?") == 1, item.prompt
        assert "?" not in item.filled


def test_the_answer_is_what_makes_the_sides_agree():
    for item in code().deck:
        assert item.left.value == item.right.value, item.filled
        assert getattr(item.right, item.slot) == item.answer


def test_a_line_key_cannot_collide_with_a_fact_key():
    facts = {fact.key for fact in LEVEL.facts}
    assert not facts & {line.key for line in code().deck}


def test_a_bare_line_is_the_only_one_that_is_not_relational():
    """`7 + 6 = ?` is the question the other three cabinets ask. It exists to
    keep a thin pool from having nothing to give, and it should be rare."""
    deck = code().deck
    bare = [line for line in deck if line.right.op is None]
    assert len(bare) < len(deck) // 3

