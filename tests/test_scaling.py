"""The load-bearing transform: layout is design space, the window is not."""

import pytest

from mathr.shell.draw import DESIGN, FIELD, fit, to_design, to_window

WINDOWS = [DESIGN, (960, 1040), (620, 1400), (2560, 1440), (1000, 500)]


@pytest.mark.parametrize("window", WINDOWS)
@pytest.mark.parametrize("point", [(0, 0), (640, 400), (980, 520), (1279, 799)])
def test_window_round_trips_back_to_design(window, point):
    assert to_design(to_window(point, window), window) == pytest.approx(point, abs=2)


@pytest.mark.parametrize("window", WINDOWS)
def test_design_surface_fits_inside_the_window(window):
    scale, (ox, oy) = fit(window)
    assert 0 <= ox and 0 <= oy
    assert DESIGN[0] * scale + 2 * ox <= window[0] + 1
    assert DESIGN[1] * scale + 2 * oy <= window[1] + 1


def test_letterbox_is_centred_on_a_tall_tile():
    scale, (ox, oy) = fit((640, 1600))
    assert scale == pytest.approx(0.5)
    assert (ox, oy) == (0, 600)


def test_the_threat_is_distant_while_the_clock_is_full_and_on_him_at_zero():
    from mathr.shell.draw import closing

    assert closing(20.0, 12.0) == 0.0  # above the cap, during grace
    assert closing(12.0, 12.0) == 0.0
    assert closing(6.0, 12.0) == pytest.approx(0.5)
    assert closing(0.0, 12.0) == 1.0


def test_the_threat_retreats_when_time_is_earned_back():
    from mathr.shell.draw import closing

    approaching = closing(4.0, 12.0)
    after_a_correct_answer = closing(7.0, 12.0)
    assert after_a_correct_answer < approaching


def test_the_ball_lands_on_his_baseline_and_starts_on_the_opponents():
    from mathr.shell.draw import COURT_BOTTOM, COURT_TOP, court_lane, court_point

    assert court_point(0.0, 0.0)[1] == COURT_TOP
    assert court_point(0.0, 1.0)[1] == COURT_BOTTOM
    assert all(-1.0 <= court_lane(asked) <= 1.0 for asked in range(20))


def test_the_court_is_wider_near_him_than_at_the_far_baseline():
    from mathr.shell.draw import court_point

    far = court_point(1.0, 0.0)[0] - court_point(-1.0, 0.0)[0]
    near = court_point(1.0, 1.0)[0] - court_point(-1.0, 1.0)[0]
    assert near > far


def test_the_court_stays_clear_of_the_keypad():
    from mathr.shell.app import KEYPAD
    from mathr.shell.draw import court_point

    assert max(court_point(1.0, travel)[0] for travel in (0.0, 0.5, 1.0)) < min(
        button.rect.left for button in KEYPAD
    )


def test_a_return_ends_at_the_opponents_baseline():
    from mathr.shell.draw import return_flight

    assert return_flight(0.8, 1.0, 0.0) == (0.8, 1.0)
    assert return_flight(0.8, 1.0, 1.0) == (0.0, 0.0)


def test_a_missed_ball_carries_on_past_his_baseline():
    from mathr.shell.draw import past_flight

    lane, travel = past_flight(-0.4, 1.0, 1.0)
    assert lane == -0.4 and travel > 1.0


def test_the_player_stays_put_through_his_follow_through():
    from mathr.shell.app import Volley

    volley = Volley("return", 0.8, 1.0, 0.8, 0.34)
    volley.elapsed = 0.17
    assert volley.player_lane == 0.8
    assert volley.position[1] < 1.0 and not volley.done
    assert 0.0 < volley.swing < 1.0
    volley.elapsed = 0.34
    assert volley.done and volley.position == (0.0, 0.0) and volley.swing == 0.0


# --- the football field ------------------------------------------------------


def test_a_yard_number_and_a_click_are_the_same_mapping():
    from mathr.shell.draw import field_x, field_yards

    for yards in (0, 1, 37, 50, 99, 100):
        x = field_x(yards, 100)
        assert field_yards((x, FIELD.centery), 100) == yards


def test_the_field_sits_above_everything_he_types_on():
    """Full width, so the line gets ten pixels a yard: it has to clear the
    readout above it and the entry and keypad below."""
    from mathr.shell.app import KEYPAD
    from mathr.shell.draw import CATCH, DOWNFIELD, TIME_BAR

    assert FIELD.top > TIME_BAR.bottom
    assert FIELD.bottom < min(button.rect.top for button in KEYPAD)
    assert FIELD.bottom < DOWNFIELD.entry.top and FIELD.bottom < CATCH.top
    assert DOWNFIELD.entry.right < min(button.rect.left for button in KEYPAD)
    assert CATCH.right < DOWNFIELD.entry.left


