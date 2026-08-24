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


if __name__ == "__main__":
    unittest.main()
