"""
Play ViewModel
Manages the application state, queue actions, and automation toggles for the Play Page.
"""
from PySide6.QtCore import Signal
from ui.qt.viewmodels.base_viewmodel import BaseViewModel
from core.events import EventBus
from services.queue_service import get_queue_service
from services.friend_service import get_friend_service
from services.settings_service import get_settings_service
from utils.logger import Logger
from utils.thread_utils import run_in_background

class PlayViewModel(BaseViewModel):
    # Signals emitted to UI
    connection_status_changed = Signal(bool)
    queue_status_changed = Signal(str, str) # Phase string, UI text state
    friends_list_updated = Signal(list)
    action_completed = Signal(bool, str) # success, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        self.queue_service = get_queue_service()
        self.friend_service = get_friend_service()

        EventBus.on("automation_queue_state", self._on_queue_state_changed)
        EventBus.on("league_connected", self._on_league_connected)
        EventBus.on("league_disconnected", self._on_league_disconnected)
        EventBus.on("friends_state_changed", self._on_friends_updated)

    # --- Actions ---
    def find_match(self):
        def task():
            success = self.queue_service.find_match()
            if success:
                self.action_completed.emit(True, "Searching for Match...")
            else:
                self.action_completed.emit(False, "Queue Search Failed")
        run_in_background(task)

    def set_game_mode(self, mode: str):
        self.config.set("aram_mode", mode)
        
    def set_automation_states(self, state_dict: dict):
        for key, val in state_dict.items():
            self.config.set(key, val)

    # --- Event Handlers (Called on Background Threads) ---
    def _on_league_connected(self):
        self.connection_status_changed.emit(True)

    def _on_league_disconnected(self):
        self.connection_status_changed.emit(False)

    def _on_queue_state_changed(self, phase, state):
        self.queue_status_changed.emit(phase, phase)

    def _on_friends_updated(self):
        try:
            friends = self.friend_service.get_friends()
            online_friends = [f for f in friends if f.get("availability", "offline") != "offline"]
            # Extract simple data structure to pass to UI safely
            friend_data = []
            for f in online_friends[:8]:
                friend_data.append({
                    "name": f.get("name", f.get("gameName", "Friend")),
                    "status": f.get("availability", "online")
                })
            self.friends_list_updated.emit(friend_data)
        except Exception as e:
            Logger.error("PlayViewModel", f"Error updating friends preview: {e}")
