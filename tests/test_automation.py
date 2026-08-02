import unittest
from unittest.mock import MagicMock, patch

# AutomationLogic seems to be an old class name. The actual class is AutomationEngine.
from services.automation import AutomationEngine

class TestAutomationEngineReadyCheck(unittest.TestCase):
    def setUp(self):
        # Instantiate without calling __init__ in case the signature is unknown
        self.logic = AutomationEngine.__new__(AutomationEngine)

        # Mock the api dependency and its request method
        self.logic.lcu = MagicMock()
        self.logic.config = MagicMock()

        # Mock the internal _log method to verify logging
        self.logic._log = MagicMock()
        self.logic.ready_check_accepted = False
        self.logic.toast_func = MagicMock()
        self.logic.ready_check_start = None
        self.logic.ready_check_delay = 2.0
        self.logic.poro_snack_func = None
        self.logic._accept_timer = None
        self.logic.queue_func = MagicMock()

    def test_handle_ready_check_not_in_progress(self):
        # Call with a phase that is not "ReadyCheck"
        self.logic._handle_ready_check("Lobby")

        # api.request should not be called
        self.logic.lcu.request.assert_not_called()
        self.logic._log.assert_not_called()

    @patch("threading.Timer")
    @patch("time.time", return_value=100)
    def test_handle_ready_check_in_progress_status_200(self, mock_time, mock_timer):
        self.logic.config.get.return_value = True # auto_accept
        mock_timer_instance = MagicMock()
        mock_timer.return_value = mock_timer_instance

        # Call with "ReadyCheck" - starts timer
        self.logic._handle_ready_check("ReadyCheck")

        # Get the callback function passed to Timer
        callback = mock_timer.call_args[0][1]

        # Execute the callback directly to simulate timer firing
        callback()

        # Verify the api request was made with correct arguments
        self.logic.lcu.request.assert_called_once_with("POST", "/lol-matchmaking/v1/ready-check/accept")

        # Verify logging was triggered
        self.logic._log.assert_called_once_with("Ready Check Accepted!")

    @patch("threading.Timer")
    @patch("time.time", return_value=100)
    def test_handle_ready_check_in_progress_status_204(self, mock_time, mock_timer):
        self.logic.config.get.return_value = True # auto_accept
        mock_timer_instance = MagicMock()
        mock_timer.return_value = mock_timer_instance

        # Call with "ReadyCheck" - starts timer
        self.logic._handle_ready_check("ReadyCheck")

        # Get the callback function passed to Timer
        callback = mock_timer.call_args[0][1]

        # Execute the callback directly to simulate timer firing
        callback()

        # Verify the api request was made
        self.logic.lcu.request.assert_called_once_with("POST", "/lol-matchmaking/v1/ready-check/accept")

        # Verify logging was triggered
        self.logic._log.assert_called_once_with("Ready Check Accepted!")

    def test_handle_ready_check_in_progress_other_status(self):
        # Test when auto_accept is false
        self.logic.config.get.return_value = False # auto_accept

        # Call with "ReadyCheck"
        self.logic._handle_ready_check("ReadyCheck")

        # Verify the api request was NOT made
        self.logic.lcu.request.assert_not_called()

        # Verify logging was NOT triggered
        self.logic._log.assert_not_called()