def test_a_click_off_the_field_is_not_a_throw():
    from mathr.shell.draw import field_yards

    assert field_yards((FIELD.centerx, FIELD.top - 100), 100) is None
    assert field_yards((FIELD.centerx, FIELD.bottom + 200), 100) is None


def test_the_tolerance_is_wide_enough_to_click_at_all():
    from mathr.domain.round import PLACE_MAX, PLACE_TOLERANCE
    from mathr.shell.draw import field_x

    span = field_x(PLACE_TOLERANCE, PLACE_MAX) - field_x(0, PLACE_MAX)
    assert span >= 20  # a seven-year-old with a mouse


# --- the cabinet at any height -----------------------------------------------


def test_a_full_height_cabinet_is_exactly_what_it_always_was():
    """The 2x2 grid halved the cabinets; scaling by the height the offsets were
    drawn against is what keeps the original look at the original size."""
    import pygame

    from mathr.shell.draw import CABINET_HEIGHT, cabinet_parts

    marquee, screen, panel = cabinet_parts(pygame.Rect(160, 190, 400, CABINET_HEIGHT))
    assert (marquee.x, marquee.y, marquee.width, marquee.height) == (184, 210, 352, 62)
    assert (screen.x, screen.y, screen.width, screen.height) == (190, 290, 340, 236)
    assert (panel.x, panel.y, panel.width, panel.height) == (190, 546, 340, 60)


def test_every_cabinet_in_the_grid_has_a_panel_with_height():
    """Below about 380 the original absolute offsets gave the panel a negative
    height, which pygame draws inverted or not at all."""
    from mathr.shell.app import CABINETS
    from mathr.shell.draw import cabinet_parts

    for _, rect in CABINETS:
        marquee, screen, panel = cabinet_parts(rect)
        assert panel.height > 0
        assert screen.bottom < panel.top < panel.bottom <= rect.bottom
        assert rect.top < marquee.top and marquee.bottom < screen.top


# --- the ice ----------------------------------------------------------------


def test_the_ends_of_the_sheet_are_nought_and_one():
    from mathr.domain.facts import SPAN
    from mathr.shell.draw import SHEET, sheet_units

    y = SHEET.centery
    assert sheet_units((SHEET.left + 80, y), SPAN) == 0
    assert sheet_units((SHEET.right - 80, y), SPAN) == SPAN


def test_a_click_across_the_ice_only_ever_moves_up_the_line():
    from mathr.domain.facts import SPAN
    from mathr.shell.draw import SHEET, sheet_units

    y = SHEET.centery
    read = [sheet_units((x, y), SPAN) for x in range(SHEET.left, SHEET.right, 10)]
    assert read == sorted(read)
    assert read[0] == 0 and read[-1] == SPAN


def test_a_click_off_the_ice_is_not_a_throw():
    from mathr.domain.facts import SPAN
    from mathr.shell.draw import SHEET, sheet_units

    assert sheet_units((SHEET.centerx, SHEET.top - 60), SPAN) is None
    assert sheet_units((SHEET.centerx, SHEET.bottom + 60), SPAN) is None


def test_a_finer_partition_draws_a_smaller_house():
    """The rings are the tolerance, so the shot visibly gets harder."""
    from mathr.domain.facts import SPAN, Target
    from mathr.shell.draw import sheet_x

    def spread(target):
        return sheet_x(target.tolerance, SPAN) - sheet_x(0, SPAN)

    assert spread(Target(1, 12, 12)) < spread(Target(1, 3, 3)) < spread(Target(1, 2, 2))


def test_two_stones_on_one_mark_stand_in_a_column():
    """1/2 and 2/4 are the same place, and one stone drawn over another is a
    stone that has gone missing."""
    from mathr.domain.facts import SPAN
    from mathr.shell.draw import stone_rows

    assert stone_rows([120, 120, 120], SPAN) == (0, 1, 2)


def test_stones_far_enough_apart_all_sit_on_the_line():
    from mathr.domain.facts import SPAN
    from mathr.shell.draw import stone_rows

    assert stone_rows([0, 60, 120, 180, 240], SPAN) == (0, 0, 0, 0, 0)


def test_a_column_of_stones_never_climbs_off_the_ice():
    from mathr.domain.facts import SPAN
    from mathr.shell.draw import (
        SHEET,
        SHEET_LINE,
        STONE_RADIUS,
        STONE_ROW,
        stone_rows,
    )

    rows = stone_rows([120] * 8, SPAN)
    assert SHEET_LINE - max(rows) * STONE_ROW - STONE_RADIUS >= SHEET.top
