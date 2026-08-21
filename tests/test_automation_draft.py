"""
The automation engine's draft actions.

Auto Ban and Auto Pick were both no-ops, for the same two reasons:

* they read config keys no screen has ever written — `ban_{role}_1..3`,
  `auto_ban_list`, `auto_ban_1..15`, `pick_{role}_1..3` — while the Bans and
  Priority screens write `ban_list` and `priority_list`;
* they resolved every entry through `assets.name_to_id`, expecting champion
  *names*, while the UI stores champion *ids*.

Both now go through `PriorityEngine` — the same code the Champ Select screen
previews with — keyed by `core.config_keys` and working in ids.
"""
import unittest
from unittest import mock

from core.config_keys import (
    AUTO_BAN_ENABLED,
    AUTO_BAN_RESPECT_HOVERS,
    AUTO_HOVER,
    AUTO_LOCK_IN,
    BAN_LIST,
    PRIORITY_LIST,
)

AHRI, GAREN, JINX, ZED = 103, 86, 222, 238
NAMES = {AHRI: "Ahri", GAREN: "Garen", JINX: "Jinx", ZED: "Zed"}


class FakeConfig:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class FakeAssets:
    def __init__(self):
        self.name_to_id = {v.lower(): k for k, v in NAMES.items()}
        self.champ_data = {}

    def get_champ_name(self, cid):
        return NAMES.get(int(cid), "")

    def get_champ_roles(self, cid):
        return ()


class FakeLcu:
    def __init__(self):
        self.calls = []
        self.is_connected = True

    def request(self, method, endpoint, data=None, silent=False):
        self.calls.append((method, endpoint, data))
        return None

    def set_in_game_mode(self, *_a):
        pass


def session(action_type="ban", my_champ=0, banned=(), picked=(), hovers=()):
    """A champ select session with one in-progress action for cell 2."""
    my_team = [{"cellId": 2, "championId": my_champ, "assignedPosition": "middle"}]
    for i, cid in enumerate(hovers):
        my_team.append({"cellId": 10 + i, "championPickIntent": cid})
    for i, cid in enumerate(picked):
        my_team.append({"cellId": 20 + i, "championId": cid})
    return {
        "localPlayerCellId": 2,
        "myTeam": my_team,
        "theirTeam": [],
        "bannedChampions": [{"championId": cid} for cid in banned],
        "actions": [[
            {"id": 7, "actorCellId": 2, "type": action_type,
             "isInProgress": True, "completed": False, "championId": my_champ},
        ]],
    }


def engine(**cfg):
    from services.automation import AutomationEngine

    with mock.patch.object(AutomationEngine, "__init__", lambda self, *a, **k: None):
        eng = AutomationEngine()

    from services.draft.priority_engine import PriorityEngine

    eng.config = FakeConfig(**cfg)
    eng.assets = FakeAssets()
    eng.lcu = FakeLcu()
    eng.log = None
    eng.draft_engine = PriorityEngine(config_manager=eng.config, asset_manager=eng.assets)
    eng._last_draft_action_time = 0.0
    eng._warned_empty_bans = False
    eng._warned_empty_picks = False
    eng.logged = []
    eng._log = lambda msg: eng.logged.append(msg)
    eng._get_local_player = lambda sess: next(
        (p for p in sess.get("myTeam", [])
         if p.get("cellId") == sess.get("localPlayerCellId")), None
    )
    return eng


def run_draft(eng, sess):
    """Drive the one method under test."""
    eng._perform_draft_assistant(sess)
    return eng.lcu.calls


