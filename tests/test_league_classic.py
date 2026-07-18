import unittest
from unittest.mock import MagicMock, patch

from services.stats_scraper import StatsScraper
from services.automation import AutomationEngine
from services.api import LeagueLoopAPIHandler
from core.constants import QUEUE_CLASSIC, QUEUE_DRAFT

class TestLeagueClassic(unittest.TestCase):
    def test_stats_scraper_league_classic(self):
        """Test that StatsScraper correctly maps queue ID 1900 to League Classic."""
        scraper = StatsScraper(fetch_live=False)
        scraper.set_mode_by_queue_id(1900)
        self.assertEqual(scraper.mode, "League Classic")
        
        # Win rates should match BASELINE_RANKED_WINRATES
        from services.stats_scraper import BASELINE_RANKED_WINRATES
        self.assertEqual(scraper.win_rates, BASELINE_RANKED_WINRATES)

    def test_automation_engine_is_classic_draft(self):
        """Test that AutomationEngine handles QUEUE_CLASSIC as a draft mode."""
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

        # Case 1: QUEUE_CLASSIC (1900)
        engine.current_queue_id = QUEUE_CLASSIC
        engine._handle_champ_select("ChampSelect", session)
        engine._perform_draft_assistant.assert_called_once_with(session)
        engine._perform_arena_synergy.assert_not_called()

    def test_local_api_handler_queue_modes_classic(self):
        """Test that LeagueLoopAPIHandler returns League Classic mode mapping."""
        mock_server = MagicMock()
        mock_server.app_instance = MagicMock()
        
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
        
        # Verify the written json contains League Classic
        written_bytes = handler.wfile.write.call_args[0][0]
        written_data = json.loads(written_bytes.decode('utf-8'))
        self.assertIn("modes", written_data)
        self.assertEqual(written_data["modes"]["League Classic"], 1900)

if __name__ == '__main__':
    unittest.main()
