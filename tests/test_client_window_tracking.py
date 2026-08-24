"""
Knowing *where* the League Client is.

The application could already tell whether the client was running — the
lockfile and the process list gave it `{port, token, connected, pid}`. It had
no idea where the window sat, which is why the companion panel could only
ever float wherever it was last dragged.

These cover the two halves: finding the right window, and turning its
geometry into a position for the panel. Both run on any platform, because
every platform call goes through an injectable backend.
"""
import dataclasses
import unittest
from unittest.mock import patch, MagicMock

from core.state import ApplicationState, ClientWindowState, StateManager
from services.client_window_tracker import ClientWindowTracker, WindowInfo
from ui.qt.services.companion_position import (
    SIDE_LEFT,
    SIDE_RIGHT,
    clamp_to_screen,
    place_companion,
    screen_for_rect,
)

FHD = (0, 0, 1920, 1040)          # primary, taskbar already excluded
SECOND = (1920, 0, 2560, 1400)    # a taller monitor to the right
PANEL = (320, 620)
CLIENT_PID = 4242


def window(hwnd, pid=CLIENT_PID, w=1280, h=720, x=100, y=50,
           visible=True, minimized=False, toplevel=True, title="League",
           monitor=0, dpi=0):
    return WindowInfo(hwnd, pid, title, (x, y, w, h), visible, minimized,
                      toplevel, monitor, dpi)


class FakeBackend:
    def __init__(self, windows=()):
        self.windows = list(windows)
        self.enumerations = 0

    def enumerate_windows(self):
        self.enumerations += 1
        return list(self.windows)

    def get_window(self, hwnd):
        return next((w for w in self.windows if w.hwnd == hwnd), None)


def tracker(backend, pid=CLIENT_PID, state_manager=None):
    return ClientWindowTracker(
        state_manager=state_manager,
        pid_provider=lambda: pid,
        backend=backend,
        discovery_interval_s=0,   # no rate limit in tests
    )


class DiscoveryTests(unittest.TestCase):
    """`LeagueClientUx.exe` owns several windows. Taking the first is wrong."""

    def test_the_real_client_window_is_chosen_over_its_helpers(self):
        backend = FakeBackend([
            window(1, w=12, h=12, title="Chrome_MessageWindow"),
            window(2, w=1280, h=720, title="League of Legends"),
            window(3, w=800, h=600, visible=False, title="hidden helper"),
        ])
        state = tracker(backend).tick()
        self.assertTrue(state.found)
        self.assertEqual(state.hwnd, 2)
        self.assertEqual(state.rect, (100, 50, 1280, 720))

    def test_another_process_is_never_chosen(self):
        """A huge window belonging to something else must not win."""
        backend = FakeBackend([
            window(9, pid=9999, w=1920, h=1080, title="Some other app"),
        ])
        self.assertFalse(tracker(backend).tick().found)

    def test_invisible_windows_are_rejected(self):
        backend = FakeBackend([window(1, visible=False)])
        self.assertFalse(tracker(backend).tick().found)

    def test_child_windows_are_rejected(self):
        backend = FakeBackend([window(1, toplevel=False)])
        self.assertFalse(tracker(backend).tick().found)

    def test_tiny_windows_are_rejected(self):
        backend = FakeBackend([window(1, w=200, h=100)])
        self.assertFalse(tracker(backend).tick().found)

    def test_nothing_running_is_reported_as_not_found(self):
        state = tracker(FakeBackend([])).tick()
        self.assertFalse(state.found)
        self.assertFalse(state.usable)

    @patch("psutil.Process")
    def test_ux_child_process_window_is_matched(self, mock_process):
        """Even if the PID provider returns the parent process PID (LeagueClient.exe),
        the window owned by the child process (LeagueClientUx.exe) should be matched."""
        def mock_process_init(pid):
            mock_proc = MagicMock()
            if pid == 4000:
                mock_proc.name.return_value = "LeagueClient.exe"
            elif pid == 5000:
                mock_proc.name.return_value = "LeagueClientUx.exe"
            else:
                mock_proc.name.return_value = ""
            return mock_proc
        
        mock_process.side_effect = mock_process_init
        
        backend = FakeBackend([
            window(2, pid=5000, w=1280, h=720, title="League of Legends"),
        ])
        t = tracker(backend, pid=4000)
        state = t.tick()
        self.assertTrue(state.found)
        self.assertEqual(state.hwnd, 2)


