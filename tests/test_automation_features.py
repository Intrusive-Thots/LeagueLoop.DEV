import unittest
from unittest.mock import MagicMock, patch
import time

from services.automation import AutomationEngine
from core.events import EventBus

class TestAutomationEngineArenaSynergy(unittest.TestCase):
    def _make_engine(self):
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.lcu = MagicMock()
        engine.config = MagicMock()
        engine.assets = MagicMock()
        engine.assets.name_to_id = {"yasuo": 30, "teemo": 20, "garen": 10, "yone": 40}
        engine.assets.get_champ_name = lambda cid: {30: "Yasuo", 20: "Teemo", 10: "Garen", 40: "Yone"}.get(cid, "")
        engine.log = MagicMock()
        engine._log = MagicMock()
        engine._last_synergy_patch = 0.0
        return engine

    @patch("time.time", return_value=100)
    def test_arena_synergy_ban(self, mock_time):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default="": {"arena_ban": "teemo", "auto_lock_in": False}.get(key, default)

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1}],
            "bannedChampions": [],
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "ban", "id": 5, "championId": 0}]]
        }

        engine._perform_arena_synergy(session)

        engine.lcu.request.assert_called_once_with("PATCH", "/lol-champ-select/v1/session/actions/5", data={"championId": 20})
        self.assertEqual(engine._last_synergy_patch, 100)

    @patch("time.time", return_value=100)
    def test_arena_synergy_ban_already_banned(self, mock_time):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default="": {"arena_ban": "teemo", "auto_lock_in": False}.get(key, default)

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1}],
            "bannedChampions": [20], # Teemo is already banned
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "ban", "id": 5, "championId": 0}]]
        }

        engine._perform_arena_synergy(session)

        engine.lcu.request.assert_not_called()

    @patch("time.time", return_value=100)
    def test_arena_synergy_pick_fallback(self, mock_time):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default="": {"arena_pairs": [{"enabled": True, "teammate": "yasuo", "me": ["garen", "teemo"]}], "arena_auto_lock": False}.get(key, default)

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1}, {"cellId": 2, "championId": 30}], # Teammate picked Yasuo
            "bannedChampions": [10], # Garen is banned
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "pick", "id": 5, "championId": 0}]]
        }

        engine._perform_arena_synergy(session)

        # Garen is banned, so should hover Teemo
        engine.lcu.request.assert_called_once_with("PATCH", "/lol-champ-select/v1/session/actions/5", data={"championId": 20})
        self.assertEqual(engine._last_synergy_patch, 100)

    @patch("time.time", return_value=100)
    def test_arena_synergy_pick_auto_lock(self, mock_time):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default="": {"arena_pairs": [{"enabled": True, "teammate": "yasuo", "me": ["yone"]}], "arena_auto_lock": True}.get(key, default)
        engine._last_synergy_patch = 0.0
        engine._synergy_patch_time = 0.0

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1}, {"cellId": 2, "championId": 30}], # Teammate picked Yasuo
            "bannedChampions": [],
            "actions": [[{"actorCellId": 1, "isInProgress": True, "type": "pick", "id": 5, "championId": 40}]] # Already hovering Yone
        }

        engine._perform_arena_synergy(session)

        # Should auto lock Yone
        engine.lcu.request.assert_called_once_with("PATCH", "/lol-champ-select/v1/session/actions/5", data={"championId": 40, "completed": True})
        self.assertEqual(engine._last_synergy_patch, 100)


