"""
Tests for Riot API performance, LCU control loops, WebSocket listener lifecycle,
and memory leak prevention.
"""
import gc
import json
import time
import unittest
from unittest.mock import MagicMock, patch

from services.api_handler import LCUClient
from services.account_manager import RiotClientAPI
from services.client_state_service import ClientStateService
from core.state import StateManager, ConnectionStateEnum, GameflowPhase
from core.events import EventBus
from utils.client_detector import scan_clients, _cached_results


class TestWebSocketListenerLifecycle(unittest.TestCase):
    def setUp(self):
        self.client = LCUClient()

    def test_subscribe_and_unsubscribe_single(self):
        """Test subscribing and explicitly unsubscribing a callback."""
        mock_ws = MagicMock()
        self.client._ws_connection = mock_ws

        cb = MagicMock()
        event_name = "OnJsonApiEvent_lol-gameflow_v1_gameflow-phase"

        self.client.subscribe(event_name, cb)
        self.assertIn(event_name, self.client._subscriptions)
        self.assertEqual(len(self.client._subscriptions[event_name]), 1)
        mock_ws.send.assert_called_with(json.dumps([5, event_name]))

        # Unsubscribe the callback
        removed = self.client.unsubscribe(event_name, cb)
        self.assertTrue(removed)
        self.assertNotIn(event_name, self.client._subscriptions)
        # Verify WAMP v1 unsubscribe [6, event_name] was sent to LCU
        mock_ws.send.assert_called_with(json.dumps([6, event_name]))

    def test_unsubscribe_multiple_listeners_on_same_event(self):
        """Unsubscribe only sends server unsubscribe when the last listener leaves."""
        mock_ws = MagicMock()
        self.client._ws_connection = mock_ws

        cb1 = MagicMock()
        cb2 = MagicMock()
        event = "OnJsonApiEvent_lol-champ-select_v1_session"

        self.client.subscribe(event, cb1)
        self.client.subscribe(event, cb2)
        self.assertEqual(len(self.client._subscriptions[event]), 2)

        # Unsubscribe cb1 - event still has cb2
        removed1 = self.client.unsubscribe(event, cb1)
        self.assertTrue(removed1)
        self.assertIn(event, self.client._subscriptions)
        self.assertEqual(len(self.client._subscriptions[event]), 1)
        # Server unsubscribe should NOT have been sent yet
        self.assertNotIn([6, event], [json.loads(c[0][0]) for c in mock_ws.send.call_args_list])

        # Unsubscribe cb2 - last listener leaves
        removed2 = self.client.unsubscribe(event, cb2)
        self.assertTrue(removed2)
        self.assertNotIn(event, self.client._subscriptions)
        # Server unsubscribe MUST now have been sent
        self.assertIn([6, event], [json.loads(c[0][0]) for c in mock_ws.send.call_args_list])

    def test_unsubscribe_all(self):
        """Test unsubscribing a listener from all registered topics at once."""
        mock_ws = MagicMock()
        self.client._ws_connection = mock_ws

        cb = MagicMock()
        e1 = "OnJsonApiEvent_lol-gameflow_v1_gameflow-phase"
        e2 = "OnJsonApiEvent_lol-lobby_v2_lobby"
        e3 = "OnJsonApiEvent_lol-chat_v1_friends"

        self.client.subscribe(e1, cb)
        self.client.subscribe(e2, cb)
        self.client.subscribe(e3, cb)

        self.assertEqual(len(self.client._subscriptions), 3)

        total = self.client.unsubscribe_all(cb)
        self.assertEqual(total, 3)
        self.assertEqual(len(self.client._subscriptions), 0)

    def test_weak_listener_auto_pruning(self):
        """Test that callbacks subscribed with weak=True do not leak when the owner is collected."""
        class DisposableListener:
            def __init__(self):
                self.calls = []

            def on_event(self, event, data):
                self.calls.append((event, data))

        listener = DisposableListener()
        event = "OnJsonApiEvent_test_event"
        self.client.subscribe(event, listener.on_event, weak=True)
        self.assertIn(event, self.client._subscriptions)

        # Delete owner and trigger garbage collection
        del listener
        gc.collect()

        # Unsubscribing or querying telemetry should prune dead listeners
        removed = self.client.unsubscribe(event, MagicMock())
        self.assertFalse(removed)
        # Channel with only the dead listener should be purged
        self.assertNotIn(event, self.client._subscriptions)

    def test_http_429_token_bucket_backoff(self):
        """Test that HTTP 429 depletes tokens and applies backoff cooldown."""
        self.client.is_connected = True
        self.client.port = "1234"
        self.client.base_url = "https://127.0.0.1:1234"

        # Give tokens
        self.client._tokens = 15.0

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "2"}
        self.client.session = MagicMock()
        self.client.session.request.return_value = mock_resp

        res = self.client.request("GET", "/lol-summoner/v1/current-summoner", silent=True)
        self.assertEqual(res, mock_resp)

        # Token bucket must be drained
        with self.client._rate_lock:
            self.assertEqual(self.client._tokens, 0.0)