class BanTests(unittest.TestCase):
    def test_a_configured_ban_is_hovered(self):
        eng = engine(**{AUTO_BAN_ENABLED: True, BAN_LIST: [ZED, JINX]})
        calls = run_draft(eng, session("ban"))
        self.assertTrue(calls, "auto ban did nothing")
        method, endpoint, body = calls[-1]
        self.assertEqual(method, "PATCH")
        self.assertTrue(endpoint.endswith("/actions/7"))
        self.assertEqual(body, {"championId": ZED})

    def test_the_ban_is_committed_without_auto_lock_in(self):
        """
        Locking a ban and locking a pick are separate decisions. This used to
        require `auto_lock_in`, so wanting bans handled but picks by hand left
        a ban hovering forever and never spent.
        """
        eng = engine(**{AUTO_BAN_ENABLED: True, BAN_LIST: [ZED], AUTO_LOCK_IN: False})
        calls = run_draft(eng, session("ban", my_champ=ZED))
        _m, _e, body = calls[-1]
        self.assertEqual(body, {"championId": ZED, "completed": True})

    def test_an_already_banned_champion_is_skipped(self):
        eng = engine(**{AUTO_BAN_ENABLED: True, BAN_LIST: [ZED, JINX]})
        calls = run_draft(eng, session("ban", banned=(ZED,)))
        _m, _e, body = calls[-1]
        self.assertEqual(body["championId"], JINX)

    def test_a_teammate_hover_is_respected(self):
        eng = engine(**{AUTO_BAN_ENABLED: True, BAN_LIST: [ZED, JINX],
                        AUTO_BAN_RESPECT_HOVERS: True})
        calls = run_draft(eng, session("ban", hovers=(ZED,)))
        _m, _e, body = calls[-1]
        self.assertEqual(body["championId"], JINX)
        self.assertTrue(any("hovering" in m for m in eng.logged))

    def test_hovers_can_be_ignored(self):
        eng = engine(**{AUTO_BAN_ENABLED: True, BAN_LIST: [ZED],
                        AUTO_BAN_RESPECT_HOVERS: False})
        calls = run_draft(eng, session("ban", hovers=(ZED,)))
        _m, _e, body = calls[-1]
        self.assertEqual(body["championId"], ZED)

    def test_auto_ban_off_does_nothing(self):
        eng = engine(**{AUTO_BAN_ENABLED: False, BAN_LIST: [ZED]})
        self.assertEqual(run_draft(eng, session("ban")), [])

    def test_an_empty_ban_list_is_reported_once(self):
        eng = engine(**{AUTO_BAN_ENABLED: True, BAN_LIST: []})
        run_draft(eng, session("ban"))
        run_draft(eng, session("ban"))
        empty = [m for m in eng.logged if "ban list is empty" in m]
        self.assertEqual(len(empty), 1)


class PickTests(unittest.TestCase):
    def test_a_configured_pick_is_hovered(self):
        eng = engine(**{PRIORITY_LIST: [AHRI, GAREN], AUTO_HOVER: True})
        calls = run_draft(eng, session("pick"))
        self.assertTrue(calls, "auto pick did nothing")
        _m, _e, body = calls[-1]
        self.assertEqual(body, {"championId": AHRI})

    def test_locking_requires_auto_lock_in(self):
        eng = engine(**{PRIORITY_LIST: [AHRI], AUTO_HOVER: True, AUTO_LOCK_IN: False})
        calls = run_draft(eng, session("pick", my_champ=AHRI))
        self.assertEqual(calls, [], "picked without being asked to lock in")

        eng = engine(**{PRIORITY_LIST: [AHRI], AUTO_LOCK_IN: True})
        calls = run_draft(eng, session("pick", my_champ=AHRI))
        _m, _e, body = calls[-1]
        self.assertEqual(body, {"championId": AHRI, "completed": True})

    def test_it_falls_down_the_list_when_the_first_is_taken(self):
        eng = engine(**{PRIORITY_LIST: [AHRI, GAREN], AUTO_HOVER: True})
        calls = run_draft(eng, session("pick", picked=(AHRI,)))
        _m, _e, body = calls[-1]
        self.assertEqual(body["championId"], GAREN)

    def test_a_teammate_hover_blocks_the_pick(self):
        eng = engine(**{PRIORITY_LIST: [AHRI]})
        calls = run_draft(eng, session("pick", hovers=(AHRI,)))
        self.assertEqual(calls, [])
        self.assertTrue(any("hovering" in m or "available" in m for m in eng.logged))

    def test_an_empty_priority_list_is_reported_once(self):
        eng = engine(**{PRIORITY_LIST: []})
        run_draft(eng, session("pick"))
        run_draft(eng, session("pick"))
        empty = [m for m in eng.logged if "priority list" in m]
        self.assertEqual(len(empty), 1)

    def test_ids_are_used_not_names(self):
        """
        The regression this whole change exists for: the engine expected
        champion names and the UI stores ids.
        """
        eng = engine(**{PRIORITY_LIST: [AHRI], AUTO_HOVER: True})
        _m, _e, body = run_draft(eng, session("pick"))[-1]
        self.assertIsInstance(body["championId"], int)
        self.assertEqual(body["championId"], AHRI)


if __name__ == "__main__":
    unittest.main()


class HoverGateTests(unittest.TestCase):
    """Auto Hover has to gate hovering; it only reached the mobile API before."""

    def test_hover_off_means_no_hover(self):
        eng = engine(**{PRIORITY_LIST: [AHRI], AUTO_HOVER: False, AUTO_LOCK_IN: False})
        self.assertEqual(run_draft(eng, session("pick")), [])

    def test_locking_implies_hovering(self):
        """You cannot lock a champion the client has not been told about."""
        eng = engine(**{PRIORITY_LIST: [AHRI], AUTO_HOVER: False, AUTO_LOCK_IN: True})
        calls = run_draft(eng, session("pick"))
        self.assertTrue(calls)
        self.assertEqual(calls[-1][2], {"championId": AHRI})
