"""
The window's behaviour as the League Client comes, goes and moves.

Nine situations, one set of rules. They were spread across three places
before — the orb followed the client, the main window did not, and the
compact-mode toggle asked `isVisible()`, which answers a different question
from the one it was asking.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from core.state import ClientWindowState  # noqa: E402

FHD = (0, 0, 1920, 1040)
SECOND = (1920, 0, 2560, 1400)
PANEL = (360, 620)


def client(x=100, y=60, w=1280, h=720, **kwargs):
    fields = dict(found=True, hwnd=7, x=x, y=y, width=w, height=h,
                  visible=True, minimized=False, monitor=1, dpi=96)
    fields.update(kwargs)
    return ClientWindowState(**fields)


class _Widget:
    """A stand-in for a Qt window: the anchor only needs these four calls."""

    def __init__(self, size=PANEL):
        self._size, self.pos, self._visible = size, None, True
        self.shows, self.hides = 0, 0

    def width(self):
        return self._size[0]

    def height(self):
        return self._size[1]

    def move(self, x, y):
        self.pos = (x, y)

    def isVisible(self):  # noqa: N802
        return self._visible

    def show(self):
        self._visible = True
        self.shows += 1

    def hide(self):
        self._visible = False
        self.hides += 1


class AnchorStateTests(unittest.TestCase):
    """Each transition, asserted on its own."""

    def setUp(self):
        from ui.qt.services.companion_anchor import CompanionAnchor

        self.widget = _Widget()
        self.anchor = CompanionAnchor(self.widget)
        # The anchor asks Qt for screens; feed it a known desktop instead.
        self.anchor.placement_for = self._placement_for

    def _placement_for(self, window):
        from ui.qt.services.companion_position import place_companion

        if not window.usable:
            return None
        return place_companion(window.rect, PANEL, [FHD, SECOND])

    def test_the_panel_moves_when_the_client_moves(self):
        self.anchor.apply(client(x=100))
        first = self.widget.pos
        self.anchor.apply(client(x=400))
        self.assertNotEqual(self.widget.pos, first)

    def test_the_panel_moves_when_the_client_is_resized(self):
        self.anchor.apply(client(w=1280))
        first = self.widget.pos
        self.anchor.apply(client(w=900))
        self.assertNotEqual(self.widget.pos, first)

    def test_the_panel_follows_the_client_to_another_monitor(self):
        self.anchor.apply(client(x=100))
        self.anchor.apply(client(x=2100, monitor=2, dpi=144))
        self.assertIsNotNone(self.widget.pos)
        self.assertGreaterEqual(self.widget.pos[0], SECOND[0])

    def test_the_panel_hides_with_a_minimised_client_and_comes_back(self):
        self.anchor.apply(client())
        self.anchor.apply(client(minimized=True))
        self.assertFalse(self.widget.isVisible())
        self.assertTrue(self.anchor.hidden_by_client)

        self.anchor.apply(client())
        self.assertTrue(self.widget.isVisible())
        self.assertFalse(self.anchor.hidden_by_client)

    def test_closing_the_client_leaves_the_panel_reachable(self):
        """Hiding here would take away the user's way back into the app."""
        self.anchor.apply(client())
        self.anchor.apply(ClientWindowState())
        self.assertTrue(self.widget.isVisible())
        self.assertFalse(self.anchor.hidden_by_client)

    def test_a_panel_the_user_closed_is_not_reopened_by_the_client(self):
        self.anchor.apply(client())
        self.widget.hide()          # the user closed it
        self.anchor.apply(client(x=500))
        self.assertFalse(self.widget.isVisible())

    def test_starting_the_client_places_the_panel(self):
        self.anchor.apply(ClientWindowState())
        self.assertIsNone(self.widget.pos)
        self.anchor.apply(client())
        self.assertIsNotNone(self.widget.pos)

    def test_following_can_be_switched_off_without_moving_the_panel(self):
        self.anchor.apply(client())
        placed = self.widget.pos
        self.anchor.enabled = False
        self.anchor.apply(client(x=1500))
        self.assertEqual(self.widget.pos, placed)


class CompactModeTests(unittest.TestCase):
    """One surface visible at a time, in both directions."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from ui.qt.main_window import LeagueLoopMainWindow

        self.window = LeagueLoopMainWindow(container=None)
        self.window.show()
        for _ in range(4):
            self.app.processEvents()

    def tearDown(self):
        self.window.orb.hide()
        self.window.close()

    def test_toggling_swaps_which_surface_is_visible(self):
        self.assertFalse(self.window.compact_mode)
        self.window.toggle_orb_mode()
        self.assertTrue(self.window.compact_mode)
        self.assertFalse(self.window.isVisible())
        self.assertTrue(self.window.orb.isVisible())

        self.window.toggle_orb_mode()
        self.assertFalse(self.window.compact_mode)
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.orb.isVisible())

    def test_toggling_from_minimised_does_not_leave_two_surfaces_up(self):
        """A minimised window is still `isVisible()` in Qt, which is what the
        old branch asked — so this produced the orb *and* the window."""
        self.window.showMinimized()
        for _ in range(4):
            self.app.processEvents()
        self.window.toggle_orb_mode()
        self.assertTrue(self.window.compact_mode)
        self.assertFalse(self.window.isVisible())
        self.assertTrue(self.window.orb.isVisible())

    def test_setting_the_same_mode_twice_is_a_no_op(self):
        self.window.set_compact_mode(False)
        self.assertTrue(self.window.isVisible())
        self.window.set_compact_mode(True)
        self.window.set_compact_mode(True)
        self.assertTrue(self.window.orb.isVisible())

    def test_the_window_does_not_chase_the_client_while_the_orb_is_up(self):
        """In compact mode the orb is the visible surface and owns placement;
        moving a hidden window would fight the next restore."""
        self.window.set_compact_mode(True)
        moved = []
        self.window.anchor.apply = lambda state: moved.append(state)
        self.window._follow_client()
        self.assertEqual(moved, [])

    def test_attaching_can_be_turned_off_and_is_remembered(self):
        saved = {}

        class Config:
            def get(self, key, default=None):
                return saved.get(key, default)

            def set(self, key, value):
                saved[key] = value

        from core.config_keys import ATTACH_TO_CLIENT

        self.window.config = Config()
        self.window.set_attached_to_client(False)
        self.assertFalse(self.window.anchor.enabled)
        self.assertIs(saved[ATTACH_TO_CLIENT], False)


if __name__ == "__main__":
    unittest.main()
