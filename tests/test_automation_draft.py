import unittest
from unittest.mock import MagicMock, patch
import time

from services.automation import AutomationEngine
from core.events import EventBus

class TestAutomationEnginePrioritySniper(unittest.TestCase):
    def _make_engine(self):
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.lcu = MagicMock()
        engine.config = MagicMock()
        engine.assets = MagicMock()
        engine.log = MagicMock()
        engine._log = MagicMock()
        engine._last_priority_swap = 0.0
        engine._skin_equipped = True
        return engine

    @patch("time.time", return_value=100)
    def test_priority_sniper_no_list(self, mock_time):
        engine = self._make_engine()
        session = {"benchChampions": [{"championId": 1}]}
        engine._perform_priority_sniper(session, [])
        engine.lcu.request.assert_not_called()

    @patch("time.time", return_value=100)
    def test_priority_sniper_no_bench(self, mock_time):
        engine = self._make_engine()
        session = {"benchChampions": []}
        engine._perform_priority_sniper(session, ["Teemo"])
        engine.lcu.request.assert_not_called()

    @patch("time.time", return_value=100)
    def test_priority_sniper_swap_better_champ(self, mock_time):
        engine = self._make_engine()
        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "championId": 10}],
            "benchChampions": [{"championId": 20}, {"championId": 30}]
        }
        engine.assets.get_champ_name.side_effect = lambda cid: {10: "Garen", 20: "Teemo", 30: "Yasuo"}.get(cid, "")

        # Yasuo is higher priority than Teemo, and Teemo is higher than Garen
        priority_list = ["Yasuo", "Teemo", "Garen"]

        engine._perform_priority_sniper(session, priority_list)

        # Should swap to Yasuo (30)
        engine.lcu.request.assert_called_once_with("POST", "/lol-champ-select/v1/session/bench/swap/30")
        self.assertEqual(engine._last_priority_swap, 100)
        self.assertFalse(engine._skin_equipped)

    @patch("time.time", return_value=100)
    def test_priority_sniper_no_better_champ(self, mock_time):
        engine = self._make_engine()
        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "championId": 10}],
            "benchChampions": [{"championId": 20}, {"championId": 30}]
        }
        engine.assets.get_champ_name.side_effect = lambda cid: {10: "Garen", 20: "Teemo", 30: "Yasuo"}.get(cid, "")

        # Garen is the highest priority, no need to swap
        priority_list = ["Garen", "Teemo", "Yasuo"]

        engine._perform_priority_sniper(session, priority_list)
        engine.lcu.request.assert_not_called()

    @patch("time.time", return_value=100)
    def test_priority_sniper_cooldown(self, mock_time):
        engine = self._make_engine()
        from core.constants import PRIORITY_SWAP_COOLDOWN
        engine._last_priority_swap = 100 - (PRIORITY_SWAP_COOLDOWN - 0.5) # Still in cooldown
        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "championId": 10}],
            "benchChampions": [{"championId": 30}]
        }
        engine.assets.get_champ_name.side_effect = lambda cid: {10: "Garen", 30: "Yasuo"}.get(cid, "")
        priority_list = ["Yasuo", "Garen"]

        engine._perform_priority_sniper(session, priority_list)
        engine.lcu.request.assert_not_called()


