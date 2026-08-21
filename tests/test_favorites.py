"""
Favourites.

The champion grid shipped a **Favourites** filter chip, a star badge on the
tile, and a context-menu action to toggle one. None of it worked:

* the tile's `context_menu_requested` was re-emitted as
  `champion_context_menu` and nothing listened, including the grid's own
  handler — so right-clicking a champion did nothing at all;
* `_toggle_favorite()` mutated an in-memory set and nothing else, so even a
  reachable toggle was gone on the next launch;
* `set_favorites()` was never called by anything, so favourites never loaded;
* there was no config key for them.

A filter with no way to fill it is worse than no filter: it reads as a broken
feature and makes the working ones look unreliable too.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from core.config_keys import FAVORITE_CHAMPIONS

AHRI, GAREN, JINX = 103, 86, 222


class FakeConfig:
    def __init__(self, **values):
        self.values = dict(values)

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class FakeAssets:
    champ_data = {
        "Ahri": {"key": "103", "name": "Ahri"},
        "Garen": {"key": "86", "name": "Garen"},
        "Jinx": {"key": "222", "name": "Jinx"},
    }
    id_to_key = {103: "Ahri", 86: "Garen", 222: "Jinx"}

    def get_champ_name(self, cid):
        return {103: "Ahri", 86: "Garen", 222: "Jinx"}.get(int(cid), "")


class FavoritesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _grid(self, config=None):
        from ui.qt.widgets.champion_grid import QtChampionGrid

        self.config = config if config is not None else FakeConfig()
        grid = QtChampionGrid(asset_manager=FakeAssets(), config=self.config)
        grid.load_champions()
        return grid

    # ---------------------------------------------------------- reachable
    def test_right_click_reaches_the_grids_own_menu(self):
        """The signal was re-emitted for callers that never existed."""
        import inspect
        from ui.qt.widgets import champion_grid

        source = inspect.getsource(champion_grid.QtChampionGrid.load_champions)
        self.assertIn("self._show_champion_context_menu", source)

    def test_the_toggle_marks_the_tile(self):
        grid = self._grid()
        self.assertFalse(grid.tiles[AHRI].model.favorite)
        grid._toggle_favorite("Ahri")
        self.assertTrue(grid.tiles[AHRI].model.favorite)

    # ------------------------------------------------------------ storage
    def test_a_favourite_is_persisted_as_an_id(self):
        grid = self._grid()
        grid._toggle_favorite("Ahri")
        self.assertEqual(self.config.get(FAVORITE_CHAMPIONS), [AHRI])

    def test_unfavouriting_persists_too(self):
        grid = self._grid()
        grid._toggle_favorite("Ahri")
        grid._toggle_favorite("Ahri")
        self.assertEqual(self.config.get(FAVORITE_CHAMPIONS), [])

    def test_favourites_survive_a_restart(self):
        config = FakeConfig(**{FAVORITE_CHAMPIONS: [AHRI, JINX]})
        grid = self._grid(config)
        self.assertTrue(grid.tiles[AHRI].model.favorite)
        self.assertTrue(grid.tiles[JINX].model.favorite)
        self.assertFalse(grid.tiles[GAREN].model.favorite)

    def test_a_stale_id_is_ignored_not_fatal(self):
        config = FakeConfig(**{FAVORITE_CHAMPIONS: [AHRI, 999999, "junk"]})
        grid = self._grid(config)
        self.assertTrue(grid.tiles[AHRI].model.favorite)

    def test_no_config_still_builds(self):
        from ui.qt.widgets.champion_grid import QtChampionGrid

        grid = QtChampionGrid(asset_manager=FakeAssets())
        grid.load_champions()
        grid._toggle_favorite("Ahri")  # must not raise
        self.assertTrue(grid.tiles[AHRI].model.favorite)

    # ------------------------------------------------------------- filter
    def test_the_filter_shows_only_favourites(self):
        grid = self._grid()
        grid._toggle_favorite("Ahri")
        grid.quick_filter = "FAVORITES"
        grid._apply_filters()
        self.assertEqual(grid._visible_ids, [AHRI])

    def test_an_empty_favourites_filter_explains_how_to_add_one(self):
        grid = self._grid()
        grid.quick_filter = "FAVORITES"
        grid._apply_filters()
        text = grid.empty_label.text()
        self.assertIn("No favourites yet", text)
        self.assertIn("Right-click", text)

    def test_the_change_is_announced(self):
        grid = self._grid()
        seen = []
        grid.favorites_changed.connect(lambda keys: seen.append(list(keys)))
        grid._toggle_favorite("Ahri")
        self.assertEqual(seen, [["Ahri"]])


if __name__ == "__main__":
    unittest.main()
