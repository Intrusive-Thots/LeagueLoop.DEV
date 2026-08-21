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

    def test_play_tab_reports_automation_rather_than_duplicating_it(self):
        """
        Play used to carry four raw QCheckBoxes mirroring the Automation
        screen. They rendered as checkboxes while every other surface uses the
        painted switch, and they read config keys directly — so the card could
        say "off" while the header said "Automation on". Play now reports live
        state and links to the one screen that changes it.
        """
        from ui.qt.widgets.play_tab import QtPlayTab

        tab = QtPlayTab(container=self.container)
        self.assertIsNotNone(tab.btn_find_match)
        self.assertIsNotNone(tab.automation_status)
        self.assertIsNotNone(tab.btn_automation)

        for gone in ("chk_auto_accept", "chk_auto_lock", "chk_auto_requeue",
                     "chk_auto_skin"):
            self.assertFalse(hasattr(tab, gone),
                             "{} is back; Play is duplicating Automation".format(gone))

        tab.update_phase("ChampSelect")

    def test_play_tab_asks_the_shell_to_open_automation(self):
        from ui.qt.widgets.play_tab import QtPlayTab

        tab = QtPlayTab(container=self.container)
        seen = []
        tab.automation_requested.connect(lambda: seen.append(1))
        tab.btn_automation.click()
        self.assertEqual(seen, [1])

    def test_diagnostics_reports_health_not_telemetry(self):
        """
        Diagnostics used to be four counters that read zero on a fresh launch
        above an empty SQLite table, with "Prune Cache" as its only action.
        It now answers the question the page name implies.
        """
        from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab

        tab = QtDiagnosticsTab(container=self.container)
        keys = [key for key, _widget in tab._checks]
        self.assertEqual(
            keys, ["client", "accounts", "automation", "champions", "history"]
        )
        for _key, widget in tab._checks:
            self.assertTrue(widget.text(), "a health row rendered with no state")

    def test_a_disconnected_client_says_what_to_do(self):
        from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab

        tab = QtDiagnosticsTab(container=self.container)
        text, _tone, detail = tab._check_client()
        self.assertEqual(text, "Not connected")
        self.assertIn("League Client", detail)

    def test_missing_champion_data_is_flagged_as_a_problem(self):
        from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab

        tab = QtDiagnosticsTab(container=self.container)
        tab.assets = type("A", (), {"champ_data": {}, "champion_data_error": "boom"})()
        text, tone, detail = tab._check_champions()
        self.assertEqual(text, "Failed to load")
        self.assertEqual(detail, "boom")

    def test_developer_details_start_hidden(self):
        from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab

        tab = QtDiagnosticsTab(container=self.container)
        self.assertFalse(tab.details_card.isVisibleTo(tab))
        tab.btn_details.click()
        self.assertTrue(tab.details_card.isVisibleTo(tab))
        self.assertIn("Hide", tab.btn_details.text())

    def test_the_report_is_copyable_text(self):
        from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab

        tab = QtDiagnosticsTab(container=self.container)
        report = tab.report_text()
        self.assertIn("LeagueLoop diagnostics", report)
        self.assertIn("Client", report)
        # The detail line carries the actionable half; text() alone loses it.
        self.assertIn("League Client", report)

    def test_zero_latency_is_not_reported_as_a_measurement(self):
        from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab

        tab = QtDiagnosticsTab(container=self.container)
        tab._render_metrics()
        self.assertNotIn("0.0 ms", tab.metrics_label.text())

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
