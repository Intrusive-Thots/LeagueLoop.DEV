import unittest
from unittest.mock import MagicMock, patch
from core.events import EventBus
from services.league_service import LeagueService

class TestLeagueService(unittest.TestCase):
    def setUp(self):
        EventBus._listeners.clear()
        self.mock_lcu = MagicMock()
        self.mock_lcu.is_connected = True

    def test_initialization(self):
        service = LeagueService(self.mock_lcu)
        self.mock_lcu.subscribe.assert_any_call("OnJsonApiEvent_lol-gameflow_v1_gameflow-phase", service._on_gameflow_phase_event)
        self.mock_lcu.subscribe.assert_any_call("OnJsonApiEvent_lol-summoner_v1_current-summoner", service._on_summoner_event)

    def test_is_connected(self):
        service = LeagueService(self.mock_lcu)
        self.mock_lcu.is_connected = True
        self.assertTrue(service.is_connected)
        self.mock_lcu.is_connected = False
        self.assertFalse(service.is_connected)

    def test_get_phase(self):
        service = LeagueService(self.mock_lcu)
        service._phase = "ChampSelect"
        self.assertEqual(service.get_phase(), "ChampSelect")

    def test_request(self):
        service = LeagueService(self.mock_lcu)
        service.request("GET", "/test-endpoint", silent=True)
        self.mock_lcu.request.assert_called_once_with("GET", "/test-endpoint", silent=True)

    def test_on_lcu_connection_change_disconnected(self):
        service = LeagueService(self.mock_lcu)
        service._phase = "Matchmaking"
        service._summoner_info = {"displayName": "Player 1"}
        
        mock_emit = MagicMock()
        with patch.object(EventBus, "emit", mock_emit):
            service._on_lcu_connection_change(False)
            self.assertEqual(service.get_phase(), "None")
            self.assertEqual(service.get_summoner_info(), {})
            mock_emit.assert_called_once_with("league_disconnected")

    @patch("threading.Thread")
    def test_on_lcu_connection_change_connected(self, mock_thread):
        service = LeagueService(self.mock_lcu)
        
        mock_emit = MagicMock()
        with patch.object(EventBus, "emit", mock_emit):
            service._on_lcu_connection_change(True)
            mock_emit.assert_called_once_with("league_connected")
            mock_thread.assert_called_once()

    def test_on_gameflow_phase_event(self):
        service = LeagueService(self.mock_lcu)
        service._phase = "None"
        
        mock_emit = MagicMock()
        with patch.object(EventBus, "emit", mock_emit):
            event = {"data": "Lobby"}
            service._on_gameflow_phase_event(event)
            self.assertEqual(service.get_phase(), "Lobby")
            mock_emit.assert_called_once_with("game_phase_changed", "Lobby")
