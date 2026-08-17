import os
import unittest

from ui.qt.theme import (
    COLOR_BACKGROUND_DARK,
    COLOR_GOLD_PRIMARY,
    COLOR_BLUE_ACCENT,
    get_global_stylesheet,
)

# Ensure offscreen rendering for headless test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestQtThemeAndComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_theme_constants_and_stylesheet(self):
        self.assertEqual(COLOR_BACKGROUND_DARK, "#010A13")
        self.assertEqual(COLOR_GOLD_PRIMARY, "#C8AA6E")
        self.assertEqual(COLOR_BLUE_ACCENT, "#0AC8B9")

        qss = get_global_stylesheet()
        self.assertIn("#010A13", qss)
        self.assertIn("#C8AA6E", qss)
        self.assertIn("QPushButton", qss)

    def test_sidebar_widget_instantiation(self):
        from ui.qt.widgets.navigation.sidebar import QtNavigationSidebar

        sidebar = QtNavigationSidebar()
        self.assertEqual(len(sidebar.buttons), 7)
        self.assertIn("play", sidebar.buttons)
        self.assertIn("settings", sidebar.buttons)

        # Test tab selection signal
        received = []
        sidebar.tab_selected.connect(lambda k: received.append(k))
        sidebar.select_tab("aram")
        self.assertIn("aram", received)

    def test_main_window_instantiation(self):
        from ui.qt.main_window import LeagueLoopMainWindow

        window = LeagueLoopMainWindow()
        self.assertEqual(window.width(), 960)
        self.assertEqual(window.height(), 640)
        self.assertIsNotNone(window.sidebar)
        self.assertIsNotNone(window.tab_stack)
        window.close()


if __name__ == "__main__":
    unittest.main()
