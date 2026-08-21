"""
Staying in front of the League Client.

The client raises itself when a lobby opens and again when the draft starts —
exactly the two moments LeagueLoop is worth looking at. "Always on top" was a
Settings toggle that wrote `always_on_top` to config, and **nothing on the
main window ever read it**, so the app sank behind the client with no way
back short of alt-tab.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt


class FakeConfig:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def set_batch(self, mapping):
        self.values.update(mapping)


class Container:
    def __init__(self, **cfg):
        import tempfile
        from core.container import ApplicationContainer

        self._tmp = tempfile.TemporaryDirectory()
        self._real = ApplicationContainer(
            db_path=os.path.join(self._tmp.name, "t.db")
        )
        self._real.config = FakeConfig(**cfg)
        self.__dict__.update(
            {k: v for k, v in self._real.__dict__.items() if not k.startswith("_")}
        )
        self.config = self._real.config

    def shutdown(self):
        self._real.shutdown()
        self._tmp.cleanup()


class AlwaysOnTopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, **cfg):
        from ui.qt.main_window import LeagueLoopMainWindow

        container = Container(**cfg)
        self.addCleanup(container.shutdown)
        return LeagueLoopMainWindow(container=container)

    def test_on_by_default(self):
        window = self._window()
        self.assertTrue(window.windowFlags() & Qt.WindowStaysOnTopHint)

    def test_the_config_value_is_honoured(self):
        window = self._window(always_on_top=False)
        self.assertFalse(window.windowFlags() & Qt.WindowStaysOnTopHint)

    def test_toggling_applies_immediately(self):
        window = self._window(always_on_top=False)
        window.set_always_on_top(True)
        self.assertTrue(window.windowFlags() & Qt.WindowStaysOnTopHint)
        window.set_always_on_top(False)
        self.assertFalse(window.windowFlags() & Qt.WindowStaysOnTopHint)

    def test_the_window_survives_the_flag_change(self):
        """Changing window flags hides a visible window in Qt."""
        window = self._window()
        window.show()
        self.assertTrue(window.isVisible())
        window.set_always_on_top(False)
        self.assertTrue(window.isVisible(), "the window vanished when toggled")

    def test_geometry_survives_the_flag_change(self):
        window = self._window()
        window.show()
        window.setGeometry(120, 130, 900, 640)
        window.set_always_on_top(False)
        self.assertEqual(window.geometry().width(), 900)
        self.assertEqual(window.geometry().height(), 640)

    def test_the_settings_switch_is_connected_to_the_window(self):
        window = self._window(always_on_top=True)
        row = window.tab_pages["settings"].row_ontop
        row.set_checked(False)
        self.assertFalse(window.windowFlags() & Qt.WindowStaysOnTopHint)


class SurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, **cfg):
        from ui.qt.main_window import LeagueLoopMainWindow

        container = Container(**cfg)
        self.addCleanup(container.shutdown)
        window = LeagueLoopMainWindow(container=container)
        window.show()
        return window

    def test_a_minimised_window_is_restored(self):
        window = self._window()
        window.showMinimized()
        window._surface()
        self.assertFalse(window.isMinimized())

    def test_stealth_mode_suppresses_it(self):
        window = self._window(stealth_mode=True)
        window.showMinimized()
        window._surface()
        self.assertTrue(
            window.isMinimized(), "stealth mode should not pop the window up"
        )

    def test_focus_is_not_stolen_by_default(self):
        """Raising over the game while you are typing is worse than hiding."""
        import inspect
        from ui.qt.main_window import LeagueLoopMainWindow

        source = inspect.getsource(LeagueLoopMainWindow._surface)
        self.assertIn("take_focus", source)
        self.assertIn("def _surface(self, take_focus: bool = False)", source)

    def test_the_draft_surfaces_the_window(self):
        from core.state import GameflowPhase

        window = self._window()
        calls = []
        window._surface = lambda *a, **k: calls.append(1)
        window._on_phase_changed(GameflowPhase.CHAMP_SELECT.value)
        self.assertEqual(calls, [1])

    def test_a_ready_check_surfaces_the_window(self):
        from core.state import GameflowPhase

        window = self._window()
        calls = []
        window._surface = lambda *a, **k: calls.append(1)
        window._on_phase_changed(GameflowPhase.READY_CHECK.value)
        self.assertEqual(calls, [1])

    def test_an_idle_phase_does_not(self):
        from core.state import GameflowPhase

        window = self._window()
        calls = []
        window._surface = lambda *a, **k: calls.append(1)
        window._on_phase_changed(GameflowPhase.NONE.value)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
