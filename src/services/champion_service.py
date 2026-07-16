"""
Champion Service
Centralizes access to champion metadata, role mappings, win/ban stats, and asset references.
"""
from services.asset_manager import AssetManager
from services.stats_scraper import StatsScraper
from core.events import EventBus
from utils.logger import Logger

class ChampionService:
    def __init__(self, asset_manager: AssetManager, stats_scraper: StatsScraper):
        self.assets = asset_manager
        self.scraper = stats_scraper
        
        # Monitor asset loading changes
        EventBus.on("assets_loaded", self._on_assets_loaded)

    def _on_assets_loaded(self):
        Logger.info("ChampionService", "Champion assets successfully loaded.")
        EventBus.emit("champion_state_changed")

    def get_champions(self) -> list:
        """Returns sorted list of all champion names."""
        if not self.assets or not self.assets.champ_data:
            return []
        return sorted([c["name"] for c in self.assets.champ_data.values()])

    def get_champion_by_id(self, champ_id: int) -> dict:
        """Retrieve full champion metadata dict by ID."""
        if not self.assets:
            return {}
        key = self.assets.id_to_key.get(champ_id)
        if key:
            return self.assets.champ_data.get(key, {})
        return {}

    def get_champion_id_by_name(self, name: str) -> int:
        if not self.assets:
            return 0
        return self.assets.name_to_id.get(name.strip().lower(), 0)

    def get_champion_roles(self, champ_id: int) -> list:
        if not self.assets:
            return []
        return self.assets.champ_roles.get(champ_id, [])

    def get_champion_stats(self, champ_name: str, queue_id: int = 450) -> dict:
        """Get winrate, pickrate, banrate, and tier for a champion."""
        if not self.scraper:
            return {"win_rate": 50.0, "pick_rate": 1.0, "ban_rate": 1.0, "tier": "A"}
            
        # StatsScraper gets stats. ARAM queue ID is 450.
        win_rate = self.scraper.get_win_rate(champ_name)
        # Construct stats dict (scraper has win rate baselines, others can be mocked/scaled)
        tier = "S+" if win_rate > 53.5 else "S" if win_rate > 51.5 else "A" if win_rate > 49.5 else "B" if win_rate > 47.5 else "D"
        return {
            "win_rate": round(win_rate, 2),
            "pick_rate": 5.0, # Placeholder
            "ban_rate": 2.0,  # Placeholder
            "tier": tier
        }

    def get_champion_icon(self, champ_id: int, size=(36, 36), callback=None, widget=None):
        """Asynchronously loads a champion profile icon and triggers a callback."""
        if not self.assets:
            return
        
        key = self.assets.id_to_key.get(champ_id)
        if not key:
            return

        self.assets.get_icon_async(
            "champion", key,
            lambda img: callback(img) if callback else None,
            size=size, widget=widget
        )

# Global singleton
_instance = None

def get_champion_service(asset_manager: AssetManager = None, stats_scraper: StatsScraper = None) -> ChampionService:
    global _instance
    if _instance is None and asset_manager is not None and stats_scraper is not None:
        _instance = ChampionService(asset_manager, stats_scraper)
    return _instance
