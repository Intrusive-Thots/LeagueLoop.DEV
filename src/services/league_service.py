"""
League Service
Centralizes LCU client interactions, connection status, and WebSocket subscription mappings.
"""
from services.api_handler import LCUClient
from core.events import EventBus
from utils.logger import Logger
import threading
import time

class LeagueService:
    def __init__(self, lcu_client: LCUClient):
        self.lcu = lcu_client
        self._phase = "None"
        self._summoner_info = {}

        # Subscribe to connection events
        EventBus.on("lcu_connected", self._on_lcu_connection_change)

        # Subscribe to WebSocket events once LCU is connected
        self.lcu.subscribe("OnJsonApiEvent_lol-gameflow_v1_gameflow-phase", self._on_gameflow_phase_event)
        self.lcu.subscribe("OnJsonApiEvent_lol-summoner_v1_current-summoner", self._on_summoner_event)

    @property
    def is_connected(self) -> bool:
        return self.lcu.is_connected

    def get_phase(self) -> str:
        if not self.is_connected:
            return "None"
        return self._phase

    def get_summoner_info(self) -> dict:
        return self._summoner_info

    def request(self, method: str, endpoint: str, *args, **kwargs):
        """Perform REST request directly to the LCU API."""
        return self.lcu.request(method, endpoint, *args, **kwargs)

    def get_champion_masteries(self) -> list:
        """Fetch summoner's champion mastery records from LCU collections."""
        if not self.is_connected or not self._summoner_info:
            return []
        summoner_id = self._summoner_info.get("summonerId")
        if not summoner_id:
            return []
        try:
            resp = self.request("GET", f"/lol-collections/v1/inventories/{summoner_id}/champion-mastery")
            if resp and resp.status_code == 200:
                return resp.json()
        except Exception as e:
            Logger.error("LeagueService", f"Failed to fetch champion masteries: {e}")
        return []

    def _on_lcu_connection_change(self, connected: bool):
        Logger.info("LeagueService", f"LCU Connection status changed: {connected}")
        if not connected:
            self._phase = "None"
            self._summoner_info = {}
            EventBus.emit("league_disconnected")
        else:
            EventBus.emit("league_connected")
            # Fetch initial state asynchronously
            threading.Thread(target=self._fetch_initial_state, daemon=True).start()

    def _fetch_initial_state(self):
        try:
            # 1. Fetch current gameflow phase
            resp = self.request("GET", "/lol-gameflow/v1/gameflow-phase")
            if resp and resp.status_code == 200:
                self._phase = resp.json()
                Logger.info("LeagueService", f"Initial game phase: {self._phase}")
                EventBus.emit("game_phase_changed", self._phase)

            # 2. Fetch current summoner info
            resp = self.request("GET", "/lol-summoner/v1/current-summoner")
            if resp and resp.status_code == 200:
                self._summoner_info = resp.json()
                Logger.info("LeagueService", f"Summoner identified: {self._summoner_info.get('displayName')}")
                EventBus.emit("summoner_changed", self._summoner_info)
        except Exception as e:
            Logger.error("LeagueService", f"Failed to fetch initial state: {e}")

    def _on_gameflow_phase_event(self, event):
        """Called on WebSocket gameflow phase updates."""
        try:
            data = event.get("data")
            if data and data != self._phase:
                self._phase = data
                Logger.info("LeagueService", f"Game phase update: {self._phase}")
                EventBus.emit("game_phase_changed", self._phase)
        except Exception as e:
            Logger.error("LeagueService", f"Error parsing gameflow phase event: {e}")

    def _on_summoner_event(self, event):
        """Called on WebSocket current-summoner updates."""
        try:
            data = event.get("data")
            if data and data != self._summoner_info:
                self._summoner_info = data
                Logger.info("LeagueService", f"Summoner update: {self._summoner_info.get('displayName')}")
                EventBus.emit("summoner_changed", self._summoner_info)
        except Exception as e:
            Logger.error("LeagueService", f"Error parsing summoner event: {e}")

# Global singleton
_instance = None

def get_league_service(lcu_client: LCUClient = None) -> LeagueService:
    global _instance
    if _instance is None and lcu_client is not None:
        _instance = LeagueService(lcu_client)
    return _instance
