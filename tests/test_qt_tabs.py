import os
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestQtTabWidgets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from core.container import ApplicationContainer
        self.container = ApplicationContainer()

    def tearDown(self):
        self.container.shutdown()

    def test_play_tab_initialization_and_toggles(self):
        from ui.qt.widgets.play_tab import QtPlayTab

        tab = QtPlayTab(container=self.container)
        self.assertIsNotNone(tab.chk_auto_accept)
        self.assertIsNotNone(tab.chk_auto_lock)
        self.assertIsNotNone(tab.btn_find_match)

        # Toggle setting
        tab.chk_auto_accept.setChecked(True)
        self.assertTrue(self.container.config.get("auto_accept"))
        tab.chk_auto_accept.setChecked(False)
        self.assertFalse(self.container.config.get("auto_accept"))

        tab.update_phase("ChampSelect")
        self.assertIn("ChampSelect", tab.phase_indicator.text())

    def test_diagnostics_tab_and_match_history(self):
        from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab

        # Insert a sample match into DB
        self.container.db.record_match({
            "game_id": 999111,
            "champion_id": 103,
            "champion_name": "Ahri",
            "win": True,
            "kills": 12,
            "deaths": 1,
            "assists": 8,
            "duration_s": 1500,
            "queue_id": 420,
        })

        tab = QtDiagnosticsTab(container=self.container)
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(tab.table.item(0, 1).text(), "Ahri")
        self.assertEqual(tab.table.item(0, 2).text(), "WIN")

        # Test prune button doesn't raise
        tab.btn_prune_cache.click()

    def test_settings_tab_and_status_save(self):
        from ui.qt.widgets.settings_tab import QtSettingsTab

        tab = QtSettingsTab(container=self.container)
        self.assertIsNotNone(tab.chk_stealth)
        self.assertIsNotNone(tab.spin_delay)
        self.assertIsNotNone(tab.txt_status)

        tab.chk_stealth.setChecked(True)
        self.assertTrue(self.container.config.get("stealth_mode"))

        tab.spin_delay.setValue(3.5)
        self.assertEqual(self.container.config.get("accept_delay"), 3.5)

        tab.txt_status.setText("Chilling in Challenger")
        tab.btn_save_status.click()
        self.assertEqual(self.container.config.get("custom_status"), "Chilling in Challenger")

    def test_champion_grid_and_priority_tab(self):
        from ui.qt.widgets.champion_grid import QtChampionGrid
        from ui.qt.widgets.priority_tab import QtPriorityTab

        grid = QtChampionGrid(asset_manager=self.container.assets)
        self.assertGreater(len(grid.tiles), 0)

        # Test search filter
        grid.search_input.setText("Ahri")
        self.assertEqual(grid.search_query, "ahri")

        # Test Priority Tab
        prio_tab = QtPriorityTab(container=self.container)
        self.assertIsNotNone(prio_tab.grid)
        self.assertIsNotNone(prio_tab.prio_list_widget)

        # Select a champion
        prio_tab._on_champion_clicked(103, "Ahri")
        self.assertIn(103, self.container.config.get("priority_list"))


if __name__ == "__main__":
    unittest.main()
