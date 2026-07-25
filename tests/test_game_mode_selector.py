import unittest
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from ui.qt.pages.play_page import PlayPage


class TestGameModeSelector(unittest.TestCase):

    def setUp(self):
        self.page = PlayPage()

    def test_game_mode_combobox_initial_state(self):
        current_text = self.page.combo_mode.currentText()
        self.assertTrue(len(current_text) > 0)
        self.assertIn("ARAM", [self.page.combo_mode.itemText(i) for i in range(self.page.combo_mode.count())])

    def test_game_mode_change_updates_config(self):
        self.page.combo_mode.setCurrentText("Ranked Solo/Duo")
        saved_mode = self.page.viewmodel.config.get("aram_mode")
        self.assertEqual(saved_mode, "Ranked Solo/Duo")


if __name__ == "__main__":
    unittest.main()