class TrackingTests(unittest.TestCase):
    def test_discovery_happens_once_then_the_handle_is_tracked(self):
        """Enumerating every window on the desktop is the expensive call; it
        must not run on every tick."""
        backend = FakeBackend([window(2)])
        t = tracker(backend)
        for _ in range(10):
            t.tick()
        self.assertEqual(backend.enumerations, 1)

    def test_a_move_is_picked_up(self):
        backend = FakeBackend([window(2, x=100, y=100)])
        t = tracker(backend)
        self.assertEqual(t.tick().rect[:2], (100, 100))
        backend.windows = [window(2, x=500, y=100)]
        self.assertEqual(t.tick().rect[:2], (500, 100))

    def test_a_resize_is_picked_up(self):
        backend = FakeBackend([window(2, w=1280, h=720)])
        t = tracker(backend)
        self.assertEqual(t.tick().rect[2:], (1280, 720))
        backend.windows = [window(2, w=1920, h=1080)]
        self.assertEqual(t.tick().rect[2:], (1920, 1080))

    def test_minimise_and_restore_are_distinct_from_closing(self):
        backend = FakeBackend([window(2)])
        t = tracker(backend)
        t.tick()
        backend.windows = [window(2, minimized=True)]
        state = t.tick()
        self.assertTrue(state.found, "a minimised client is still there")
        self.assertTrue(state.minimized)
        self.assertFalse(state.usable)
        backend.windows = [window(2)]
        self.assertFalse(t.tick().minimized)

    def test_a_closed_client_is_reported_and_the_handle_dropped(self):
        backend = FakeBackend([window(2)])
        t = tracker(backend)
        t.tick()
        backend.windows = []
        self.assertFalse(t.tick().found)

    def test_a_recycled_handle_belonging_to_someone_else_is_rejected(self):
        """Windows reuses handles. Tracking one blindly would attach the panel
        to whatever inherited it."""
        backend = FakeBackend([window(2)])
        t = tracker(backend)
        t.tick()
        backend.windows = [window(2, pid=9999)]
        self.assertFalse(t.tick().found)

    def test_identical_geometry_is_not_republished(self):
        """Otherwise every bound view re-renders several times a second."""
        backend = FakeBackend([window(2)])
        seen = []
        t = tracker(backend)
        t.subscribe(seen.append)
        for _ in range(5):
            t.tick()
        self.assertEqual(len(seen), 1)

    def test_state_reaches_the_application_state_manager(self):
        manager = StateManager()
        backend = FakeBackend([window(2, x=7, y=9, w=1280, h=720)])
        tracker(backend, state_manager=manager).tick()
        published = manager.state.client_window
        self.assertTrue(published.found)
        self.assertEqual(published.rect, (7, 9, 1280, 720))


class StateShapeTests(unittest.TestCase):
    def test_usable_requires_a_visible_unminimised_window(self):
        self.assertFalse(ClientWindowState().usable)
        self.assertFalse(ClientWindowState(found=True, visible=False).usable)
        self.assertFalse(
            ClientWindowState(found=True, visible=True, minimized=True,
                              width=100, height=100).usable
        )
        self.assertTrue(
            ClientWindowState(found=True, visible=True, width=100, height=100).usable
        )

    def test_the_state_stays_hashable(self):
        """A dict field here would break every frozen-dataclass comparison."""
        self.assertIsInstance(hash(ApplicationState()), int)

    def test_scale_is_derived_from_dpi_and_defaults_to_one(self):
        """An unknown DPI must not silently become 0x scaling."""
        self.assertEqual(ClientWindowState().scale, 1.0)
        self.assertEqual(ClientWindowState(dpi=96).scale, 1.0)
        self.assertEqual(ClientWindowState(dpi=144).scale, 1.5)
        self.assertEqual(ClientWindowState(dpi=192).scale, 2.0)


