"""
Friend Service
Handles fetching, updating, sorting, and configuring friend data (including Auto-Join status).
"""
import threading
from core.events import EventBus
from services.league_service import get_league_service
from services.settings_service import get_settings_service
from utils.logger import Logger

class FriendService:
    def __init__(self, settings_service=None, league_service=None):
        self._settings = settings_service or get_settings_service()
        self._league = league_service or get_league_service()
        self._friends_cache = []
        self._auto_join_names = {}
        
        # Load initial config
        self._load_config()
        
        # Subscribe to LCU friend events
        EventBus.on("friends_event", self._on_friends_update)
        EventBus.on("league_connected", self._on_league_connected)
        EventBus.on("setting_changed:auto_join_list", self._on_auto_join_list_changed)

    def _load_config(self):
        if self._settings:
            self._auto_join_names = {
                f.get("name", "").lower(): f.get("enabled", True)
                for f in self._settings.get("auto_join_list", [])
            }

    def _on_auto_join_list_changed(self, val):
        self._load_config()
        EventBus.emit("friends_state_changed")

    def _on_league_connected(self):
        self.fetch_friends()

    def _on_friends_update(self, friends_data):
        if not friends_data:
            return
        if isinstance(friends_data, list):
            self._process_friends(friends_data)
        elif isinstance(friends_data, dict):
            self._merge_friend_delta(friends_data)

    def fetch_friends(self):
        """Fetch the friends list from LCU Client asynchronously."""
        if not self._league or not self._league.is_connected:
            return

        def task():
            try:
                res = self._league.request("GET", "/lol-chat/v1/friends", silent=True)
                if res and res.status_code == 200:
                    self._process_friends(res.json())
            except Exception as e:
                Logger.error("FriendService", f"Error fetching friends: {e}")

        threading.Thread(target=task, daemon=True).start()

    def _process_friends(self, friends):
        for f in friends:
            f["_name_lower"] = (f.get("gameName", "") or f.get("name", "")).lower()

        # Sort friends: online first, then by name
        def sort_key(f):
            avail = f.get("availability", "offline")
            gn = f.get("_name_lower", "")
            prio = 1 if avail == "offline" else 0
            return (prio, gn)

        friends.sort(key=sort_key)
        self._friends_cache = friends
        EventBus.emit("friends_state_changed")

    def _merge_friend_delta(self, delta):
        puuid = delta.get("puuid") or delta.get("id")
        if not puuid:
            self.fetch_friends()
            return

        updated = False
        for i, f in enumerate(self._friends_cache):
            if f.get("puuid") == puuid or f.get("id") == puuid:
                self._friends_cache[i].update(delta)
                updated = True
                break
        
        if not updated:
            self._friends_cache.append(delta)
        
        self._process_friends(self._friends_cache)

    def get_friends(self) -> list:
        return self._friends_cache

    def get_auto_join_status(self, name: str) -> bool:
        return self._auto_join_names.get(name.lower(), False)

    def toggle_auto_join(self, name: str):
        name_lower = name.lower()
        is_enabled = not self._auto_join_names.get(name_lower, False)
        self._auto_join_names[name_lower] = is_enabled
        
        # Save updates back to settings
        if self._settings:
            lst = [{"name": n, "enabled": e} for n, e in self._auto_join_names.items()]
            self._settings.set("auto_join_list", lst)
        
        EventBus.emit("friends_state_changed")

    def invite_friend(self, summoner_id: int):
        """Invite a friend to lobby."""
        if not self._league or not self._league.is_connected:
            return
        
        payload = [{"toSummonerId": summoner_id}]
        self._league.request("POST", "/lol-lobby/v2/lobby/invitations", json=payload)

# Global singleton
_instance = None

def get_friend_service(settings_service=None, league_service=None) -> FriendService:
    global _instance
    if _instance is None:
        _instance = FriendService(settings_service, league_service)
    return _instance
