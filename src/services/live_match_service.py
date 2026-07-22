"""
Live Match Service
──────────────────
Connects to the local League of Legends In-Game Live Client Data API (port 2999)
during active gameplay to provide real-time match analytics, team comp stats,
gold leads, objective trackers, and live damage breakdowns.
"""
import urllib3
import requests
import warnings
from typing import Dict, Any, Optional, List
from utils.logger import Logger
from core.events import EventBus

LIVE_CLIENT_URL = "https://127.0.0.1:2999/liveclientdata"


class LiveMatchService:
    """Queries live in-game data and calculates real-time match statistics."""

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.is_active = False
        self._last_data: Dict[str, Any] = {}

    def fetch_all_game_data(self) -> Optional[Dict[str, Any]]:
        """Fetch complete live game state from port 2999."""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
                res = self.session.get(f"{LIVE_CLIENT_URL}/allgamedata", timeout=2)
                if res.status_code == 200:
                    data = res.json()
                    self._last_data = data
                    self.is_active = True
                    return data
        except Exception:
            pass
        self.is_active = False
        return None

    def get_match_summary(self) -> Dict[str, Any]:
        """Parse raw game data into structured live match metrics."""
        data = self._last_data or {}
        players = data.get("allPlayers", [])
        
        blue_kills, red_kills = 0, 0
        blue_gold, red_gold = 0, 0
        blue_players, red_players = [], []

        for p in players:
            team = p.get("team", "ORDER")
            scores = p.get("scores", {})
            kills = scores.get("kills", 0)
            items = p.get("items", [])
            item_gold = sum(i.get("price", 0) for i in items if isinstance(i, dict))

            info = {
                "name": p.get("summonerName", ""),
                "champion": p.get("championName", ""),
                "kills": kills,
                "deaths": scores.get("deaths", 0),
                "assists": scores.get("assists", 0),
                "cs": scores.get("creepScore", 0),
                "team": team,
            }

            if team == "ORDER":  # Blue Team
                blue_kills += kills
                blue_gold += item_gold
                blue_players.append(info)
            else:  # Red Team / CHAOS
                red_kills += kills
                red_gold += item_gold
                red_players.append(info)

        return {
            "in_game": self.is_active,
            "game_time": data.get("gameData", {}).get("gameTime", 0.0),
            "blue_kills": blue_kills,
            "red_kills": red_kills,
            "blue_gold": blue_gold,
            "red_gold": red_gold,
            "gold_diff": blue_gold - red_gold,
            "blue_players": blue_players,
            "red_players": red_players,
        }


_instance: Optional[LiveMatchService] = None


def get_live_match_service() -> LiveMatchService:
    global _instance
    if _instance is None:
        _instance = LiveMatchService()
    return _instance
