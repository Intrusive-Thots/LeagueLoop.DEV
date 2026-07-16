import unittest
from unittest.mock import MagicMock, patch
from core.events import EventBus
from services.draft_service import DraftService, get_draft_service

class TestDraftService(unittest.TestCase):
    def setUp(self):
        EventBus._listeners.clear()
        self.mock_league = MagicMock()
        self.mock_league.is_connected = True

    def test_on_disconnect(self):
        service = DraftService(self.mock_league)
        service._session_cache = {"localPlayerCellId": 5}
        
        mock_listener = MagicMock()
        EventBus.on("draft_state_changed", mock_listener)
        EventBus.emit("league_disconnected")
        
        self.assertEqual(service.get_session(), {})
        mock_listener.assert_called_once_with(None)

    def test_on_champ_select_update(self):
        service = DraftService(self.mock_league)
        
        mock_listener = MagicMock()
        EventBus.on("draft_state_changed", mock_listener)
        EventBus.emit("champ_select_event", {"localPlayerCellId": 2})
        
        self.assertEqual(service.get_session(), {"localPlayerCellId": 2})
        mock_listener.assert_called_once_with({"localPlayerCellId": 2})

    @patch("threading.Thread")
    def test_select_champion_not_connected(self, mock_thread):
        self.mock_league.is_connected = False
        service = DraftService(self.mock_league)
        service.select_champion(24)
        mock_thread.assert_not_called()

    def test_swap_bench_champion(self):
        service = DraftService(self.mock_league)
        service.swap_bench_champion(24)
        self.mock_league.request.assert_called_once_with("POST", "/lol-champ-select/v1/session/bench/swap/24")

    def test_request_trade(self):
        service = MagicMock()
        service = DraftService(self.mock_league)
        service.request_trade(3)
        self.mock_league.request.assert_called_once_with("POST", "/lol-champ-select/v1/session/trades/3/request")

    def test_singleton(self):
        with patch("services.draft_service._instance", None):
            inst1 = get_draft_service(self.mock_league)
            inst2 = get_draft_service()
            self.assertIs(inst1, inst2)
