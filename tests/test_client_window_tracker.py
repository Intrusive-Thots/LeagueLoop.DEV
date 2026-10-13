"""
Tests for `services.client_window_tracker`.
"""
import ctypes
import sys
from unittest.mock import MagicMock, patch

import pytest

from services.client_window_tracker import (
    LEAGUE_TITLES,
    RIOT_TITLES,
    ClientWindow,
    ClientWindowTracker,
)


def test_client_window_dataclass():
    """Test ClientWindow default values and usable property."""
    cw = ClientWindow()
    assert not cw.found
    assert not cw.visible
    assert not cw.minimized
    assert cw.rect == (0, 0, 0, 0)
    assert cw.hwnd == 0
    assert cw.title == ""
    assert not cw.usable

    # Valid usable window
    usable_cw = ClientWindow(
        found=True,
        visible=True,
        minimized=False,
        rect=(100, 100, 1280, 720),
        hwnd=12345,
        title="League of Legends",
    )
    assert usable_cw.usable

    # Minimized window is not usable
    min_cw = ClientWindow(
        found=True,
        visible=True,
        minimized=True,
        rect=(100, 100, 1280, 720),
        hwnd=12345,
        title="League of Legends",
    )
    assert not min_cw.usable

    # Invisible window is not usable
    invis_cw = ClientWindow(
        found=True,
        visible=False,
        minimized=False,
        rect=(100, 100, 1280, 720),
        hwnd=12345,
        title="League of Legends",
    )
    assert not invis_cw.usable

    # Zero size window is not usable
    zero_cw = ClientWindow(
        found=True,
        visible=True,
        minimized=False,
        rect=(100, 100, 0, 0),
        hwnd=12345,
        title="League of Legends",
    )
    assert not zero_cw.usable


def test_tracker_non_windows():
    """Test ClientWindowTracker on non-Windows platforms returns empty ClientWindow."""
    with patch("services.client_window_tracker._IS_WINDOWS", False):
        tracker = ClientWindowTracker()
        win = tracker.tick()
        assert not win.found
        assert not win.usable


