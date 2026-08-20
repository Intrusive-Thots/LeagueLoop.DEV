"""
ClientStateService — the producer for ApplicationState.

Before this existed, `StateManager.update_client()` was never called by
anything in the application. The Qt shell renders entirely from that state,
so the header read "Disconnected" and the phase read "Idle" with the League
Client open in champ select, and the follow-the-draft jump could never fire.
"""
import unittest

from core.events import EventBus
from core.state import ConnectionStateEnum, GameflowPhase, StateManager
from services.client_state_service import ClientStateService


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeLcu:
    """Serves canned LCU endpoints and counts requests."""

    def __init__(self, connectable=True, phase="None", summoner=None,
                 search=None, lobby=None, champ_select=None):
        self.connectable = connectable
        self.is_connected = False
        self.connection_state = ConnectionStateEnum.DISCONNECTED
        self.phase = phase
        self.summoner = summoner
        self.search = search
        self.lobby = lobby
        self.champ_select = champ_select
        self.requests = []

    def connect(self, silent=False):
        self.is_connected = self.connectable
        self.connection_state = (
            ConnectionStateEnum.CONNECTED if self.connectable
            else ConnectionStateEnum.DISCONNECTED
        )
        return self.connectable

    def request(self, method, endpoint, silent=False):
        self.requests.append(endpoint)
        if not self.is_connected:
            return None
        if "gameflow-phase" in endpoint:
            return FakeResponse(self.phase)
        if "current-summoner" in endpoint:
            return FakeResponse(self.summoner) if self.summoner else FakeResponse(None, 404)
        if "champ-select/v1/session" in endpoint:
            return (FakeResponse(self.champ_select) if self.champ_select
                    else FakeResponse(None, 404))
        if "matchmaking/v1/search" in endpoint:
            return FakeResponse(self.search or {})
        if "lobby" in endpoint:
            return FakeResponse(self.lobby or {})
        return FakeResponse(None, 404)


def build(**kw):
    state = StateManager(bus=EventBus)
    lcu = FakeLcu(**kw)
    service = ClientStateService(lcu, state, sleep=lambda _s: None)
    return service, lcu, state


class ConnectionTests(unittest.TestCase):
    def test_a_running_client_is_reported_as_connected(self):
        service, _lcu, state = build(summoner={"gameName": "DPM", "tagLine": "Null"})
        self.assertTrue(service.tick())
        self.assertTrue(state.state.client.connected)

    def test_a_missing_client_is_reported_as_disconnected(self):
        service, _lcu, state = build(connectable=False)
        self.assertFalse(service.tick())
        self.assertFalse(state.state.client.connected)

    def test_disconnecting_clears_the_summoner_identity(self):
        """A stale name on a dead client reads as 'still signed in'."""
        service, lcu, state = build(summoner={"gameName": "DPM", "tagLine": "Null"})
        service.tick()
        self.assertEqual(state.state.client.summoner_name, "DPM#Null")

        lcu.connectable = False
        lcu.is_connected = False
        service.tick()
        self.assertIsNone(state.state.client.summoner_name)


class SummonerTests(unittest.TestCase):
    def test_riot_id_is_preferred_over_the_legacy_display_name(self):
        service, _lcu, state = build(summoner={
            "gameName": "DPM", "tagLine": "Null", "displayName": "",
            "summonerId": 7, "puuid": "abc", "profileIconId": 12,
        })
        service.tick()
        client = state.state.client
        self.assertEqual(client.summoner_name, "DPM#Null")
        self.assertEqual(client.summoner_id, 7)
        self.assertEqual(client.puuid, "abc")
        self.assertEqual(client.profile_icon_id, 12)

    def test_falls_back_to_display_name_for_pre_riot_id_accounts(self):
        service, _lcu, state = build(summoner={"displayName": "OldName"})
        service.tick()
        self.assertEqual(state.state.client.summoner_name, "OldName")

    def test_summoner_is_fetched_once_per_connection(self):
        service, lcu, _state = build(summoner={"gameName": "A", "tagLine": "B"})
        service.tick()
        service.tick()
        service.tick()
        self.assertEqual(
            sum(1 for e in lcu.requests if "current-summoner" in e), 1
        )

    def test_reconnecting_refetches_the_summoner(self):
        service, lcu, _state = build(summoner={"gameName": "A", "tagLine": "B"})
        service.tick()
        lcu.connectable = False
        lcu.is_connected = False
        service.tick()
        lcu.connectable = True
        service.tick()
        self.assertEqual(
            sum(1 for e in lcu.requests if "current-summoner" in e), 2
        )


class PhaseTests(unittest.TestCase):
    def test_champ_select_reaches_the_state(self):
        """The exact case that was broken: client in draft, shell says Idle."""
        service, _lcu, state = build(
            phase="ChampSelect", summoner={"gameName": "A", "tagLine": "B"}
        )
        service.tick()
        self.assertEqual(
            state.state.client.phase, GameflowPhase.CHAMP_SELECT.value
        )
        self.assertTrue(state.state.champ_select.active)

    def test_leaving_champ_select_clears_the_flag(self):
        service, lcu, state = build(
            phase="ChampSelect", summoner={"gameName": "A", "tagLine": "B"}
        )
        service.tick()
        lcu.phase = "InProgress"
        service.tick()
        self.assertFalse(state.state.champ_select.active)

    def test_a_disconnected_client_reports_no_phase(self):
        service, _lcu, state = build(connectable=False)
        service.tick()
        self.assertEqual(state.state.client.phase, GameflowPhase.NONE.value)


