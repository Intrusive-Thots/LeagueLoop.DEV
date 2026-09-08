"""
The ARAM Picker must obey its switch, and must not fight the player.

All three of these were reported together and are one experience: "sometimes
it doesn't pick, sometimes it picks and I can't turn it off, and it keeps
switching back to the champion it chose even though the icon says off."

Every number here comes from the user's own debug log.
"""
import os
import unittest

os.environ.setdefault("PYSTRAY_BACKEND", "dummy")


class Assets:
    NAMES = {38: "Kassadin", 78: "Poppy", 33: "Rammus", 17: "Teemo"}

    def get_champ_name(self, cid):
        return self.NAMES.get(cid, str(cid))


class Engine:
    """The sniper, lifted off AutomationEngine without its constructor."""

    def __init__(self):
        from services.automation import AutomationEngine

        self.assets = Assets()
        self.swaps = []
        self.logs = []
        self._last_priority_swap = 0.0
        self._sniper_picked_id = 0
        self._sniper_overridden = False
        self._skin_equipped = False
        self._perform = AutomationEngine._perform_priority_sniper.__get__(self)
        self._get_local_player = AutomationEngine._get_local_player.__get__(self)

    def _log(self, message):
        self.logs.append(message)

    def _act(self, method, endpoint, what="", **detail):
        self.swaps.append(int(endpoint.rsplit("/", 1)[-1]))
        return True


def session(my_champ, bench):
    return {
        "localPlayerCellId": 0,
        "myTeam": [{"cellId": 0, "championId": my_champ}],
        "benchChampions": [{"championId": c} for c in bench],
    }


PRIORITY = ["Poppy", "Rammus", "Kassadin", "Teemo"]


class SniperStandsDownTests(unittest.TestCase):
    """The log shows it swapping to Poppy at 00:39:57, 00:40:08 and 00:40:16 —
    three times in nineteen seconds, because the player kept swapping away and
    it kept swapping back."""

    def setUp(self):
        self.engine = Engine()

    def test_it_swaps_to_the_best_bench_champion(self):
        self.engine._perform(session(17, [78, 33]), PRIORITY)
        self.assertEqual(self.engine.swaps, [78])

    def test_it_does_not_swap_back_after_the_player_overrides_it(self):
        """The bug, exactly: pick Poppy, player takes Teemo, Poppy is back on
        the bench and still ranked higher — so it took Poppy again."""
        self.engine._perform(session(17, [78, 33]), PRIORITY)
        self.assertEqual(self.engine.swaps, [78])

        # Player swaps away; the cooldown has passed.
        self.engine._last_priority_swap = 0.0
        self.engine._perform(session(17, [78, 33]), PRIORITY)

        self.assertEqual(
            self.engine.swaps, [78], "it swapped back over the player's choice"
        )
        self.assertTrue(self.engine._sniper_overridden)

    def test_standing_down_is_explained_not_silent(self):
        self.engine._perform(session(17, [78, 33]), PRIORITY)
        self.engine._last_priority_swap = 0.0
        self.engine._perform(session(17, [78, 33]), PRIORITY)
        self.assertTrue(
            any("standing down" in m.lower() for m in self.engine.logs),
            self.engine.logs,
        )

    def test_it_stays_stood_down_for_the_rest_of_the_draft(self):
        self.engine._perform(session(17, [78, 33]), PRIORITY)
        self.engine._last_priority_swap = 0.0
        self.engine._perform(session(17, [78, 33]), PRIORITY)
        for _ in range(5):
            self.engine._last_priority_swap = 0.0
            self.engine._perform(session(17, [78, 33]), PRIORITY)
        self.assertEqual(len(self.engine.swaps), 1)

    def test_keeping_the_champion_it_chose_is_not_an_override(self):
        """Standing down on its own pick would disable it for no reason."""
        self.engine._perform(session(17, [78, 33]), PRIORITY)
        self.engine._last_priority_swap = 0.0
        # Still on Poppy; only Rammus left on the bench, which is a downgrade.
        self.engine._perform(session(78, [33]), PRIORITY)
        self.assertFalse(self.engine._sniper_overridden)
        self.assertEqual(self.engine.swaps, [78])

    def test_a_cooldown_alone_could_never_have_fixed_this(self):
        """The situation is identical every time the cooldown expires, which
        is why the original guard did not help."""
        import inspect

        from services.automation import AutomationEngine

        body = inspect.getsource(AutomationEngine._perform_priority_sniper)
        self.assertIn("_sniper_overridden", body)


class OneSwitchTests(unittest.TestCase):
    """`aram_bench_swap OR priority_picker.enabled` meant either flag could
    enable the feature and neither could disable it."""

    def test_the_engine_reads_one_key_only(self):
        import inspect

        from services.automation import AutomationEngine

        body = inspect.getsource(AutomationEngine._handle_champ_select)
        self.assertNotIn(
            'self.config.get("aram_bench_swap"', body,
            "the retired flag can still force the sniper on",
        )
        self.assertIn('priority_cfg.get("enabled"', body)


class MigrationTests(unittest.TestCase):
    """Nothing can clear `aram_bench_swap` any more — the Qt screen that wrote
    it is gone — so it must not be left able to affect anything."""

    def _manager(self, cfg):
        from services.config_manager import ConfigManager

        manager = ConfigManager.__new__(ConfigManager)
        manager.cfg = dict(cfg)
        manager.save = lambda: None
        return manager

    def test_an_enabled_legacy_flag_is_folded_into_the_live_setting(self):
        manager = self._manager({"aram_bench_swap": True})
        self.assertEqual(manager.migrate_legacy_keys(), ["aram_bench_swap"])
        self.assertTrue(manager.cfg["priority_picker"]["enabled"])
        self.assertNotIn("aram_bench_swap", manager.cfg)

    def test_a_disabled_legacy_flag_does_not_switch_anything_on(self):
        manager = self._manager(
            {"aram_bench_swap": False, "priority_picker": {"enabled": False}}
        )
        manager.migrate_legacy_keys()
        self.assertFalse(manager.cfg["priority_picker"]["enabled"])
        self.assertNotIn("aram_bench_swap", manager.cfg)

    def test_it_does_not_clobber_the_rest_of_the_priority_settings(self):
        manager = self._manager({
            "aram_bench_swap": True,
            "priority_picker": {"enabled": False, "list": ["Poppy", "Teemo"]},
        })
        manager.migrate_legacy_keys()
        self.assertEqual(manager.cfg["priority_picker"]["list"], ["Poppy", "Teemo"])

    def test_a_config_without_the_legacy_key_is_left_alone(self):
        manager = self._manager({"priority_picker": {"enabled": True}})
        self.assertEqual(manager.migrate_legacy_keys(), [])


class PulseTests(unittest.TestCase):
    """`_start_pulse` passed "" as a colour: `unknown color name ""`, caught
    and logged 6,335 times in one session."""

    def test_no_empty_colour_is_ever_passed(self):
        from pathlib import Path

        body = (Path(__file__).resolve().parent.parent / "src" / "ui" /
                "components" / "toggle_row.py").read_text(encoding="utf-8")
        self.assertNotIn('text_color=get_color("colors.accent.gold") if not', body)

    def test_both_halves_of_the_pulse_are_real_colours(self):
        from ui.components.toggle_row import PULSE_DIM_GOLD

        self.assertTrue(PULSE_DIM_GOLD.startswith("#"))
        self.assertEqual(len(PULSE_DIM_GOLD), 7)


if __name__ == "__main__":
    unittest.main()
