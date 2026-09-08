"""`AssetManager.search_item_*_recommendations` invents win rates. Keep it unwired.

There are 21 of these methods — build, build_order, upgrade_tree, path,
counter_build, flex_build, core_build, starter, boots, legendary, mythic,
support, ap, capstone, luxury, situational, defensive, offensive, hybrid,
utility. Every one filters the champion index and then attaches numbers that
were typed into the source:

    "situational_item": "Quicksilver Sash",
    "win_rate_pct": 58.4,
    "pick_rate_pct": 34.2,

The same literals come back for every champion, ignoring `query`, `champ_id`
and `role`. They are not measurements of anything. Their docstrings say what
they are actually for — "Benchmark and optimize memory pooling for ... slice
tuple creation" — so the payload is filler around a memory-pooling
experiment.

Today nothing outside the tests calls any of them, so no user can see the
numbers. That is the only reason this is not already a live bug, and it is
exactly the situation `_FALLBACK_CHAMPIONS` was in before someone rendered
it: twelve invented champions shown as the user's roster, with a test that
passed *because* of the fake data.

So this guard is deliberately narrow. It does not ask anyone to delete the
methods. It asks that if one is ever wired into a screen, the fabricated
stats are dealt with in that same change — because the alternative is
shipping "54.2% win rate" for a champion nobody measured.

If you are here because this test failed: remove `win_rate_pct`,
`pick_rate_pct` and the hardcoded item names from the method you are wiring
up, or source them from `StatsScraper` and label them as community
aggregate data. Then delete that method's name from FABRICATES_STATS below.
"""

import ast
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ASSET_MANAGER = SRC / "services" / "asset_manager.py"

FABRICATED_KEYS = ("win_rate_pct", "pick_rate_pct", "ban_rate_pct")


def _methods_returning_invented_stats():
    """Every search_item_*_recommendations that hardcodes a rate literal."""
    tree = ast.parse(ASSET_MANAGER.read_text(encoding="utf-8-sig"))
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not re.fullmatch(r"search_item_\w*recommendations", node.name):
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Dict):
                continue
            for key, value in zip(sub.keys, sub.values):
                if not isinstance(key, ast.Constant) or key.value not in FABRICATED_KEYS:
                    continue
                if isinstance(value, ast.Constant) and isinstance(
                    value.value, (int, float)
                ):
                    found[node.name] = node.lineno
    return found


class FabricatedBuildStatsTests(unittest.TestCase):

    def test_the_inventory_is_accurate(self):
        """If a method stopped inventing stats, shrink the list below."""
        found = _methods_returning_invented_stats()
        self.assertTrue(
            found,
            "no method hardcodes a win/pick rate any more — good. Delete this "
            "file, and the guard below with it.",
        )

    def test_none_of_them_is_reachable_from_the_application(self):
        """Nothing outside asset_manager.py and tests/ may call these."""
        fabricators = set(_methods_returning_invented_stats())

        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            if path == ASSET_MANAGER:
                continue
            text = path.read_text(encoding="utf-8-sig")
            for number, line in enumerate(text.splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                for name in fabricators:
                    if name + "(" in line:
                        offenders.append(
                            "%s:%d calls %s"
                            % (path.relative_to(ROOT), number, name)
                        )

        self.assertEqual(
            offenders, [],
            "these methods return hardcoded win/pick rates for every "
            "champion; wiring one into the app ships invented statistics as "
            "though they were measured. Strip the fabricated fields (or "
            "source them from StatsScraper and label them as community "
            "data) in the same change: %s" % offenders,
        )


if __name__ == "__main__":
    unittest.main()
