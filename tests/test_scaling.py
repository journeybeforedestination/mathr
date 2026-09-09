"""The load-bearing transform: layout is design space, the window is not."""

import pytest

from mathr.shell.draw import DESIGN, fit, to_design, to_window

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


def test_alien_is_distant_while_the_bank_is_full_and_fills_the_sky_at_zero():
    from mathr.shell.draw import alien_scale

    assert alien_scale(20.0, 12.0) == 0.0  # above the cap, during grace
    assert alien_scale(12.0, 12.0) == 0.0
    assert alien_scale(6.0, 12.0) == pytest.approx(0.5)
    assert alien_scale(0.0, 12.0) == 1.0


def test_alien_retreats_when_time_is_earned_back():
    from mathr.shell.draw import alien_scale

    closing = alien_scale(4.0, 12.0)
    after_a_correct_answer = alien_scale(7.0, 12.0)
    assert after_a_correct_answer < closing