class TestAutomationEngineDraftAssistant(unittest.TestCase):
    def _make_engine(self):
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.lcu = MagicMock()
        engine.config = MagicMock()
        engine.assets = MagicMock()
        engine.assets.name_to_id = {"yasuo": 30, "teemo": 20, "garen": 10}
        engine.log = MagicMock()
        engine._log = MagicMock()
        engine._last_draft_action_time = 0.0
        return engine

    @patch("time.time", return_value=100)
    def test_draft_assistant_teammate_respect_ban(self, mock_time):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default="": {"ban_MIDDLE_1": "yasuo", "ban_MIDDLE_2": "teemo", "auto_lock_in": False}.get(key, default)

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "assignedPosition": "middle"}, {"cellId": 2, "championPickIntent": 30}], # Teammate hovering Yasuo
            "bannedChampions": [],
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "ban", "id": 5, "championId": 0}]]
        }

        engine._perform_draft_assistant(session)

        # Yasuo is hovered, so it should skip Yasuo and hover Teemo
        engine.lcu.request.assert_called_once_with("PATCH", "/lol-champ-select/v1/session/actions/5", data={"championId": 20})
        self.assertEqual(engine._last_draft_action_time, 100)

    @patch("time.time", return_value=100)
    def test_draft_assistant_teammate_respect_ban_champion_id(self, mock_time):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default="": {"ban_MIDDLE_1": "yasuo", "ban_MIDDLE_2": "teemo", "auto_lock_in": False}.get(key, default)

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "assignedPosition": "middle"}, {"cellId": 2, "championId": 30}], # Teammate hovering Yasuo via championId
            "bannedChampions": [],
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "ban", "id": 5, "championId": 0}]]
        }

        engine._perform_draft_assistant(session)

        # Yasuo is hovered, so it should skip Yasuo and hover Teemo
        engine.lcu.request.assert_called_once_with("PATCH", "/lol-champ-select/v1/session/actions/5", data={"championId": 20})
        self.assertEqual(engine._last_draft_action_time, 100)

    @patch("time.time", return_value=100)
    def test_draft_assistant_fallback_pick(self, mock_time):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default="": {"pick_MIDDLE_1": "garen", "pick_MIDDLE_2": "yasuo", "auto_lock_in": False}.get(key, default)

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "assignedPosition": "middle"}],
            "bannedChampions": [10], # Garen is banned
            "theirTeam": [],
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "pick", "id": 5, "championId": 0}]]
        }

        engine._perform_draft_assistant(session)

        # Garen is banned, should pick Yasuo
        engine.lcu.request.assert_called_once_with("PATCH", "/lol-champ-select/v1/session/actions/5", data={"championId": 30})
        self.assertEqual(engine._last_draft_action_time, 100)

    @patch("time.time", return_value=100)
    def test_draft_assistant_auto_lock_pick(self, mock_time):
        engine = self._make_engine()
        # Ensure sufficient time has passed since last action
        engine._last_draft_action_time = 0.0
        engine.config.get.side_effect = lambda key, default="": {"pick_MIDDLE_1": "yasuo", "auto_lock_in": True}.get(key, default)

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "assignedPosition": "middle"}],
            "bannedChampions": [],
            "theirTeam": [],
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "pick", "id": 5, "championId": 30}]] # Already hovering Yasuo
        }

        engine._perform_draft_assistant(session)

        # Should lock in Yasuo
        engine.lcu.request.assert_called_once_with("PATCH", "/lol-champ-select/v1/session/actions/5", data={"championId": 30, "completed": True})
        self.assertEqual(engine._last_draft_action_time, 100)

    @patch("time.time", return_value=100)
    def test_draft_assistant_teammate_respect_pick(self, mock_time):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default="": {"pick_MIDDLE_1": "yasuo", "pick_MIDDLE_2": "teemo", "auto_lock_in": False}.get(key, default)

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "assignedPosition": "middle"}, {"cellId": 2, "championPickIntent": 30}], # Teammate hovering Yasuo
            "bannedChampions": [],
            "theirTeam": [],
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "pick", "id": 5, "championId": 0}]]
        }

        engine._perform_draft_assistant(session)

        # Yasuo is hovered by teammate, so it should skip Yasuo and hover Teemo (20)
        engine.lcu.request.assert_called_once_with("PATCH", "/lol-champ-select/v1/session/actions/5", data={"championId": 20})
        self.assertEqual(engine._last_draft_action_time, 100)


class TestAutomationEngineDraftAssistantCoverage(unittest.TestCase):
    def _make_engine(self):
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.lcu = MagicMock()
        engine.config = MagicMock()
        engine.assets = MagicMock()
        engine.log = MagicMock()
        engine._log = MagicMock()
        engine._last_draft_action_time = 0
        return engine

    @patch('time.time')
    def test_perform_draft_assistant_teammate_hover_dodge(self, mock_time):
        mock_time.return_value = 1000
        engine = self._make_engine()
        engine.assets.name_to_id = {"yasuo": 157}
        engine.config.get.side_effect = lambda k, d=None: "yasuo" if "ban" in k else d

        session = {
            "myTeam": [
                {"cellId": 1, "assignedPosition": "mid"},
                {"cellId": 2, "championPickIntent": 157} # Teammate hovering yasuo
            ],
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "ban", "id": 1, "championId": 0}]],
            "bannedChampions": []
        }

        engine._get_local_player = MagicMock(return_value={"cellId": 1, "assignedPosition": "mid"})

        engine._perform_draft_assistant(session)

        # It should skip banning yasuo because teammate hovered it
        engine.lcu.request.assert_not_called()


class TestAutomationEngineArenaPickCoverage(unittest.TestCase):
    def _make_engine(self):
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.lcu = MagicMock()
        engine.config = MagicMock()
        engine.assets = MagicMock()
        engine.log = MagicMock()
        engine._log = MagicMock()
        engine._last_synergy_patch = 0
        return engine

    @patch('time.time')
    def test_handle_arena_pick_success(self, mock_time):
        mock_time.return_value = 1000
        engine = self._make_engine()

        engine.config.get.side_effect = lambda k, d=None: [
            {"enabled": True, "teammate": "yasuo", "me": ["yone"]}
        ] if k == "arena_pairs" else d

        engine.assets.get_champ_name.return_value = "Yasuo"
        engine.assets.name_to_id = {"yone": 777, "yasuo": 157}

        session = {
            "myTeam": [
                {"cellId": 1, "championId": 0},
                {"cellId": 2, "championId": 157} # Teammate picked Yasuo
            ]
        }
        me = {"cellId": 1, "championId": 0}
        action = {"id": 1, "championId": 0}
        banned_ids = []

        engine._handle_arena_pick(session, me, action, banned_ids)

        engine.lcu.request.assert_called_with("PATCH", "/lol-champ-select/v1/session/actions/1", data={"championId": 777})


if __name__ == '__main__':
    unittest.main()
