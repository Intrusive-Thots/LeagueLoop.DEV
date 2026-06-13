import unittest
from unittest.mock import MagicMock, patch

from services.stats_scraper import StatsScraper
from services.automation import AutomationEngine
from services.local_api import LeagueLoopAPIHandler
from core.constants import QUEUE_ARENA, QUEUE_ARENA_3V6

class TestArena3v6(unittest.TestCase):
    def test_stats_scraper_arena_3v6(self):
        """Test that StatsScraper correctly maps queue ID 1710 to Arena 3v6."""
        scraper = StatsScraper()
        scraper.set_mode_by_queue_id(1710)
        self.assertEqual(scraper.mode, "Arena 3v6")
        
        # Win rates should match BASELINE_ARENA_WINRATES
        from services.stats_scraper import BASELINE_ARENA_WINRATES
        self.assertEqual(scraper.win_rates, BASELINE_ARENA_WINRATES)

    def test_automation_engine_is_arena(self):
        """Test that AutomationEngine handles both QUEUE_ARENA and QUEUE_ARENA_3V6 as arena modes."""
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
        
        # Mock sub-handlers to avoid running unrelated logic
        engine._handle_auto_dodge = MagicMock()
        engine._handle_chat_warden = MagicMock()
        engine._perform_priority_sniper = MagicMock()
        engine._perform_arena_synergy = MagicMock()
        engine._perform_draft_assistant = MagicMock()
        engine._equip_random_skin = MagicMock()
        engine._auto_equip_runes = MagicMock()

        session = {
            "localPlayerCellId": 1,
            "myTeam": [{"cellId": 1, "assignedPosition": "", "championId": 10}]
        }

        # Case 1: QUEUE_ARENA (1700)
        engine.current_queue_id = QUEUE_ARENA
        engine._handle_champ_select("ChampSelect", session)
        engine._perform_arena_synergy.assert_called_once_with(session)
        engine._perform_draft_assistant.assert_not_called()
        
        # Reset mock
        engine._perform_arena_synergy.reset_mock()

        # Case 2: QUEUE_ARENA_3V6 (1710)
        engine.current_queue_id = QUEUE_ARENA_3V6
        engine._handle_champ_select("ChampSelect", session)
        engine._perform_arena_synergy.assert_called_once_with(session)
        engine._perform_draft_assistant.assert_not_called()

    def test_local_api_handler_queue_modes(self):
        """Test that LeagueLoopAPIHandler returns Arena 3v6 mode mapping."""
        # Create a mock server that has app_instance
        mock_server = MagicMock()
        mock_server.app_instance = MagicMock()
        
        # We can just verify the modes dict itself is accessible or mock http request
        # But even simpler: LeagueLoopAPIHandler has a modes dict inside do_GET
        # We can construct the handler and verify the path mapping via mocking do_GET's wfile.write
        handler = LeagueLoopAPIHandler.__new__(LeagueLoopAPIHandler)
        handler.server = mock_server
        handler.path = "/queue-modes"
        handler.headers = {}
        handler.wfile = MagicMock()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        
        import json
        handler.do_GET()
        
        # Verify response was sent
        handler.send_response.assert_called_with(200)
        
        # Verify the written json contains Arena 3v6
        written_bytes = handler.wfile.write.call_args[0][0]
        written_data = json.loads(written_bytes.decode('utf-8'))
        self.assertIn("modes", written_data)
        self.assertEqual(written_data["modes"]["Arena 3v6"], 1710)
        self.assertEqual(written_data["modes"]["Arena"], 1700)

if __name__ == '__main__':
    unittest.main()
