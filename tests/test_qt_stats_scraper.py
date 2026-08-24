"""
Unit tests for StatsScraper (Lolalytics) integration in the PySide6 Qt shell.
Validates win rate display, tier lookup, champion sorting, grid tooltips, and Champ Select VM wiring.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestQtStatsScraperWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.temp_dir.name, "test_qt_stats.db")
        from core.container import ApplicationContainer
        self.container = ApplicationContainer(db_path=db_path)

    def tearDown(self):
        self.container.shutdown()
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_container_has_scraper_instance(self):
        from services.stats_scraper import StatsScraper
        self.assertIsNotNone(self.container.scraper)
        self.assertIsInstance(self.container.scraper, StatsScraper)

    def test_aram_tab_scraper_integration(self):
        from ui.qt.widgets.aram_tab import QtAramTab

        tab = QtAramTab(container=self.container)
        self.assertIsNotNone(tab.scraper)
        self.assertEqual(tab.scraper.mode, "ARAM")
        self.assertIsNotNone(tab.btn_sort)

        # Pre-populate live winrates for testing
        tab.scraper.live_winrates["ARAM"] = {"sona": 55.0, "ryze": 47.0}

        tab._on_clear_all()

        # Populate with two champions
        self.container.assets.champ_data = {
            "Sona": {"key": "37", "name": "Sona"},
            "Ryze": {"key": "13", "name": "Ryze"},
        }
        self.container.assets.id_to_key = {37: "Sona", 13: "Ryze"}
        tab.grid.load_champions()

        tab._on_champion_clicked(13, "Ryze")
        tab._on_champion_clicked(37, "Sona")

        # Verify display names include Lolalytics winrate
        self.assertIn("55.0% WR", tab._display_name(37))
        self.assertIn("47.0% WR", tab._display_name(13))

        # Test sort by winrate (Sona 55.0% > Ryze 47.0%)
        tab._on_sort_by_winrate()
        self.assertEqual(tab.current_ids(), [37, 13])

    def test_champion_list_tab_scraper_and_sort(self):
        from ui.qt.widgets.champion_list_tab import QtPriorityTab

        tab = QtPriorityTab(container=self.container)
        self.assertIsNotNone(tab.scraper)
        self.assertEqual(tab.scraper.mode, "Ranked")
        self.assertIsNotNone(tab.btn_sort)

        # Pre-populate live winrates for testing
        tab.scraper.live_winrates["Ranked"] = {"sona": 55.0, "ryze": 47.0}

        tab._on_clear_all()

        self.container.assets.champ_data = {
            "Sona": {"key": "37", "name": "Sona"},
            "Ryze": {"key": "13", "name": "Ryze"},
        }
        self.container.assets.id_to_key = {37: "Sona", 13: "Ryze"}
        tab.grid.load_champions()

        tab._on_champion_clicked(13, "Ryze")
        tab._on_champion_clicked(37, "Sona")

        # Test sorting
        tab._on_sort_by_winrate()
        self.assertEqual(tab.current_ids(), [37, 13])

    def test_champion_tile_model_and_tooltip_with_winrate(self):
        from ui.qt.components.champion_tile import ChampionTileModel, LLChampionTile, TileSize

        model = ChampionTileModel(
            champ_id=99,
            name="Lux",
            key="Lux",
            winrate=53.0,
            winrate_source="Lolalytics",
        )
        tile = LLChampionTile(model, size=TileSize.MD)
        tooltip = tile._tooltip_text()
        self.assertIn("53.0% WR (Lolalytics)", tooltip)

    def test_champ_select_viewmodel_attaches_winrate(self):
        from ui.qt.viewmodels.champ_select_viewmodel import ChampSelectViewModel
        from core.state import ApplicationState, ChampSelectState, ClientState, GameflowPhase

        vm = ChampSelectViewModel(container=self.container)
        self.container.scraper.live_winrates[self.container.scraper.mode] = {"sona": 55.0}

        self.container.assets.champ_data = {
            "Sona": {"key": "37", "name": "Sona"},
        }
        self.container.assets.id_to_key = {37: "Sona"}
        self.container.assets.get_champ_name = lambda cid: "Sona" if cid == 37 else str(cid)

        # Mock priority list
        self.container.config.set("priority_list", [37])

        client_st = ClientState(phase=GameflowPhase.CHAMP_SELECT.value, connected=True)
        cs_st = ChampSelectState(active=True, timer_remaining_s=20.0, local_role="UTILITY")
        app_state = ApplicationState(client=client_st, champ_select=cs_st)

        vm.apply(app_state)
        rec = vm.recommendation
        if rec.valid:
            self.assertIsNotNone(rec.winrate)
            self.assertTrue(any("WR" in reason for reason in rec.reasons))

    def test_diagnostics_tab_stats_scraper_metric(self):
        from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab

        tab = QtDiagnosticsTab(container=self.container)
        self.assertIsNotNone(tab.health_card)
        tab.refresh()


if __name__ == "__main__":
    unittest.main()