class TestAutomationEngineAutoHonor(unittest.TestCase):
    def _make_engine(self):
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.lcu = MagicMock()
        engine.config = MagicMock()
        engine.log = MagicMock()
        engine._log = MagicMock()
        engine._honor_handled = False
        return engine

    def test_auto_honor_disabled(self):
        engine = self._make_engine()
        engine.config.get.return_value = False
        engine._handle_end_of_game("EndOfGame")
        engine.lcu.request.assert_not_called()

    def test_auto_honor_handled(self):
        engine = self._make_engine()
        engine.config.get.return_value = True
        engine._honor_handled = True
        engine._handle_end_of_game("EndOfGame")
        engine.lcu.request.assert_not_called()

    def test_auto_honor_no_teammates(self):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default=False: {"auto_honor_enabled": True}.get(key, default)

        # Mock API responses
        mock_eog = MagicMock()
        mock_eog.status_code = 200
        mock_eog.json.return_value = {
            "gameId": 1234,
            "localPlayer": {"puuid": "player-1"},
            "teams": [
                {"isPlayerTeam": True, "players": [{"puuid": "player-1"}]} # Only me on team
            ]
        }
        engine.lcu.request.return_value = mock_eog

        engine._handle_end_of_game("EndOfGame")
        self.assertTrue(engine._honor_handled)

        # Only EOG fetched, no honor posted
        engine.lcu.request.assert_called_once_with("GET", "/lol-end-of-game/v1/eog-stats-block", silent=True)

    def test_auto_honor_success_best_kda(self):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default=False: {"auto_honor_enabled": True, "honor_strategy": "best_kda"}.get(key, default)

        def mock_request(method, endpoint, *args, **kwargs):
            mock = MagicMock()
            mock.status_code = 200
            if endpoint == "/lol-end-of-game/v1/eog-stats-block":
                mock.json.return_value = {
                    "gameId": 1234,
                    "localPlayer": {"puuid": "player-1"},
                    "teams": [
                        {"isPlayerTeam": True, "players": [
                            {"puuid": "player-1"},
                            {"puuid": "player-2", "summonerId": 2, "stats": {"CHAMPIONS_KILLED": 1, "ASSISTS": 1, "NUM_DEATHS": 2}}, # KDA: 1.0
                            {"puuid": "player-3", "summonerId": 3, "stats": {"CHAMPIONS_KILLED": 5, "ASSISTS": 5, "NUM_DEATHS": 1}}  # KDA: 10.0 (Best)
                        ]}
                    ]
                }
            elif endpoint == "/lol-chat/v1/friends":
                mock.json.return_value = [] # No friends
            elif endpoint == "/lol-honor-v2/v1/honor-player":
                # POST request to honor player
                pass
            return mock

        engine.lcu.request.side_effect = mock_request

        engine._handle_end_of_game("EndOfGame")

        engine.lcu.request.assert_any_call("POST", "/lol-honor-v2/v1/honor-player", {
            "gameId": 1234,
            "honorCategory": "HEART",
            "honorType": "HEART",
            "summonerId": 3,
            "puuid": "player-3"
        })

    def test_auto_honor_friend_priority(self):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default=False: {"auto_honor_enabled": True, "honor_strategy": "mvp"}.get(key, default)

        def mock_request(method, endpoint, *args, **kwargs):
            mock = MagicMock()
            mock.status_code = 200
            if endpoint == "/lol-end-of-game/v1/eog-stats-block":
                mock.json.return_value = {
                    "gameId": 1234,
                    "localPlayer": {"puuid": "player-1"},
                    "teams": [
                        {"isPlayerTeam": True, "players": [
                            {"puuid": "player-1"},
                            {"puuid": "player-2", "summonerId": 2, "stats": {"CHAMPIONS_KILLED": 10, "ASSISTS": 10}}, # Best MVP score
                            {"puuid": "friend-1", "summonerId": 3, "stats": {"CHAMPIONS_KILLED": 1, "ASSISTS": 1}}   # Friend, lower score
                        ]}
                    ]
                }
            elif endpoint == "/lol-chat/v1/friends":
                mock.json.return_value = [{"puuid": "friend-1"}] # Friend is in match
            return mock

        engine.lcu.request.side_effect = mock_request

        engine._handle_end_of_game("EndOfGame")

        # It should honor the friend despite having lower MVP score
        engine.lcu.request.assert_any_call("POST", "/lol-honor-v2/v1/honor-player", {
            "gameId": 1234,
            "honorCategory": "HEART",
            "honorType": "HEART",
            "summonerId": 3,
            "puuid": "friend-1"
        })

    def test_auto_honor_conflict_409(self):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default=False: {"auto_honor_enabled": True, "honor_strategy": "random"}.get(key, default)

        def mock_request(method, endpoint, *args, **kwargs):
            mock = MagicMock()
            if endpoint == "/lol-end-of-game/v1/eog-stats-block":
                mock.status_code = 200
                mock.json.return_value = {
                    "gameId": 1234,
                    "localPlayer": {"puuid": "player-1"},
                    "teams": [{"isPlayerTeam": True, "players": [{"puuid": "player-1"}, {"puuid": "player-2", "summonerId": 2}]}]
                }
            elif endpoint == "/lol-chat/v1/friends":
                mock.status_code = 200
                mock.json.return_value = []
            elif endpoint == "/lol-honor-v2/v1/honor-player":
                mock.status_code = 409
            return mock

        engine.lcu.request.side_effect = mock_request
        engine._handle_end_of_game("EndOfGame")
        
        # It should mark as handled on 409 conflict
        self.assertTrue(engine._honor_handled)

    def test_auto_honor_rate_limit_429(self):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default=False: {"auto_honor_enabled": True, "honor_strategy": "random"}.get(key, default)

        def mock_request(method, endpoint, *args, **kwargs):
            mock = MagicMock()
            if endpoint == "/lol-end-of-game/v1/eog-stats-block":
                mock.status_code = 200
                mock.json.return_value = {
                    "gameId": 1234,
                    "localPlayer": {"puuid": "player-1"},
                    "teams": [{"isPlayerTeam": True, "players": [{"puuid": "player-1"}, {"puuid": "player-2", "summonerId": 2}]}]
                }
            elif endpoint == "/lol-chat/v1/friends":
                mock.status_code = 200
                mock.json.return_value = []
            elif endpoint == "/lol-honor-v2/v1/honor-player":
                mock.status_code = 429
            return mock

        engine.lcu.request.side_effect = mock_request
        engine._handle_end_of_game("EndOfGame")
        
        # It should NOT mark as handled on 429 so we retry
        self.assertFalse(engine._honor_handled)

    def test_auto_honor_retry_limit(self):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default=False: {"auto_honor_enabled": True, "honor_strategy": "random"}.get(key, default)

        def mock_request(method, endpoint, *args, **kwargs):
            mock = MagicMock()
            if endpoint == "/lol-end-of-game/v1/eog-stats-block":
                mock.status_code = 200
                mock.json.return_value = {
                    "gameId": 1234,
                    "localPlayer": {"puuid": "player-1"},
                    "teams": [{"isPlayerTeam": True, "players": [{"puuid": "player-1"}, {"puuid": "player-2", "summonerId": 2}]}]
                }
            elif endpoint == "/lol-chat/v1/friends":
                mock.status_code = 200
                mock.json.return_value = []
            elif endpoint == "/lol-honor-v2/v1/honor-player":
                mock.status_code = 500
            return mock

        engine.lcu.request.side_effect = mock_request
        
        # Attempt 1
        engine._handle_end_of_game("EndOfGame")
        self.assertFalse(engine._honor_handled)
        self.assertEqual(engine._honor_attempts, 1)

        # Attempt 2
        engine._handle_end_of_game("EndOfGame")
        self.assertFalse(engine._honor_handled)
        self.assertEqual(engine._honor_attempts, 2)

        # Attempt 3 - should give up and set handled to True
        engine._handle_end_of_game("EndOfGame")
        self.assertTrue(engine._honor_handled)
        self.assertEqual(engine._honor_attempts, 0)

    def test_auto_honor_party_priority_multiple(self):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default=False: {
            "auto_honor_enabled": True,
            "honor_strategy": "mvp",
            "honor_party_first": True
        }.get(key, default)

        # Let's say we have party members: player-2, player-3
        engine._party_puuids = {"player-2", "player-3"}

        def mock_request(method, endpoint, *args, **kwargs):
            mock = MagicMock()
            mock.status_code = 200
            if endpoint == "/lol-end-of-game/v1/eog-stats-block":
                mock.json.return_value = {
                    "gameId": 1234,
                    "localPlayer": {"puuid": "player-1"},
                    "teams": [
                        {"isPlayerTeam": True, "players": [
                            {"puuid": "player-1"},
                            {"puuid": "player-2", "summonerId": 2, "stats": {"CHAMPIONS_KILLED": 1, "ASSISTS": 2}}, # MVP score 3
                            {"puuid": "player-3", "summonerId": 3, "stats": {"CHAMPIONS_KILLED": 5, "ASSISTS": 5}}, # MVP score 10 (Best)
                            {"puuid": "player-4", "summonerId": 4, "stats": {"CHAMPIONS_KILLED": 12, "ASSISTS": 12}} # MVP score 24 (Not in party)
                        ]}
                    ]
                }
            elif endpoint == "/lol-chat/v1/friends":
                mock.json.return_value = []
            return mock

        engine.lcu.request.side_effect = mock_request
        engine._handle_end_of_game("EndOfGame")

        # It should honor both party members in order of MVP score: first player-3, then player-2.
        # It should NOT honor player-4 (the high score non-party member).
        calls = engine.lcu.request.call_args_list
        post_calls = [c for c in calls if c[0][0] == "POST" and c[0][1] == "/lol-honor-v2/v1/honor-player"]
        self.assertEqual(len(post_calls), 2)
        # 1st call should be player-3 (mvp score 10)
        self.assertEqual(post_calls[0][0][2]["puuid"], "player-3")
        # 2nd call should be player-2 (mvp score 3)
        self.assertEqual(post_calls[1][0][2]["puuid"], "player-2")
        self.assertTrue(engine._honor_handled)

    def test_auto_honor_party_priority_fallback(self):
        engine = self._make_engine()
        engine.config.get.side_effect = lambda key, default=False: {
            "auto_honor_enabled": True,
            "honor_strategy": "best_kda",
            "honor_party_first": True
        }.get(key, default)

        # No party members present or not match
        engine._party_puuids = {"player-99"}

        def mock_request(method, endpoint, *args, **kwargs):
            mock = MagicMock()
            mock.status_code = 200
            if endpoint == "/lol-end-of-game/v1/eog-stats-block":
                mock.json.return_value = {
                    "gameId": 1234,
                    "localPlayer": {"puuid": "player-1"},
                    "teams": [
                        {"isPlayerTeam": True, "players": [
                            {"puuid": "player-1"},
                            {"puuid": "player-2", "summonerId": 2, "stats": {"CHAMPIONS_KILLED": 1, "ASSISTS": 1, "NUM_DEATHS": 2}}, # KDA: 1.0
                            {"puuid": "player-3", "summonerId": 3, "stats": {"CHAMPIONS_KILLED": 5, "ASSISTS": 5, "NUM_DEATHS": 1}}  # KDA: 10.0 (Best)
                        ]}
                    ]
                }
            elif endpoint == "/lol-chat/v1/friends":
                mock.json.return_value = []
            return mock

        engine.lcu.request.side_effect = mock_request
        engine._handle_end_of_game("EndOfGame")

        # Fallback to single honor of player-3
        calls = engine.lcu.request.call_args_list
        post_calls = [c for c in calls if c[0][0] == "POST" and c[0][1] == "/lol-honor-v2/v1/honor-player"]
        self.assertEqual(len(post_calls), 1)
        self.assertEqual(post_calls[0][0][2]["puuid"], "player-3")
        self.assertTrue(engine._honor_handled)


if __name__ == '__main__':
    unittest.main()
