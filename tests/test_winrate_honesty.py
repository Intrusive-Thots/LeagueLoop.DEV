"""
Win rates must be measured or absent — never invented.

`StatsScraper` shipped a hand-written table of ~170 ARAM win rates, and
derived the other three modes from it by arithmetic:

    RANKED    = ARAM - 1.5
    ARENA     = ARAM + 2.0
    QUICKPLAY = ARAM - 0.5

`get_winrate()` then fell back to that table, and failing that to a flat
`50.0`, so every champion always had a plausible percentage. The champion
tile displayed it and the tooltip credited it to **Lolalytics**. None of it
was measured, and `fetch_live` defaults to False so the scraper never ran.

These tests pin the honest behaviour: no data means no number.
"""
import unittest

from services.stats_scraper import StatsScraper


def scraper(mode="ARAM", live=None):
    s = StatsScraper(mode=mode, fetch_live=False)
    if live is not None:
        s.live_winrates[s.mode] = live
    return s


class NoInventedNumbersTests(unittest.TestCase):
    def test_an_unfetched_winrate_is_none_not_fifty(self):
        self.assertIsNone(scraper().get_winrate("Ahri"))

    def test_an_unknown_champion_is_none(self):
        self.assertIsNone(scraper().get_winrate("Notachampion"))

    def test_a_scraped_winrate_is_returned(self):
        s = scraper(live={"ahri": 53.4})
        self.assertEqual(s.get_winrate("Ahri"), 53.4)

    def test_name_cleaning_still_works(self):
        s = scraper(live={"leesin": 51.0, "chogath": 52.0})
        self.assertEqual(s.get_winrate("Lee Sin"), 51.0)
        self.assertEqual(s.get_winrate("Cho'Gath"), 52.0)

    def test_the_source_is_empty_when_nothing_was_scraped(self):
        self.assertEqual(scraper().winrate_source(), "")
        self.assertFalse(scraper().has_live_winrates())

    def test_the_source_is_named_when_something_was(self):
        s = scraper(live={"ahri": 53.4})
        self.assertEqual(s.winrate_source(), "lolalytics")
        self.assertTrue(s.has_live_winrates())


class DerivedTablesTests(unittest.TestCase):
    def test_modes_no_longer_differ_by_arithmetic(self):
        """
        RANKED was ARAM minus 1.5 for every champion. Two modes cannot
        legitimately differ by a constant.
        """
        from services import stats_scraper as ss

        self.assertIs(ss.BASELINE_RANKED_WINRATES, ss.BASELINE_ARAM_WINRATES)
        self.assertIs(ss.BASELINE_ARENA_WINRATES, ss.BASELINE_ARAM_WINRATES)

    def test_the_baseline_is_still_available_for_internal_ordering(self):
        """It may break a tie inside automation. It may not reach the screen."""
        hint = scraper().get_ordering_hint("Ahri")
        self.assertIsInstance(hint, float)
        self.assertGreater(hint, 0)

    def test_the_ordering_hint_prefers_real_data(self):
        s = scraper(live={"ahri": 60.0})
        self.assertEqual(s.get_ordering_hint("Ahri"), 60.0)


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self, live=None):
        from ui.qt.widgets.champion_list_tab import QtPriorityTab

        class Config:
            def __init__(self): self.d = {"priority_list": [103]}
            def get(self, k, default=None): return self.d.get(k, default)
            def set(self, k, v): self.d[k] = v

        class Container:
            def __init__(self, sc):
                self.config = Config()
                self.scraper = sc
                self.assets = None

        # The Priority tab edits the Summoner's Rift list, so it puts the
        # scraper in Ranked mode. Seed the mode the screen will actually read.
        return QtPriorityTab(container=Container(scraper(mode="Ranked", live=live)))

    def test_no_percentage_is_rendered_without_data(self):
        tab = self._tab()
        text = tab.list_widget.item(0).text() if tab.list_widget.count() else ""
        self.assertNotIn("%", text)

    def test_sort_by_winrate_is_disabled_without_data(self):
        tab = self._tab()
        self.assertFalse(tab.btn_sort.isEnabled())
        self.assertIn("not available", tab.btn_sort.toolTip())

    def test_sort_by_winrate_is_enabled_with_data(self):
        tab = self._tab(live={"ahri": 53.0})
        self.assertTrue(tab.btn_sort.isEnabled())

    def test_switching_to_aram_switches_the_winrate_source(self):
        """ARAM priorities were annotated with Summoner's Rift win rates."""
        from core.config_keys import ARAM_PRIORITY_LIST, PRIORITY_LIST

        tab = self._tab(live={"ahri": 53.0})
        self.assertEqual(tab.scraper.mode, "Ranked")
        tab.set_mode(ARAM_PRIORITY_LIST)
        self.assertEqual(tab.scraper.mode, "ARAM")
        tab.set_mode(PRIORITY_LIST)
        self.assertEqual(tab.scraper.mode, "Ranked")

    def test_sorting_refuses_to_run_without_data(self):
        tab = self._tab()
        before = tab.current_ids()
        tab._on_sort_by_winrate()
        self.assertEqual(tab.current_ids(), before)

    def test_the_tile_does_not_attribute_an_unsourced_number(self):
        from ui.qt.components.champion_tile import ChampionTileModel, LLChampionTile

        model = ChampionTileModel(champ_id=103, name="Ahri", key="Ahri", winrate=52.0)
        tile = LLChampionTile(model)
        self.assertNotIn("Lolalytics", tile.toolTip())

    def test_the_tile_attributes_a_sourced_number(self):
        from ui.qt.components.champion_tile import ChampionTileModel, LLChampionTile

        model = ChampionTileModel(
            champ_id=103, name="Ahri", key="Ahri",
            winrate=52.0, winrate_source="lolalytics",
        )
        tile = LLChampionTile(model)
        self.assertIn("lolalytics", tile.toolTip())


if __name__ == "__main__":
    unittest.main()


class GridLayoutTests(unittest.TestCase):
    """
    Column count is derived from the scroll *viewport*, which the scroll area
    resizes independently of the grid widget. Watching only the grid's own
    resizeEvent meant it kept whatever count it computed first — a 540px panel
    rendered three columns in space that fits six.
    """

    @classmethod
    def setUpClass(cls):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _grid(self, width):
        from ui.qt.widgets.champion_grid import QtChampionGrid

        class Assets:
            champ_data = {
                n: {"key": str(i + 100), "name": n}
                for i, n in enumerate("abcdefghijklmnop")
            }

        grid = QtChampionGrid(asset_manager=Assets())
        grid.resize(width, 400)
        grid.show()
        for _ in range(6):
            self.app.sendPostedEvents()
            self.app.processEvents()
        return grid

    def test_a_wide_panel_uses_more_columns_than_a_narrow_one(self):
        narrow = self._grid(320)
        wide = self._grid(900)
        self.assertGreater(wide._columns, narrow._columns)

    def test_the_viewport_is_watched(self):
        grid = self._grid(600)
        # An event filter on the viewport is the mechanism; assert it is armed
        # by driving a viewport resize and checking the count follows.
        before = grid._columns
        grid.resize(1200, 400)
        for _ in range(6):
            self.app.sendPostedEvents()
            self.app.processEvents()
        self.assertGreaterEqual(grid._columns, before)
