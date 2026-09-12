"""
Two live faults, from one real ARAM game's log.

1. The draft assistant re-sent the same hover on every tick. The log line
   "Draft: hovered Sona" appears six times for a single draft, each one a real
   PATCH the client answered 204. The only guard was

       my_action["championId"] != pick_id

   which assumes an accepted hover comes back in the session. In ARAM it does
   not -- the action's championId stays 0 -- so the condition never went false.

2. Find Match created a lobby, threw the response away, and searched anyway.
   With a game still running the client answers the create with HTTP 500, the
   transport retries it three times as a transient 5xx, the search that follows
   is a guaranteed 400, and the only thing the user sees is "Matchmaking failed
   - check client".
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.config_keys import AUTO_HOVER, PRIORITY_LIST
from services.automation import AutomationEngine

AHRI, GAREN = 103, 86


class FakeConfig:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class FakeAssets:
    name_to_id = {"ahri": AHRI, "garen": GAREN}
    champ_data: dict = {}

    def get_champ_name(self, cid):
        return {AHRI: "Ahri", GAREN: "Garen"}.get(int(cid), "")

    def get_champ_roles(self, cid):
        return ()

    def preload_champion_icons(self, keys):
        pass


class AramLikeLcu:
    """A client that accepts a hover and never reflects it back.

    This is what the real one does in ARAM, and it is the whole reason the
    loop existed: every read says the action is still empty.
    """

    def __init__(self, status=204):
        self.calls = []
        self.status = status
        self.is_connected = True

    def request(self, method, endpoint, data=None, silent=False):
        self.calls.append((method, endpoint, data))
        return SimpleNamespace(status_code=self.status, text="")

    def set_in_game_mode(self, *_a):
        pass


def picking_session(queue_id=450, my_champ=0):
    return {
        "queueId": queue_id,
        "localPlayerCellId": 2,
        "myTeam": [{"cellId": 2, "championId": my_champ}],
        "theirTeam": [],
        "bannedChampions": [],
        "benchChampions": [],
        "actions": [[
            {"id": 9, "actorCellId": 2, "type": "pick",
             "isInProgress": True, "completed": False, "championId": 0},
        ]],
    }


def engine(lcu=None, **cfg):
    cfg.setdefault(AUTO_HOVER, True)
    cfg.setdefault(PRIORITY_LIST, [AHRI])
    cfg.setdefault("aram_priority_list", [AHRI])
    eng = AutomationEngine(
        lcu=lcu or AramLikeLcu(),
        assets=FakeAssets(),
        config=FakeConfig(**cfg),
        log_func=lambda *a, **k: None,
    )
    eng._log = MagicMock()
    return eng


def hovers(eng):
    return [c for c in eng.lcu.calls if c[0] == "PATCH"]


class TheHoverIsSentOnce(unittest.TestCase):
    def test_ten_ticks_produce_one_patch(self):
        eng = engine()
        for _ in range(10):
            eng._perform_draft_assistant(picking_session())
        self.assertEqual(
            len(hovers(eng)), 1,
            "the hover repeated: %d PATCHes for one draft" % len(hovers(eng)),
        )

    def test_a_refused_hover_is_retried(self):
        """Not recorded unless the client took it -- otherwise one dropped
        packet would mean never hovering at all."""
        eng = engine(lcu=AramLikeLcu(status=500))
        for _ in range(3):
            eng._perform_draft_assistant(picking_session())
            eng._last_draft_action_time = 0      # skip the rate limit
        self.assertGreater(len(hovers(eng)), 1)

    def test_a_champion_picked_by_hand_is_left_alone(self):
        """The 'it keeps switching back' complaint."""
        eng = engine()
        eng._perform_draft_assistant(picking_session())
        self.assertEqual(len(hovers(eng)), 1)

        # The player picks Garen themselves; the session now says so.
        for _ in range(5):
            eng._last_draft_action_time = 0
            eng._perform_draft_assistant(picking_session(my_champ=GAREN))
        self.assertEqual(
            len(hovers(eng)), 1,
            "the assistant overwrote a champion the player chose by hand",
        )

    def test_a_new_draft_starts_clean(self):
        eng = engine()
        eng._perform_draft_assistant(picking_session())
        eng._handle_champ_select("None", None)          # draft ended
        eng._last_draft_action_time = 0
        eng._perform_draft_assistant(picking_session())
        self.assertEqual(len(hovers(eng)), 2)

    def test_priority_picker_locks_in_aram(self):
        eng = engine(priority_picker={"enabled": True, "list": ["Ahri"]})
        # First tick hovers
        eng._perform_draft_assistant(picking_session())
        self.assertEqual(len(hovers(eng)), 1)
        self.assertEqual(hovers(eng)[0][2], {"championId": AHRI})

        # Second tick locks in even when LCU does not echo championId in session
        eng._last_draft_action_time = 0
        eng._perform_draft_assistant(picking_session())
        self.assertEqual(len(hovers(eng)), 2)
        self.assertEqual(hovers(eng)[1][2], {"championId": AHRI, "completed": True})

        # Subsequent ticks do not spam lock
        for _ in range(5):
            eng._last_draft_action_time = 0
            eng._perform_draft_assistant(picking_session())
        self.assertEqual(len(hovers(eng)), 2)


class TheLobbyRefusalIsExplained(unittest.TestCase):
    """The sidebar's two new helpers, tested without building a window."""

    def setUp(self):
        from ui.app_sidebar import SidebarWidget
        self.cls = SidebarWidget

    def test_every_blocking_phase_has_a_message(self):
        for phase, message in self.cls.PHASES_WITHOUT_A_LOBBY.items():
            with self.subTest(phase=phase):
                self.assertTrue(message.strip())
                self.assertNotIn("check client", message.lower())

    def test_lobby_and_idle_are_not_blocked(self):
        for phase in ("Lobby", "None"):
            self.assertNotIn(phase, self.cls.PHASES_WITHOUT_A_LOBBY)

    def test_a_500_names_the_real_cause(self):
        message = self.cls._lobby_refusal_message("ARAM", 500)
        self.assertIn("ARAM", message)
        self.assertIn("game or draft", message)

    def test_no_response_is_not_reported_as_a_refusal(self):
        self.assertIn("no answer", self.cls._lobby_refusal_message("ARAM", None).lower())

    def test_the_phase_probe_survives_a_dead_client(self):
        widget = self.cls.__new__(self.cls)
        widget.lcu = SimpleNamespace(
            request=lambda *a, **k: (_ for _ in ()).throw(OSError("client gone"))
        )
        self.assertIsNone(widget._phase_blocking_a_lobby())

    def test_an_unreadable_phase_does_not_block(self):
        """Unknown is not the same as blocked: let the call through and report
        whatever the client actually says."""
        widget = self.cls.__new__(self.cls)
        widget.lcu = SimpleNamespace(
            request=lambda *a, **k: SimpleNamespace(status_code=503)
        )
        self.assertIsNone(widget._phase_blocking_a_lobby())

    def test_in_progress_blocks(self):
        widget = self.cls.__new__(self.cls)
        widget.lcu = SimpleNamespace(
            request=lambda *a, **k: SimpleNamespace(
                status_code=200, json=lambda: "InProgress"
            )
        )
        self.assertIn("game is still running", widget._phase_blocking_a_lobby())


if __name__ == "__main__":
    unittest.main()
