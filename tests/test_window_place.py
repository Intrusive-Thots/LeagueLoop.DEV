"""Popups must open fully on-screen even when the sidebar sits at a screen edge."""
import pytest

from ui.components.window_place import EDGE_MARGIN, clamp_rect

AREA = (0, 0, 1920, 1040)  # 1080p minus taskbar


def test_inside_position_is_untouched():
    assert clamp_rect(500, 300, 460, 460, AREA) == (500, 300)


def test_left_edge_sidebar_popup_is_pulled_on_screen():
    # About (460 wide) centred on a 300 px sidebar docked at x=0 → x=-80.
    assert clamp_rect(-80, 270, 460, 460, AREA) == (EDGE_MARGIN, 270)


def test_right_and_bottom_edges():
    x, y = clamp_rect(1800, 900, 380, 480, AREA)
    assert x + 380 <= AREA[2] - EDGE_MARGIN + 0
    assert y + 480 <= AREA[3] - EDGE_MARGIN + 0


def test_left_monitor_negative_coordinates_stay_valid():
    left_monitor = (-1920, 0, 0, 1040)
    assert clamp_rect(-1500, 200, 460, 460, left_monitor) == (-1500, 200)


def test_oversized_window_keeps_title_bar_reachable():
    small = (0, 0, 700, 500)
    assert clamp_rect(-50, -50, 800, 520, small) == (EDGE_MARGIN, EDGE_MARGIN)