class TestClientWindowTrackerWindows:
    """Test suite for ClientWindowTracker Windows logic using ctypes mocks."""

    def setup_method(self):
        self.mock_user32 = MagicMock()
        self.mock_windll = MagicMock()
        self.mock_windll.user32 = self.mock_user32

        # Define mock wintypes on ctypes so non-Windows environments have wintypes
        self.mock_wintypes = MagicMock()
        self.mock_wintypes.BOOL = ctypes.c_long
        self.mock_wintypes.HWND = ctypes.c_void_p
        self.mock_wintypes.LPARAM = ctypes.c_long

        # Mock RECT structure with left, top, right, bottom attributes
        class MockRect(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        self.mock_wintypes.RECT = MockRect

        self.added_wintypes = False
        if not hasattr(ctypes, "wintypes"):
            ctypes.wintypes = self.mock_wintypes
            self.added_wintypes = True

        self.patches = [
            patch.object(ctypes, "windll", self.mock_windll, create=True),
            patch.object(
                ctypes, "WINFUNCTYPE", lambda *args: lambda func: func, create=True
            ),
            patch("services.client_window_tracker._IS_WINDOWS", True),
        ]
        for p in self.patches:
            p.start()

    def teardown_method(self):
        for p in reversed(self.patches):
            p.stop()
        if self.added_wintypes and hasattr(ctypes, "wintypes"):
            del ctypes.wintypes

    def test_find_league_window(self):
        """Test finding an active League Client window during enumeration."""
        self.mock_user32.IsIconic.return_value = False

        def fake_enum_windows(callback, lparam):
            self.mock_user32.IsWindowVisible.side_effect = lambda hwnd: hwnd == 100
            self.mock_user32.GetWindowTextLengthW.side_effect = lambda hwnd: (
                17 if hwnd == 100 else 0
            )

            def fake_get_text(hwnd, buf, length):
                if hwnd == 100:
                    buf.value = "League of Legends"

            self.mock_user32.GetWindowTextW.side_effect = fake_get_text

            def fake_get_rect(hwnd, byref_rect):
                rect = byref_rect._obj if hasattr(byref_rect, "_obj") else byref_rect
                rect.left = 100
                rect.top = 200
                rect.right = 1380
                rect.bottom = 920

            self.mock_user32.GetWindowRect.side_effect = fake_get_rect

            callback(100, 0)

        self.mock_user32.EnumWindows.side_effect = fake_enum_windows
        self.mock_user32.IsWindow.return_value = True

        tracker = ClientWindowTracker()
        win = tracker.tick()

        assert win.found
        assert win.visible
        assert not win.minimized
        assert win.hwnd == 100
        assert win.title == "League of Legends"
        assert win.rect == (100, 200, 1280, 720)
        assert win.usable

    def test_caching_and_forget(self):
        """Test handle caching across ticks and resetting via forget()."""
        self.mock_user32.IsIconic.return_value = False

        def fake_enum_windows(callback, lparam):
            self.mock_user32.IsWindowVisible.return_value = True
            self.mock_user32.GetWindowTextLengthW.return_value = 17

            def fake_get_text(hwnd, buf, length):
                buf.value = "League of Legends"

            self.mock_user32.GetWindowTextW.side_effect = fake_get_text

            def fake_get_rect(hwnd, byref_rect):
                rect = byref_rect._obj if hasattr(byref_rect, "_obj") else byref_rect
                rect.left = 0
                rect.top = 0
                rect.right = 800
                rect.bottom = 600

            self.mock_user32.GetWindowRect.side_effect = fake_get_rect

            callback(200, 0)

        self.mock_user32.EnumWindows.side_effect = fake_enum_windows
        self.mock_user32.IsWindow.return_value = True

        tracker = ClientWindowTracker()
        win1 = tracker.tick()
        assert win1.hwnd == 200
        assert self.mock_user32.EnumWindows.call_count == 1

        # Second tick should re-validate handle 200 without calling EnumWindows again
        win2 = tracker.tick()
        assert win2.hwnd == 200
        assert self.mock_user32.EnumWindows.call_count == 1

        # forget() clears cache
        tracker.forget()
        win3 = tracker.tick()
        assert win3.hwnd == 200
        assert self.mock_user32.EnumWindows.call_count == 2

    def test_switch_from_riot_to_league_window(self):
        """Test transitioning from Riot Client to League Client when League opens."""
        self.mock_user32.IsIconic.return_value = False

        def fake_enum_riot(callback, lparam):
            self.mock_user32.IsWindowVisible.return_value = True
            self.mock_user32.GetWindowTextLengthW.return_value = 11

            def fake_get_text(hwnd, buf, length):
                buf.value = "Riot Client"

            self.mock_user32.GetWindowTextW.side_effect = fake_get_text

            def fake_get_rect(hwnd, byref_rect):
                rect = byref_rect._obj if hasattr(byref_rect, "_obj") else byref_rect
                rect.left = 10
                rect.top = 10
                rect.right = 510
                rect.bottom = 510

            self.mock_user32.GetWindowRect.side_effect = fake_get_rect

            callback(300, 0)

        self.mock_user32.EnumWindows.side_effect = fake_enum_riot
        self.mock_user32.IsWindow.return_value = True

        tracker = ClientWindowTracker()
        win1 = tracker.tick()
        assert win1.hwnd == 300
        assert win1.title == "Riot Client"

        # Step 2: Next tick, _still_valid check runs _find_league_only, which finds League
        def fake_enum_league(callback, lparam):
            self.mock_user32.IsWindowVisible.return_value = True
            self.mock_user32.GetWindowTextLengthW.return_value = 17

            def fake_get_text(hwnd, buf, length):
                buf.value = "League of Legends"

            self.mock_user32.GetWindowTextW.side_effect = fake_get_text

            def fake_get_rect(hwnd, byref_rect):
                rect = byref_rect._obj if hasattr(byref_rect, "_obj") else byref_rect
                rect.left = 100
                rect.top = 100
                rect.right = 1100
                rect.bottom = 700

            self.mock_user32.GetWindowRect.side_effect = fake_get_rect

            callback(400, 0)

        self.mock_user32.EnumWindows.side_effect = fake_enum_league

        win2 = tracker.tick()
        assert win2.hwnd == 400
        assert win2.title == "League of Legends"

    def test_minimized_window_retains_last_rect(self):
        """Test that a minimized window retains and reports its last known rect."""
        is_iconic = False

        self.mock_user32.IsIconic.side_effect = lambda hwnd: is_iconic

        def fake_enum(callback, lparam):
            self.mock_user32.IsWindowVisible.return_value = True
            self.mock_user32.GetWindowTextLengthW.return_value = 17

            def fake_get_text(hwnd, buf, length):
                buf.value = "League of Legends"

            self.mock_user32.GetWindowTextW.side_effect = fake_get_text

            def fake_get_rect(hwnd, byref_rect):
                rect = byref_rect._obj if hasattr(byref_rect, "_obj") else byref_rect
                rect.left = 50
                rect.top = 50
                rect.right = 1050
                rect.bottom = 650

            self.mock_user32.GetWindowRect.side_effect = fake_get_rect

            callback(500, 0)

        self.mock_user32.EnumWindows.side_effect = fake_enum
        self.mock_user32.IsWindow.return_value = True

        tracker = ClientWindowTracker()
        win1 = tracker.tick()
        assert win1.rect == (50, 50, 1000, 600)
        assert not win1.minimized

        # Step 2: Window gets minimized
        is_iconic = True

        win2 = tracker.tick()
        assert win2.minimized
        assert win2.rect == (50, 50, 1000, 600)

    def test_tick_exception_suppression(self):
        """Test that unexpected exceptions during tick() are caught and log-suppressed."""
        self.mock_user32.IsWindow.side_effect = RuntimeError("Window handle destroyed")

        tracker = ClientWindowTracker()
        tracker._hwnd = 999
        win = tracker.tick()

        assert not win.found
        assert tracker._hwnd == 0

    def test_desktop_attachment_error_handled(self):
        """Test that desktop attachment errors during window search are safely ignored."""
        self.mock_user32.OpenInputDesktop.side_effect = OSError("Desktop access denied")
        self.mock_user32.EnumWindows.side_effect = lambda cb, lp: None

        tracker = ClientWindowTracker()
        win = tracker.tick()
        assert not win.found
