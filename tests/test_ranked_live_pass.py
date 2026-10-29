"""#23 pass 3: fixes from a live Ranked Solo/Duo run under a read-only launcher.

The launcher blocked every non-GET request and logged it. With every
automation toggle off in config, LeagueLoop still tried to:
  * DELETE + POST /lol-lobby/v2/lobby on the first lobby event (mode sync),
  * PATCH a champ-select hover (master switch ignored at startup).
The sidebar also estimated every queue at 2:00 (the client said 1:08) and
showed "● Drafting" for the whole draft with no turn and no clock.

Fixtures in tests/fixtures/lcu/*ranked*.json are anonymized captures of that
draft. The local player is cell 6 (team 2, cells 5-9).
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.events import EventBus
from core.state import StateManager
from services.automation import AutomationEngine
from services.client_state_service import ClientStateService
from services.draft.status import draft_status, time_left_s, turn_label

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "lcu")


def _fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


class _Resp:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _Lcu:
    """GET-only fake: answers phase + session, records every call."""

    def __init__(self, session):
        self.session = session
        self.is_connected = True
        self.connection_state = None
        self.calls = []

    def connect(self, silent=False):
        return True

    def request(self, method, endpoint, *a, **k):
        self.calls.append((method, endpoint))
        if "gameflow-phase" in endpoint:
            return _Resp("ChampSelect")
        if "champ-select/v1/session" in endpoint:
            return _Resp(self.session)
        return _Resp(None, 404)


def _published(name):
    """Run a fixture through the real producer and return ChampSelectState."""
    session = _fixture(name)
    lcu = _Lcu(session)
    state = StateManager(bus=EventBus)
    service = ClientStateService(lcu, state, sleep=lambda _s: None)
    service.tick()
    return state.state.champ_select, lcu


class DraftStatusFromLiveRanked(unittest.TestCase):
    def test_planning_shows_declare_intent(self):
        # PLANNING marks all ten ban actions in progress; that is not a ban turn.
        cs, _ = _published("champ_select_ranked_planning.json")
        self.assertEqual(cs.timer_phase, "PLANNING")
        self.assertEqual(turn_label(cs), "Declare intent")

    def test_simultaneous_bans_are_my_ban(self):
        cs, _ = _published("champ_select_ranked_ban_turn.json")
        text, mine = draft_status(cs, now=cs.timer_sampled_at)
        self.assertTrue(text.startswith("● Your ban"), text)
        self.assertTrue(mine)

    def test_ten_bans_reveal_is_not_a_pick(self):
        cs, _ = _published("champ_select_ranked_bans_reveal.json")
        self.assertEqual(turn_label(cs), "Bans revealed")

    def test_my_pick_pair(self):
        cs, _ = _published("champ_select_ranked_my_pick.json")
        text, mine = draft_status(cs, now=cs.timer_sampled_at)
        self.assertEqual(text.split(" · ")[0], "● Your pick")
        self.assertTrue(mine)

    def test_teammates_picking(self):
        cs, _ = _published("champ_select_ranked_team_pick.json")
        self.assertEqual(turn_label(cs), "Team picking")

    def test_enemy_picking(self):
        cs, _ = _published("champ_select_ranked_enemy_pick.json")
        text, mine = draft_status(cs, now=cs.timer_sampled_at)
        self.assertTrue(text.startswith("● Enemy picking"), text)
        self.assertFalse(mine)

    def test_finalization(self):
        cs, _ = _published("champ_select_ranked_finalization.json")
        self.assertEqual(turn_label(cs), "Finalizing")

    def test_countdown_keeps_running_between_publishes(self):
        # The producer ages the capture by the real clock, so pin the value.
        published, _ = _published("champ_select_ranked_my_pick.json")
        cs = SimpleNamespace(**{**published.__dict__, "timer_remaining_s": 25.0,
                                "timer_sampled_at": 1000.0})
        start = time_left_s(cs, now=cs.timer_sampled_at)
        later = time_left_s(cs, now=cs.timer_sampled_at + 10)
        self.assertAlmostEqual(start - later, 10, delta=0.01)
        self.assertEqual(time_left_s(cs, now=cs.timer_sampled_at + 999), start)  # implausible age ignored
        stale = SimpleNamespace(**{**cs.__dict__, "timer_remaining_s": 3.0})
        self.assertEqual(time_left_s(stale, now=cs.timer_sampled_at + 5), 0.0)

    def test_countdown_text_format(self):
        cs = SimpleNamespace(timer_phase="BAN_PICK", cell_id=6, my_team=({"cellId": 6},),
                             actions=({"actorCellId": 6, "type": "pick", "isInProgress": True,
                                       "completed": False},),
                             locked_in=False, timer_remaining_s=18.4, timer_sampled_at=100.0)
        self.assertEqual(draft_status(cs, now=100.0), ("● Your pick · 0:18", True))

    def test_producer_only_reads(self):
        _, lcu = _published("champ_select_ranked_my_pick.json")
        self.assertTrue(lcu.calls)
        self.assertEqual({m for m, _ in lcu.calls}, {"GET"})


class QueueClockSource(unittest.TestCase):
    def _engine(self, responses):
        engine = AutomationEngine(lcu=MagicMock(), assets=MagicMock(),
                                  config=MagicMock(), log_func=MagicMock())
        engine.lcu.request.side_effect = lambda method, ep, *a, **k: responses.get(ep)
        return engine

    def test_prefers_matchmaking_search_with_clock(self):
        search = _fixture("matchmaking_search_ranked.json")
        engine = self._engine({
            "/lol-matchmaking/v1/search": _Resp(search),
            "/lol-lobby/v2/lobby/matchmaking/search-state": _Resp(
                _fixture("lobby_matchmaking_search_state.json")),
        })
        got = engine._read_search_state()
        self.assertEqual(got["timeInQueue"], 2.0)
        self.assertAlmostEqual(got["estimatedQueueTime"], 97.42, places=1)
        for call in engine.lcu.request.call_args_list:
            self.assertEqual(call.args[0], "GET")

    def test_lobby_search_state_has_no_clock(self):
        # Why the old source always fell back to 0:00 / Est 2:00.
        state = _fixture("lobby_matchmaking_search_state.json")
        self.assertNotIn("timeInQueue", state)
        self.assertNotIn("estimatedQueueTime", state)

    def test_falls_back_to_lobby_search_state(self):
        engine = self._engine({
            "/lol-matchmaking/v1/search": _Resp(None, 404),
            "/lol-lobby/v2/lobby/matchmaking/search-state": _Resp({"searchState": "Searching"}),
        })
        self.assertEqual(engine._read_search_state(), {"searchState": "Searching"})


class PausedEngineStillReads(unittest.TestCase):
    def test_paused_loop_ticks_for_the_display(self):
        engine = AutomationEngine(lcu=MagicMock(), assets=MagicMock(),
                                  config=MagicMock(), log_func=MagicMock())
        engine.lcu.is_connected = True
        engine.running = True
        engine.paused = True
        engine._stop_event = MagicMock()
        engine._stop_event.wait.return_value = False

        def tick():
            engine.running = False
        engine._tick = MagicMock(side_effect=tick)
        engine._loop()
        engine._tick.assert_called_once()

    def test_paused_tick_sends_no_writes(self):
        engine = AutomationEngine(lcu=MagicMock(), assets=MagicMock(),
                                  config=MagicMock(), log_func=MagicMock())
        engine.config.get.side_effect = lambda k, d=None: True  # every toggle on
        engine.paused = True
        engine.last_phase = "ChampSelect"
        session = _fixture("champ_select_ranked_my_pick.json")

        def req(method, ep, *a, **k):
            if "gameflow-phase" in ep:
                return _Resp("ChampSelect")
            if "champ-select/v1/session" in ep:
                return _Resp(session)
            return _Resp({}, 200)
        engine.lcu.request.side_effect = req
        engine._is_game_running = MagicMock(return_value=False)
        engine._maybe_autosave_replay = MagicMock()
        engine._tick()
        methods = {c.args[0] for c in engine.lcu.request.call_args_list}
        self.assertEqual(methods, {"GET"})


class MasterSwitchAtStartup(unittest.TestCase):
    def test_reads_controller_then_config(self):
        from core.main import LeagueLoopApp
        fn = LeagueLoopApp._automation_master_enabled
        ctrl = MagicMock()
        ctrl.master_enabled.return_value = False
        self.assertFalse(fn(SimpleNamespace(container=SimpleNamespace(automation_controller=ctrl))))
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, d=None: {"automation_master": False}.get(k, d)
        self.assertFalse(fn(SimpleNamespace(container=None, config=cfg)))
        cfg.get.side_effect = lambda k, d=None: d
        self.assertTrue(fn(SimpleNamespace(container=None, config=cfg)))


class LobbySyncDoesNotRecreate(unittest.TestCase):
    def _fake(self):
        fake = MagicMock()
        fake.lcu.is_connected = True
        fake._get_queue_id_for_mode.return_value = 420
        return fake

    def test_sync_from_lobby_event_makes_no_requests(self):
        from ui.app_sidebar import SidebarWidget
        import threading
        fake = self._fake()
        before = threading.active_count()
        SidebarWidget._on_mode_change(fake, "Ranked Solo/Duo", create_lobby=False)
        # Resolving the queue id may GET the queue list; nothing else.
        methods = {c.args[0] for c in fake.lcu.request.call_args_list}
        self.assertLessEqual(methods, {"GET"})
        fake.automation.leave_friend_lobby_and_cooldown.assert_not_called()
        self.assertLessEqual(threading.active_count(), before)
        fake.config.set.assert_called_with("aram_mode", "Ranked Solo/Duo")

    def test_lobby_event_passes_create_lobby_false(self):
        from ui.app_sidebar import SidebarWidget
        fake = self._fake()
        fake.winfo_exists.return_value = True
        fake.config.get.return_value = "ARAM"
        fake.after.side_effect = lambda _ms, fn: fn()
        SidebarWidget._on_lobby_event(fake, {"gameConfig": {"queueId": 420}})
        if fake._on_mode_change.called:
            self.assertEqual(fake._on_mode_change.call_args.kwargs.get("create_lobby"), False)


if __name__ == "__main__":
    unittest.main()
