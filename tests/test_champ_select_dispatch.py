"""
Which handler runs in which mode.

Reported from a live ARAM Mayhem game: the companion showed "ARAM Mayhem /
Champ Select / Drafting", accepted the ready check, equipped a skin -- and then
sat through the whole "Pick Your Champion" screen without picking. The debug
log for that draft carried nothing but `skin-carousel-skins` and
`my-selection`; no pick was ever attempted.

The dispatch was an if/elif chain ending in

    elif is_draft:                 # {400, 420, 440}
        self._perform_draft_assistant(session)

so ARAM Mayhem (2400) matched no branch. Neither did Swiftplay, Quickplay, URF,
ARURF, One For All, Nexus Blitz, Ultimate Spellbook or Brawl. The ARAM bench
branch did not save it either: while you are choosing between the three cards
the bench does not exist yet, so `benchChampions` is empty.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from core.config_keys import AUTO_HOVER, PRIORITY_LIST
from services.automation import AutomationEngine

AHRI = 103

QUEUES_THAT_ASK_YOU_TO_PICK = {
    400: "Draft Pick",
    420: "Ranked Solo/Duo",
    440: "Ranked Flex",
    480: "Swiftplay",
    490: "Quickplay",
    900: "URF",
    1010: "ARURF",
    1020: "One For All",
    1300: "Nexus Blitz",
    1400: "Ultimate Spellbook",
    2300: "Brawl",
    2400: "ARAM Mayhem",
}

ARENA_QUEUES = (1700, 1710)


class FakeConfig:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class FakeAssets:
    name_to_id = {"ahri": AHRI}
    champ_data: dict = {}

    def get_champ_name(self, cid):
        return "Ahri" if int(cid) == AHRI else ""

    def get_champ_roles(self, cid):
        return ()

    def preload_champion_icons(self, keys):
        pass


class FakeLcu:
    def __init__(self):
        self.calls = []
        self.is_connected = True

    def request(self, method, endpoint, data=None, silent=False):
        self.calls.append((method, endpoint, data))
        return None

    def set_in_game_mode(self, *_a):
        pass


def picking_session(queue_id, bench=()):
    """Champ select with a pick action in progress for us, and no role."""
    return {
        "queueId": queue_id,
        "localPlayerCellId": 2,
        "myTeam": [{"cellId": 2, "championId": 0}],
        "theirTeam": [],
        "bannedChampions": [],
        "benchChampions": [{"championId": c} for c in bench],
        "actions": [[
            {"id": 7, "actorCellId": 2, "type": "pick",
             "isInProgress": True, "completed": False, "championId": 0},
        ]],
    }


def engine(**cfg):
    cfg.setdefault(AUTO_HOVER, True)
    cfg.setdefault(PRIORITY_LIST, [AHRI])
    cfg.setdefault("aram_priority_list", [AHRI])
    cfg.setdefault("auto_random_skin", False)
    eng = AutomationEngine(
        lcu=FakeLcu(), assets=FakeAssets(), config=FakeConfig(**cfg),
        log_func=lambda *a, **k: None,
    )
    eng._log = MagicMock()
    eng._auto_equip_runes = MagicMock()
    eng._equip_random_skin = MagicMock()
    return eng


class EveryModeThatAsksYouToPick(unittest.TestCase):
    def test_the_draft_assistant_is_reached(self):
        for queue_id, name in QUEUES_THAT_ASK_YOU_TO_PICK.items():
            with self.subTest(queue=queue_id, mode=name):
                eng = engine()
                eng._handle_champ_select("ChampSelect", picking_session(queue_id))
                self.assertTrue(
                    eng.lcu.calls,
                    "%s (%d) reached no handler -- the pick phase passed with "
                    "nothing attempted" % (name, queue_id),
                )
                method, endpoint, body = eng.lcu.calls[-1]
                self.assertEqual(method, "PATCH")
                self.assertTrue(endpoint.endswith("/actions/7"))
                self.assertEqual(body.get("championId"), AHRI)

    def test_aram_mayhem_picks_before_any_bench_exists(self):
        """The exact reported case: three cards on screen, bench still empty."""
        eng = engine()
        session = picking_session(2400, bench=())
        self.assertEqual(session["benchChampions"], [])
        eng._handle_champ_select("ChampSelect", session)
        self.assertTrue(eng.lcu.calls, "ARAM Mayhem did not attempt a pick")


class ArenaKeepsItsOwnHandler(unittest.TestCase):
    def test_arena_does_not_go_to_the_draft_assistant(self):
        for queue_id in ARENA_QUEUES:
            with self.subTest(queue=queue_id):
                eng = engine(arena_synergy_enabled=False)
                eng._perform_draft_assistant = MagicMock()
                eng._perform_arena_synergy = MagicMock()
                eng._handle_champ_select("ChampSelect", picking_session(queue_id))
                eng._perform_draft_assistant.assert_not_called()


class TheBenchStillWins(unittest.TestCase):
    def test_a_bench_still_reaches_the_sniper(self):
        eng = engine(priority_picker={"enabled": True, "list": ["Ahri"]})
        eng._perform_priority_sniper = MagicMock()
        eng._handle_champ_select(
            "ChampSelect", picking_session(450, bench=(AHRI,))
        )
        eng._perform_priority_sniper.assert_called_once()

    def test_the_sniper_stays_off_when_the_switch_is_off(self):
        eng = engine(priority_picker={"enabled": False, "list": ["Ahri"]})
        eng._perform_priority_sniper = MagicMock()
        eng._handle_champ_select(
            "ChampSelect", picking_session(450, bench=(AHRI,))
        )
        eng._perform_priority_sniper.assert_not_called()


if __name__ == "__main__":
    unittest.main()