class MonitorAndDpiTests(unittest.TestCase):
    """The brief requires monitor and DPI alongside the geometry."""

    def test_monitor_and_dpi_reach_published_state(self):
        backend = FakeBackend([window(7, monitor=0x10001, dpi=144)])
        state = tracker(backend).tick()
        self.assertTrue(state.found)
        self.assertEqual(state.monitor, 0x10001)
        self.assertEqual(state.dpi, 144)
        self.assertEqual(state.scale, 1.5)

    def test_moving_to_another_monitor_counts_as_a_change(self):
        """Same rect, different display: the panel still has to re-place."""
        first = ClientWindowState(found=True, hwnd=7, width=1280, height=720,
                                  visible=True, monitor=1, dpi=96)
        second = dataclasses.replace(first, monitor=2, dpi=144)
        self.assertNotEqual(first.geometry_key, second.geometry_key)

    def test_a_publish_with_only_a_dpi_change_is_not_suppressed(self):
        seen = []
        backend = FakeBackend([window(7, monitor=1, dpi=96)])
        track = tracker(backend)
        track.subscribe(seen.append)
        track.tick()
        backend.windows = [window(7, monitor=1, dpi=144)]
        track.tick()
        self.assertEqual([s.dpi for s in seen], [96, 144])

    def test_the_state_manager_receives_the_new_fields(self):
        manager = StateManager()
        backend = FakeBackend([window(7, monitor=99, dpi=120)])
        tracker(backend, state_manager=manager).tick()
        window_state = manager.state.client_window
        self.assertEqual(window_state.monitor, 99)
        self.assertEqual(window_state.dpi, 120)


class PlacementTests(unittest.TestCase):
    """No hard-coded coordinates: the position is derived from the client."""

    def _on_screen(self, placement, screen, size=PANEL):
        return (
            screen[0] <= placement.x
            and placement.x + size[0] <= screen[0] + screen[2]
            and screen[1] <= placement.y
            and placement.y + size[1] <= screen[1] + screen[3]
        )

    def test_it_sits_to_the_right_of_the_client_by_default(self):
        client = (100, 50, 1280, 720)
        placement = place_companion(client, PANEL, [FHD], gap=8)
        self.assertEqual(placement.side, SIDE_RIGHT)
        self.assertEqual(placement.x, 100 + 1280 + 8)
        self.assertEqual(placement.y, 50)
        self.assertFalse(placement.overlapping)

    def test_it_flips_to_the_left_when_the_right_has_no_room(self):
        client = (620, 50, 1280, 720)   # right edge at 1900 of 1920
        placement = place_companion(client, PANEL, [FHD], gap=8)
        self.assertEqual(placement.side, SIDE_LEFT)
        self.assertTrue(self._on_screen(placement, FHD))

    def test_a_maximised_client_overlaps_rather_than_going_off_screen(self):
        placement = place_companion(FHD, PANEL, [FHD])
        self.assertTrue(placement.overlapping)
        self.assertTrue(self._on_screen(placement, FHD))

    def test_the_preferred_side_is_honoured_when_it_fits(self):
        client = (620, 50, 1280, 720)
        placement = place_companion(
            client, PANEL, [FHD], preferred_side=SIDE_LEFT
        )
        self.assertEqual(placement.side, SIDE_LEFT)

    def test_it_stays_on_screen_when_the_client_is_near_the_bottom(self):
        client = (100, 900, 1280, 720)  # extends past the screen bottom
        placement = place_companion(client, PANEL, [FHD])
        self.assertTrue(self._on_screen(placement, FHD))

    def test_it_follows_the_client_to_another_monitor(self):
        client = (2000, 100, 1280, 720)
        placement = place_companion(client, PANEL, [FHD, SECOND])
        self.assertTrue(self._on_screen(placement, SECOND))
        self.assertFalse(self._on_screen(placement, FHD))

    def test_the_screen_is_the_one_the_client_mostly_occupies(self):
        """Corner-based detection makes the panel jump monitors early, while
        a window is still mostly on the old one."""
        # Straddles the seam: 420px wide on the primary, 180px on the second.
        mostly_primary = (1500, 100, 600, 720)
        self.assertEqual(screen_for_rect(mostly_primary, [FHD, SECOND]), FHD)
        # And the other way round.
        mostly_second = (1800, 100, 1280, 720)   # 120px primary, 1160 second
        self.assertEqual(screen_for_rect(mostly_second, [FHD, SECOND]), SECOND)

    def test_an_off_screen_client_still_yields_a_visible_panel(self):
        placement = place_companion((-500, 50, 1280, 720), PANEL, [FHD])
        self.assertTrue(self._on_screen(placement, FHD))

    def test_clamping_prefers_the_top_when_the_panel_is_taller_than_the_screen(self):
        x, y = clamp_to_screen(0, 500, (320, 2000), FHD)
        self.assertEqual(y, FHD[1])