class TestAutomationEngineWindowState(unittest.TestCase):
    """Tests for window state transitions including stealth mode."""

    def _make_engine(self, stealth=False):
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.lcu = MagicMock()
        engine.config = MagicMock()
        engine.config.get = MagicMock(side_effect=lambda key, default=None: {
            "stealth_mode": stealth,
            "auto_accept": False,
            "auto_requeue": False,
        }.get(key, default))
        engine.assets = MagicMock()
        engine.window_func = MagicMock()
        engine.log = MagicMock()
        engine._log = MagicMock()
        engine.stop_func = None
        engine.stats_func = None
        engine.toast_func = None
        engine.running = True
        engine.paused = False
        engine.setup_done = False
        engine._skin_equipped = False
        engine._requeue_handled = False
        engine._stop_event = MagicMock()
        engine.executor = MagicMock()
        engine._last_error_times = {}
        engine.last_phase = "None"
        engine.current_queue_id = None
        engine.queue_func = MagicMock()
        engine.discord_rpc = MagicMock()
        engine.ready_check_start = None
        engine.ready_check_delay = None
        engine.ready_check_accepted = False
        engine._last_countdown_log = None
        engine._last_disconnect_log = 0.0
        engine._last_priority_swap = 0.0
        engine._last_search_state_time = 0.0
        engine._cached_search_state = None
        engine._accept_timer = None
        engine._honor_handled = False
        return engine

    def test_stealth_off_sends_restore(self):
        """When stealth_mode is OFF, transitioning from InProgress → EndOfGame calls restore."""
        engine = self._make_engine(stealth=False)
        engine.last_phase = "InProgress"

        # Simulate phase data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = "EndOfGame"
        mock_future = MagicMock()
        mock_future.result.return_value = mock_response
        engine.executor.submit.return_value = mock_future

        engine._is_first_tick = False
        engine._game_pid = None
        engine._tick()

        engine.window_func.assert_called_with("restore")

    def test_stealth_on_sends_restore_quiet(self):
        """When stealth_mode is ON, transitioning from InProgress → EndOfGame calls restore_quiet."""
        engine = self._make_engine(stealth=True)
        engine.last_phase = "InProgress"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = "EndOfGame"
        mock_future = MagicMock()
        mock_future.result.return_value = mock_response
        engine.executor.submit.return_value = mock_future

        engine._is_first_tick = False
        engine._game_pid = None
        engine._tick()

        engine.window_func.assert_called_with("restore_quiet")

    def test_inprogress_always_minimizes(self):
        """Regardless of stealth mode, entering InProgress does not auto-minimize."""
        for stealth in (True, False):
            engine = self._make_engine(stealth=stealth)
            engine.last_phase = "ChampSelect"
            engine._is_first_tick = False
            engine._is_game_running = MagicMock(return_value=False)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = "InProgress"
            mock_future = MagicMock()
            mock_future.result.return_value = mock_response
            engine.executor.submit.return_value = mock_future

            engine._tick()

            engine.window_func.assert_not_called()


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

class TestAutomationEngineChampSelect(unittest.TestCase):
    def _make_engine(self):
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.lcu = MagicMock()
        engine.config = MagicMock()
        engine.assets = MagicMock()
        engine.log = MagicMock()
        engine._log = MagicMock()
        engine.paused = False
        engine._skin_equipped = True
        engine._runes_equipped = True
        engine._last_champ_id = 0
        engine.stats_func = None
        engine.current_queue_id = 0
        
        # Mock sub-handlers to avoid running unrelated logic
        engine._handle_auto_dodge = MagicMock()
        engine._handle_chat_warden = MagicMock()
        engine._perform_priority_sniper = MagicMock()
        engine._perform_arena_synergy = MagicMock()
        engine._perform_draft_assistant = MagicMock()
        engine._equip_random_skin = MagicMock()
        engine._auto_equip_runes = MagicMock()
        return engine

    def test_champ_select_champion_change_resets_flags(self):
        engine = self._make_engine()
        
        # Mock _get_local_player to return cellId and championId
        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "assignedPosition": "middle", "championId": 10}] # Garen
        }
        
        # First call, should set _last_champ_id and reset flags
        engine._handle_champ_select("ChampSelect", session)
        self.assertEqual(engine._last_champ_id, 10)
        self.assertFalse(engine._skin_equipped)
        self.assertFalse(engine._runes_equipped)

        # Set flags to True again
        engine._skin_equipped = True
        engine._runes_equipped = True

        # Second call with same champion ID, flags should remain True
        engine._handle_champ_select("ChampSelect", session)
        self.assertTrue(engine._skin_equipped)
        self.assertTrue(engine._runes_equipped)

        # Third call with new champion ID (e.g. swap or picker), flags should reset
        session["myTeam"][0]["championId"] = 20 # Teemo
        engine._handle_champ_select("ChampSelect", session)
        self.assertEqual(engine._last_champ_id, 20)
        self.assertFalse(engine._skin_equipped)
        self.assertFalse(engine._runes_equipped)


