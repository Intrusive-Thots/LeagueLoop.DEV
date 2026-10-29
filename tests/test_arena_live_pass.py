"""#23 pass 4: a live Bravery Arena draft (queue 1740) under the read-only launcher.

What the real session looked like (tests/fixtures/lcu/*arena_bravery*.json):
  * all 18 players in `myTeam` with `team: 1`; `theirTeam` empty;
  * 18 simultaneous pick actions, no bans; `hasSimultaneousPicks` True;
  * the local trio is cells 9-11, the only rows with visible spells/intent;
  * -3 is the Bravery placeholder (cell 9 and 11 locked it, cell 10 Ashe).

LeagueLoop missed queue 1740 as Arena, and its "teammate" was the first other
cell (a hidden stranger in cell 0), so synergy pairs could never fire.
"""
import json
import os
import unittest
from unittest.mock import MagicMock

from services.automation import AutomationEngine
from services.draft import arena

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "lcu")
ASHE, JINX, XAYAH = 22, 222, 498
NAMES = {ASHE: "Ashe", JINX: "Jinx", XAYAH: "Xayah", 223: "Tahm Kench", 11: "Master Yi"}


def _fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


class ArenaShape(unittest.TestCase):
    def test_bravery_queue_is_arena(self):
        self.assertTrue(arena.is_arena(1740))
        self.assertTrue(arena.is_arena(None, "CHERRY"))
        self.assertFalse(arena.is_arena(450, "ARAM"))
        gf = _fixture("gameflow_session_arena_bravery.json")
        q = gf["gameData"]["queue"]
        self.assertTrue(arena.is_arena(q["id"], q["gameMode"]))

    def test_teammates_are_the_visible_trio(self):
        s = _fixture("champ_select_arena_bravery_picking.json")
        self.assertEqual(len(s["myTeam"]), 18)
        self.assertEqual(s["theirTeam"], [])
        self.assertEqual(sorted(p["cellId"] for p in arena.teammates(s)), [10, 11])

    def test_bravery_placeholder_is_not_a_champion(self):
        s = _fixture("champ_select_arena_bravery_finalization.json")
        cells = {p["cellId"]: p for p in s["myTeam"]}
        self.assertEqual(cells[9]["championId"], -3)
        self.assertEqual(arena.champion_of(cells[9]), 0)
        self.assertEqual(arena.champion_of(cells[10]), ASHE)

    def test_partner_prefers_configured_pair_then_any_champion(self):
        s = _fixture("champ_select_arena_bravery_teammate_hovers.json")
        p = arena.partner_target(s, {"ashe"}, NAMES.get)
        self.assertEqual(p["cellId"], 10)
        # No pair: first teammate with a real champion (cell 11 is on -3).
        self.assertEqual(arena.partner_target(s)["cellId"], 10)

    def test_old_two_team_shape_still_works(self):
        s = {"localPlayerCellId": 0, "myTeam": [{"cellId": 0}, {"cellId": 1, "championPickIntent": 5}],
             "theirTeam": [{"cellId": 2}]}
        self.assertEqual([p["cellId"] for p in arena.teammates(s)], [1])


def _engine(cfg):
    eng = AutomationEngine(lcu=MagicMock(), assets=MagicMock(), config=MagicMock(), log_func=MagicMock())
    eng.config.get.side_effect = lambda k, d=None: cfg.get(k, d)
    eng.assets.get_champ_name.side_effect = lambda cid: NAMES.get(cid, "")
    eng.assets.name_to_id = {v.lower(): k for k, v in NAMES.items()}
    eng.assets.get_champ_id = lambda n: eng.assets.name_to_id.get(str(n).lower(), 0)
    eng._act = MagicMock()
    return eng


class ArenaSynergyOnRealSession(unittest.TestCase):
    def test_hovers_the_pair_for_the_real_partner(self):
        eng = _engine({"arena_pairs": [{"teammate": "Ashe", "me": ["Jinx"], "enabled": True}]})
        eng._perform_arena_synergy(_fixture("champ_select_arena_bravery_teammate_hovers.json"))
        self.assertTrue(eng._act.called, "pair for partner Ashe never fired")
        method, endpoint, body = eng._act.call_args.args[:3]
        self.assertEqual(method, "PATCH")
        self.assertTrue(endpoint.endswith("/actions/%d" % 9) or "/actions/" in endpoint)
        self.assertEqual(body.get("championId"), JINX)
        self.assertFalse(body.get("completed", False))  # hover only, no lock

    def test_no_pair_no_fallback_does_nothing(self):
        eng = _engine({})
        eng._perform_arena_synergy(_fixture("champ_select_arena_bravery_teammate_hovers.json"))
        eng._act.assert_not_called()

    def test_locked_session_sends_nothing(self):
        # Every trio action is completed in finalization: nothing left to do.
        eng = _engine({"arena_pairs": [{"teammate": "Ashe", "me": ["Jinx"]}], "arena_auto_lock": True})
        eng._perform_arena_synergy(_fixture("champ_select_arena_bravery_finalization.json"))
        eng._act.assert_not_called()


class PausedEngineInArena(unittest.TestCase):
    def test_paused_arena_tick_sends_no_writes(self):
        eng = AutomationEngine(lcu=MagicMock(), assets=MagicMock(), config=MagicMock(), log_func=MagicMock())
        eng.config.get.side_effect = lambda k, d=None: True
        eng.paused = True
        eng.last_phase = "ChampSelect"
        session = _fixture("champ_select_arena_bravery_teammate_hovers.json")

        class R:
            def __init__(self, p, c=200):
                self.status_code, self._p = c, p

            def json(self):
                return self._p

        def req(method, ep, *a, **k):
            if "gameflow-phase" in ep:
                return R("ChampSelect")
            if "champ-select/v1/session" in ep:
                return R(session)
            return R({}, 200)
        eng.lcu.request.side_effect = req
        eng._is_game_running = MagicMock(return_value=False)
        eng._maybe_autosave_replay = MagicMock()
        eng._tick()
        self.assertEqual({c.args[0] for c in eng.lcu.request.call_args_list}, {"GET"})


class EndOfGameRecord(unittest.TestCase):
    def test_role_comes_from_detected_position(self):
        eog = _fixture("end_of_game_ranked.json")
        eng = AutomationEngine(lcu=MagicMock(), assets=MagicMock(), config=MagicMock(), log_func=MagicMock())
        eng.config.get.side_effect = lambda k, d=None: {"auto_honor_enabled": False, "skip_stats_enabled": False,
                                                         "auto_save_replays": True}.get(k, d if d is not None else False)
        eng.assets.get_champ_name.return_value = "Zyra"
        eng.db = MagicMock()

        class R:
            status_code = 200

            def json(self):
                return eog
        eng.lcu.request.return_value = R()
        eng._handle_end_of_game("EndOfGame")
        rec = eng.db.record_match.call_args.args[0]
        self.assertEqual(rec["role"], "UTILITY")
        self.assertTrue(rec["win"])
        self.assertEqual((rec["kills"], rec["deaths"], rec["assists"]), (4, 4, 10))
        self.assertEqual(rec["duration_s"], 1776)
        self.assertEqual({c.args[0] for c in eng.lcu.request.call_args_list}, {"GET"})


if __name__ == "__main__":
    unittest.main()