class AnchorTests(unittest.TestCase):
    """The panel hides with the client and comes back with it — but must not
    fight the user about it."""

    class FakeWidget:
        def __init__(self, w=320, h=620):
            self._w, self._h = w, h
            self.visible = True
            self.moved_to = None

        def width(self): return self._w
        def height(self): return self._h
        def isVisible(self): return self.visible
        def hide(self): self.visible = False
        def show(self): self.visible = True
        def move(self, x, y): self.moved_to = (x, y)

    def _anchor(self, widget, screens=(FHD,)):
        from ui.qt.services import companion_anchor

        anchor = companion_anchor.CompanionAnchor(widget)
        # Screens come from Qt, which is not running in this test.
        companion_anchor.qt_available_screens = lambda app=None: list(screens)
        return anchor

    def test_it_hides_when_the_client_minimises_and_returns_on_restore(self):
        widget = self.FakeWidget()
        anchor = self._anchor(widget)
        live = ClientWindowState(found=True, visible=True, x=100, y=50,
                                 width=1280, height=720)
        anchor.apply(live)
        self.assertTrue(widget.visible)

        anchor.apply(ClientWindowState(found=True, visible=True, minimized=True,
                                       x=100, y=50, width=1280, height=720))
        self.assertFalse(widget.visible)
        self.assertTrue(anchor.hidden_by_client)

        anchor.apply(live)
        self.assertTrue(widget.visible)
        self.assertFalse(anchor.hidden_by_client)

    def test_closing_the_client_leaves_the_panel_alone(self):
        """Hiding here would take away the user's way back into the app."""
        widget = self.FakeWidget()
        anchor = self._anchor(widget)
        anchor.apply(ClientWindowState(found=True, visible=True, x=100, y=50,
                                       width=1280, height=720))
        anchor.apply(ClientWindowState())
        self.assertTrue(widget.visible)

    def test_it_moves_the_widget_to_the_calculated_position(self):
        widget = self.FakeWidget()
        anchor = self._anchor(widget)
        anchor.apply(ClientWindowState(found=True, visible=True, x=100, y=50,
                                       width=1280, height=720))
        self.assertEqual(widget.moved_to, (100 + 1280 + 8, 50))


class NoHardCodedCoordinatesTests(unittest.TestCase):
    def test_the_orb_does_not_place_itself_at_a_fixed_point(self):
        import inspect

        from ui.qt.widgets import orb_widget

        source = inspect.getsource(orb_widget)
        # The only move() left is the drag handler, which is user-driven.
        self.assertNotIn("move(1200", source)
        self.assertIn("CompanionAnchor", source)

    def test_the_panel_size_is_a_token_not_a_literal(self):
        import inspect

        from ui.qt.widgets import orb_widget

        source = inspect.getsource(orb_widget)
        self.assertNotIn("setFixedSize(280, 72)", source)
        self.assertIn("ORB_WIDTH", source)


if __name__ == "__main__":
    unittest.main()
