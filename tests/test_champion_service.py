import unittest
from unittest.mock import MagicMock, patch
from core.events import EventBus
from services.champion_service import ChampionService, get_champion_service

class TestChampionService(unittest.TestCase):
    def setUp(self):
        EventBus._listeners.clear()
        self.mock_assets = MagicMock()
        self.mock_scraper = MagicMock()

    def test_on_assets_loaded(self):
        service = ChampionService(self.mock_assets, self.mock_scraper)
        mock_listener = MagicMock()
        EventBus.on("champion_state_changed", mock_listener)
        EventBus.emit("assets_loaded")
        mock_listener.assert_called_once()

    def test_get_champions(self):
        self.mock_assets.champ_data = {
            "Jax": {"name": "Jax"},
            "Ashe": {"name": "Ashe"}
        }
        service = ChampionService(self.mock_assets, self.mock_scraper)
        self.assertEqual(service.get_champions(), ["Ashe", "Jax"])

    def test_get_champion_by_id(self):
        self.mock_assets.id_to_key = {24: "Jax"}
        self.mock_assets.champ_data = {"Jax": {"name": "Jax", "id": 24}}
        service = ChampionService(self.mock_assets, self.mock_scraper)
        
        self.assertEqual(service.get_champion_by_id(24), {"name": "Jax", "id": 24})
        self.assertEqual(service.get_champion_by_id(999), {})

    def test_get_champion_id_by_name(self):
        self.mock_assets.name_to_id = {"jax": 24}
        service = ChampionService(self.mock_assets, self.mock_scraper)
        self.assertEqual(service.get_champion_id_by_name("Jax"), 24)
        self.assertEqual(service.get_champion_id_by_name("Ashe"), 0)

    def test_get_champion_roles(self):
        self.mock_assets.champ_roles = {24: ["TOP", "JUNGLE"]}
        service = ChampionService(self.mock_assets, self.mock_scraper)
        self.assertEqual(service.get_champion_roles(24), ["TOP", "JUNGLE"])
        self.assertEqual(service.get_champion_roles(999), [])

    def test_get_champion_stats(self):
        self.mock_scraper.get_win_rate.return_value = 54.0
        service = ChampionService(self.mock_assets, self.mock_scraper)
        
        stats = service.get_champion_stats("Jax")
        self.assertEqual(stats["win_rate"], 54.0)
        self.assertEqual(stats["tier"], "S+")

    def test_get_champion_icon(self):
        self.mock_assets.id_to_key = {24: "Jax"}
        service = ChampionService(self.mock_assets, self.mock_scraper)
        
        callback = MagicMock()
        service.get_champion_icon(24, callback=callback)
        self.mock_assets.get_icon_async.assert_called_once()

    def test_singleton(self):
        with patch("services.champion_service._instance", None):
            inst1 = get_champion_service(self.mock_assets, self.mock_scraper)
            inst2 = get_champion_service()
            self.assertIs(inst1, inst2)
