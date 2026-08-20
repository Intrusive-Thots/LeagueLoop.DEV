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
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.temp_dir.name, "test_qt_tabs.db")
        from core.container import ApplicationContainer
        self.container = ApplicationContainer(db_path=db_path)

    def tearDown(self):
        self.container.shutdown()
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

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

    def _assets(self, champ_data):
        class FakeAssets:
            def __init__(self):
                self.champ_data = champ_data
        return FakeAssets()

    def test_champion_grid_renders_real_champion_data(self):
        from ui.qt.widgets.champion_grid import QtChampionGrid

        assets = self._assets({
            "Ahri": {"key": "103", "name": "Ahri"},
            "Garen": {"key": "86", "name": "Garen"},
        })
        grid = QtChampionGrid(asset_manager=assets)
        grid.load_champions()

        self.assertEqual(sorted(grid.tiles), [86, 103])

        grid.search_input.setText("Ahri")
        self.assertEqual(grid.search_query, "ahri")

    def test_grid_invents_nothing_when_champion_data_is_missing(self):
        """
        There used to be a hardcoded list of twelve champions here, so a
        machine whose assets had not downloaded showed a plausible roster
        that was not the user's. This test exists to keep it gone.
        """
        from ui.qt.widgets.champion_grid import QtChampionGrid

        grid = QtChampionGrid(asset_manager=self._assets({}))
        grid.load_champions()

        self.assertEqual(grid.tiles, {})
        self.assertTrue(grid.empty_label.isVisibleTo(grid))
        self.assertIn("not loaded", grid.empty_label.text().lower())

    def test_empty_search_and_missing_data_say_different_things(self):
        from ui.qt.widgets.champion_grid import QtChampionGrid

        grid = QtChampionGrid(asset_manager=self._assets(
            {"Ahri": {"key": "103", "name": "Ahri"}}
        ))
        grid.load_champions()
        grid.search_input.setText("zzzzzz")
        self.assertIn("match your search", grid.empty_label.text().lower())

    def test_priority_tab(self):
        from ui.qt.widgets.priority_tab import QtPriorityTab

        # Test Priority Tab
        prio_tab = QtPriorityTab(container=self.container)
        self.assertIsNotNone(prio_tab.grid)
        self.assertIsNotNone(prio_tab.prio_list_widget)

        # Select a champion
        prio_tab._on_champion_clicked(103, "Ahri")
        self.assertIn(103, self.container.config.get("priority_list"))


if __name__ == "__main__":
    unittest.main()