class QueueTests(unittest.TestCase):
    def test_searching_is_reflected(self):
        service, _lcu, state = build(
            phase="Matchmaking",
            summoner={"gameName": "A", "tagLine": "B"},
            search={"searchState": "Searching", "estimatedQueueTime": 90.0,
                    "timeInQueue": 12.0},
            lobby={"gameConfig": {"queueId": 450}},
        )
        service.tick()
        queue = state.state.queue
        self.assertTrue(queue.is_searching)
        self.assertEqual(queue.queue_id, 450)
        self.assertEqual(queue.estimated_delay_s, 90.0)

    def test_in_game_has_no_queue(self):
        service, _lcu, state = build(
            phase="InProgress", summoner={"gameName": "A", "tagLine": "B"},
            lobby={"gameConfig": {"queueId": 450}},
        )
        service.tick()
        self.assertIsNone(state.state.queue.queue_id)
        self.assertFalse(state.state.queue.is_searching)


class ChurnTests(unittest.TestCase):
    """Every update emits STATE_CHANGED, which repaints the shell."""

    def test_a_steady_state_does_not_republish(self):
        service, _lcu, state = build(
            phase="Lobby", summoner={"gameName": "A", "tagLine": "B"},
            lobby={"gameConfig": {"queueId": 450}},
        )
        service.tick()

        seen = []
        handle = EventBus.on("state_changed", lambda *a, **k: seen.append(1))
        try:
            for _ in range(5):
                service.tick()
        finally:
            try:
                handle.dispose()
            except Exception:
                pass

        self.assertEqual(seen, [], "idle polling repainted the shell")

    def test_a_real_change_does_publish(self):
        service, lcu, _state = build(
            phase="Lobby", summoner={"gameName": "A", "tagLine": "B"}
        )
        service.tick()

        seen = []
        handle = EventBus.on("state_changed", lambda *a, **k: seen.append(1))
        try:
            lcu.phase = "ChampSelect"
            service.tick()
        finally:
            try:
                handle.dispose()
            except Exception:
                pass

        self.assertTrue(seen, "a phase change was not published")


class RobustnessTests(unittest.TestCase):
    def test_a_throwing_client_does_not_propagate(self):
        service, lcu, state = build(summoner={"gameName": "A", "tagLine": "B"})

        def explode(*_a, **_kw):
            raise RuntimeError("client went away")

        lcu.request = explode
        service.tick()  # must not raise
        self.assertEqual(state.state.client.phase, GameflowPhase.NONE.value)

    def test_start_and_stop_are_idempotent(self):
        service, _lcu, _state = build(connectable=False)
        service.start()
        service.start()
        self.assertTrue(service.running)
        service.stop()
        service.stop()
        self.assertFalse(service.running)


if __name__ == "__main__":
    unittest.main()


SESSION = {
    "localPlayerCellId": 2,
    "timer": {"adjustedTimeLeftInPhase": 27400},
    "myTeam": [
        {"cellId": 0, "championId": 51},
        {"cellId": 2, "championId": 103, "assignedPosition": "middle"},
    ],
    "theirTeam": [{"cellId": 5}],
    "actions": [
        [{"actorCellId": 0, "type": "pick", "completed": True}],
        [{"actorCellId": 2, "type": "pick", "completed": False}],
    ],
}


class ChampSelectTests(unittest.TestCase):
    def _service(self, session=SESSION):
        service, lcu, state = build(
            phase="ChampSelect",
            summoner={"gameName": "A", "tagLine": "B"},
            champ_select=session,
        )
        return service, lcu, state

    def test_the_draft_reaches_the_state(self):
        service, _lcu, state = self._service()
        service.tick()
        cs = state.state.champ_select
        self.assertTrue(cs.active)
        self.assertEqual(cs.cell_id, 2)
        self.assertEqual(cs.local_role, "middle")
        self.assertEqual(cs.selected_champion_id, 103)
        self.assertEqual(len(cs.my_team), 2)
        self.assertEqual(len(cs.their_team), 1)

    def test_the_timer_is_converted_from_milliseconds(self):
        """The LCU reports ms; every consumer here works in seconds."""
        service, _lcu, state = self._service()
        service.tick()
        self.assertAlmostEqual(state.state.champ_select.timer_remaining_s, 27.4)

    def test_actions_are_flattened_across_groups(self):
        service, _lcu, state = self._service()
        service.tick()
        self.assertEqual(len(state.state.champ_select.actions), 2)

    def test_lock_in_is_read_from_my_own_action_only(self):
        """Cell 0 has locked; cell 2 (me) has not."""
        service, _lcu, state = self._service()
        service.tick()
        self.assertFalse(state.state.champ_select.locked_in)

    def test_lock_in_is_detected_when_it_is_mine(self):
        session = dict(SESSION)
        session["actions"] = [[{"actorCellId": 2, "type": "pick", "completed": True}]]
        service, _lcu, state = self._service(session)
        service.tick()
        self.assertTrue(state.state.champ_select.locked_in)

    def test_leaving_the_draft_clears_the_roster_and_timer(self):
        service, lcu, state = self._service()
        service.tick()
        self.assertTrue(state.state.champ_select.my_team)

        lcu.phase = "InProgress"
        service.tick()
        cs = state.state.champ_select
        self.assertFalse(cs.active)
        self.assertEqual(cs.my_team, ())
        self.assertEqual(cs.timer_remaining_s, 0.0)
        self.assertEqual(cs.cell_id, -1)

    def test_no_session_yet_is_not_a_crash(self):
        service, _lcu, state = self._service(session=None)
        service.tick()
        self.assertTrue(state.state.champ_select.active)

    def test_the_session_is_not_polled_outside_the_draft(self):
        service, lcu, _state = build(
            phase="Lobby", summoner={"gameName": "A", "tagLine": "B"}
        )
        service.tick()
        self.assertFalse(
            any("champ-select" in e for e in lcu.requests),
            "polled the draft endpoint outside a draft",
        )