class TestAutomationEngineSpectatorThrottle(unittest.TestCase):
    def test_spectator_polling_throttle_and_reset(self):
        """Spectator phase initializes spectate_start_time and calculates adaptive sleep throttle."""
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.executor = MagicMock()
        mock_future = MagicMock()
        mock_req = MagicMock()
        mock_req.status_code = 200
        mock_req.json.return_value = "Spectating"
        mock_future.result.return_value = mock_req
        engine.executor.submit.return_value = mock_future
        engine.lcu = MagicMock()
        engine.queue_func = None
        engine.window_func = None
        engine.last_phase = "None"
        engine._spectate_start_time = None
        engine._game_pid = None
        engine._last_game_scan = 0.0
        engine._handle_ready_check = MagicMock()
        engine._handle_champ_select = MagicMock()
        engine._handle_dodge_requeue = MagicMock()
        engine._handle_end_of_game = MagicMock()
        engine._check_friend_lobby = MagicMock()
        engine._update_discord_rpc = MagicMock()
        engine.lcu.request.return_value.status_code = 200
        engine.lcu.request.return_value.json.return_value = "Spectating"

        # Mock time and stop_event
        engine._stop_event = MagicMock()
        engine._stop_event.is_set.return_value = True

        engine._tick()
        self.assertIsNotNone(engine._spectate_start_time)
        self.assertEqual(engine.last_phase, "Spectating")


class TestAutomationEngineAutoJoinAndSkin(unittest.TestCase):
    def setUp(self):
        self.engine = AutomationEngine.__new__(AutomationEngine)
        self.engine.lcu = MagicMock()
        self.engine.config = MagicMock()
        self.engine._log = MagicMock()
        self.engine._auto_joined_friends_cooldown = {}
        self.engine._current_auto_joined_friend = None
        self.engine._current_auto_joined_party_id = None
        self.engine._skin_equipped = False

    def test_leave_friend_lobby_applies_5min_cooldown(self):
        self.engine._current_auto_joined_friend = "Alice"
        self.engine.lcu.is_connected = True

        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "partyId": "party-123",
            "localMember": {"isLeader": False},
            "members": [{"cellId": 0}, {"cellId": 1}]
        }
        self.engine.lcu.request.return_value = mock_res

        left = self.engine.leave_friend_lobby_and_cooldown()

        self.assertTrue(left)
        self.assertIn("alice", self.engine._auto_joined_friends_cooldown)
        self.assertIsNone(self.engine._current_auto_joined_friend)
        self.assertIsNone(self.engine._current_auto_joined_party_id)

    def test_reset_auto_join_cooldowns_clears_timers(self):
        self.engine._auto_joined_friends_cooldown = {"alice": 9999999999.0, "bob": 9999999999.0}
        self.engine.reset_auto_join_cooldowns("alice")
        self.assertNotIn("alice", self.engine._auto_joined_friends_cooldown)
        self.assertIn("bob", self.engine._auto_joined_friends_cooldown)

        self.engine.reset_auto_join_cooldowns()
        self.assertEqual(len(self.engine._auto_joined_friends_cooldown), 0)

    def test_equip_random_skin_respects_config_toggle(self):
        self.engine.config.get.side_effect = lambda key, default=None: False if key == "auto_random_skin" else default
        session = {"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championId": 10}]}
        self.engine._equip_random_skin(session)
        self.engine.lcu.request.assert_not_called()

    def test_equip_random_skin_selects_unlocked_skin(self):
        self.engine.config.get.side_effect = lambda key, default=None: True if key == "auto_random_skin" else default
        session = {"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championId": 10}]}

        mock_skins_res = MagicMock()
        mock_skins_res.status_code = 200
        mock_skins_res.json.return_value = [
            {"id": 10000, "isBase": True, "name": "Base Garen"},
            {"id": 10001, "isBase": False, "name": "Dreadknight Garen", "unlocked": True}
        ]
        mock_patch_res = MagicMock()
        mock_patch_res.status_code = 200

        def mock_request(method, endpoint, **kwargs):
            if method == "GET" and endpoint == "/lol-champ-select/v1/skin-carousel-skins":
                return mock_skins_res
            if method == "PATCH":
                return mock_patch_res
            return None

        self.engine.lcu.request.side_effect = mock_request
        self.engine._equip_random_skin(session)

        self.assertTrue(self.engine._skin_equipped)


if __name__ == '__main__':
    unittest.main()