class TestRiotClientAPIPerformance(unittest.TestCase):
    def test_riot_client_rate_limiting(self):
        """Test token-bucket rate limiting on RiotClientAPI."""
        api = RiotClientAPI()
        api.is_connected = True
        api.port = "5555"
        api.base_url = "https://127.0.0.1:5555"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        api.session = MagicMock()
        api.session.request.return_value = mock_resp

        # Drain tokens to 0
        with api._rate_lock:
            api._tokens = 0.0

        with patch("time.sleep") as mock_sleep:
            res = api.request("GET", "/rso-auth/v1/session", silent=True)
            self.assertEqual(res, mock_resp)
            mock_sleep.assert_called_once()

    def test_riot_client_retry_on_transient_500(self):
        """Test exponential backoff and retry on transient 500 from Riot Client."""
        api = RiotClientAPI()
        api.is_connected = True
        api.port = "5555"
        api.base_url = "https://127.0.0.1:5555"

        fail_resp = MagicMock()
        fail_resp.status_code = 502
        ok_resp = MagicMock()
        ok_resp.status_code = 200

        api.session = MagicMock()
        api.session.request.side_effect = [fail_resp, ok_resp]

        with patch("time.sleep") as mock_sleep:
            res = api.request("GET", "/rso-auth/v1/authorization", silent=True)
            self.assertEqual(res, ok_resp)
            self.assertEqual(api.session.request.call_count, 2)
            mock_sleep.assert_called()


class TestClientStateInGameSynchronization(unittest.TestCase):
    def test_in_game_mode_sync(self):
        """Test that ClientStateService notifies LCU when entering and exiting InProgress phase."""
        mock_lcu = MagicMock()
        mock_lcu.is_connected = True
        mock_lcu.connection_state = ConnectionStateEnum.CONNECTED

        state = StateManager(bus=EventBus)
        service = ClientStateService(mock_lcu, state, sleep=lambda _s: None)

        # Simulate entering InProgress
        service._publish_phase(GameflowPhase.IN_PROGRESS.value)
        mock_lcu.set_in_game_mode.assert_called_with(True)

        # Simulate exiting to EndOfGame
        service._publish_phase(GameflowPhase.END_OF_GAME.value)
        mock_lcu.set_in_game_mode.assert_called_with(False)


class TestClientDetectorPriority(unittest.TestCase):
    def test_detects_ux_even_if_launcher_first(self):
        """Verify LeagueClientUx.exe credentials are used even if LeagueClient.exe appears first."""
        mock_launcher = MagicMock()
        mock_launcher.info = {"name": "LeagueClient.exe", "pid": 100}
        mock_launcher.cmdline.return_value = ["C:\\Riot Games\\League of Legends\\LeagueClient.exe"]

        mock_ux = MagicMock()
        mock_ux.info = {"name": "LeagueClientUx.exe", "pid": 200}
        mock_ux.cmdline.return_value = [
            "LeagueClientUx.exe",
            "--app-port=54321",
            "--remoting-auth-token=super-auth-token-123",
        ]

        with patch("utils.client_detector.psutil.process_iter", return_value=[mock_launcher, mock_ux]):
            results = scan_clients(force=True)

            self.assertEqual(results["league"]["port"], "54321")
            self.assertEqual(results["league"]["token"], "super-auth-token-123")
            self.assertEqual(results["league"]["pid"], 200)
            self.assertTrue(results["league"]["connected"])
