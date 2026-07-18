"""
Draft Service
Manages champion select session state, hover actions, lock-ins, and trade requests.
"""
from core.events import EventBus
from services.league_service import get_league_service
from utils.logger import Logger

class DraftService:
    def __init__(self, league_service=None):
        self._league = league_service or get_league_service()
        self._session_cache = {}
        
        # Subscribe to LCU draft updates
        EventBus.on("champ_select_event", self._on_champ_select_update)
        EventBus.on("league_disconnected", self._on_disconnect)

    def _on_disconnect(self):
        self._session_cache = {}
        EventBus.emit("draft_state_changed", None)

    def _on_champ_select_update(self, session_data):
        if not session_data:
            self._session_cache = {}
            return
        
        data = session_data if isinstance(session_data, dict) else session_data.get("data", {})
        self._session_cache = data
        EventBus.emit("draft_state_changed", data)

    def get_session(self) -> dict:
        return self._session_cache

    def select_champion(self, champ_id: int, action_type="pick", lock_in=True):
        """Asynchronously pick or ban a champion in the current draft session."""
        if not self._league or not self._league.is_connected or not self._session_cache:
            return

        def task():
            try:
                # Find my action ID
                local_cell_id = self._session_cache.get("localPlayerCellId", -1)
                actions = self._session_cache.get("actions", [])
                
                my_action_id = -1
                for group in actions:
                    for act in group:
                        if act.get("actorCellId") == local_cell_id and act.get("type") == action_type and not act.get("completed"):
                            my_action_id = act.get("id", -1)
                            break
                
                if my_action_id == -1:
                    Logger.debug("DraftService", f"No active {action_type} action found for local player.")
                    return
                
                # Hover/Select
                url = f"/lol-champ-select/v1/session/actions/{my_action_id}"
                payload = {"championId": champ_id}
                self._league.request("PATCH", url, json=payload)
                
                # Lock-in
                if lock_in:
                    self._league.request("POST", f"{url}/complete")
            except Exception as e:
                Logger.error("DraftService", f"Select action failed: {e}")

        import threading
        threading.Thread(target=task, daemon=True).start()

    def swap_bench_champion(self, champ_id: int):
        """Swaps current pick with a champion on the bench (ARAM only)."""
        if not self._league or not self._league.is_connected:
            return
        
        url = f"/lol-champ-select/v1/session/bench/swap/{champ_id}"
        self._league.request("POST", url)

    def request_trade(self, cell_id: int):
        """Request trade with a teammate."""
        url = f"/lol-champ-select/v1/session/trades/{cell_id}/request"
        self._league.request("POST", url)

    def get_local_player(self) -> dict:
        """Get local player's data dict from the session cache."""
        local_cell_id = self._session_cache.get("localPlayerCellId", -1)
        my_team = self._session_cache.get("myTeam", [])
        return next((p for p in my_team if p.get("cellId") == local_cell_id), None)

    def get_my_active_action(self) -> dict:
        """Find the active action in progress for the local player."""
        local_cell_id = self._session_cache.get("localPlayerCellId", -1)
        actions = self._session_cache.get("actions", [])
        for group in actions:
            for act in group:
                if act.get("actorCellId") == local_cell_id and act.get("isInProgress"):
                    return act
        return None

    def get_banned_champion_ids(self) -> list:
        """Get all banned champion IDs in the session."""
        banned = []
        for b in self._session_cache.get("bannedChampions", []):
            if isinstance(b, dict):
                banned.append(b.get("championId", 0))
            else:
                banned.append(b)
        return banned

# Global singleton
_instance = None

def get_draft_service(league_service=None) -> DraftService:
    global _instance
    if _instance is None:
        _instance = DraftService(league_service)
    return _instance
