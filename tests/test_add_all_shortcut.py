import unittest
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from ui.qt.pages.coach_page import RolePriorityListWidget


class TestAddAllShortcut(unittest.TestCase):

    def setUp(self):
        self.widget = RolePriorityListWidget(role="TOP")
        self.widget.active_champs = ["Aatrox"]
        self.widget._save_role_champs()

    def test_add_all_shortcut(self):
        self.widget.entry_add.setText("#all")
        self.widget._add_champion()

        # Check that active champions list now contains many champions (> 10)
        self.assertGreater(len(self.widget.active_champs), 10)
        self.assertIn("Aatrox", self.widget.active_champs)
        self.assertIn("Darius", self.widget.active_champs)


if __name__ == "__main__":
    unittest.main()
