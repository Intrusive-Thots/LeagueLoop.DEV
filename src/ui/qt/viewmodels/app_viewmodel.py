"""
App ViewModel
Manages the outer application shell state, connection polling, and global automation toggling.
"""
from PySide6.QtCore import Signal
from ui.qt.viewmodels.base_viewmodel import BaseViewModel
from services.league_service import get_league_service
from services.settings_service import get_settings_service
from core.events import EventBus

class AppViewModel(BaseViewModel):
    # Signals
    league_connected = Signal()
    league_disconnected = Signal()
    queue_state_changed = Signal(str, str) # phase, search_state

    def __init__(self, parent=None):
        super().__init__(parent)
        self.league_service = get_league_service()
        self.config = get_settings_service()

        EventBus.on("league_connected", self._on_connected)
        EventBus.on("league_disconnected", self._on_disconnected)
        EventBus.on("automation_queue_state", self._on_queue_state)

        # We need a reference to the global engine to toggle power
        # For now, we will fire an event that the engine listens to, or call the state manager

    def _on_connected(self, *args):
        self.league_connected.emit()

    def _on_disconnected(self, *args):
        self.league_disconnected.emit()

    def _on_queue_state(self, phase, search_state):
        self.queue_state_changed.emit(phase, search_state)

    def toggle_power(self, state: bool):
        # We emit a global event that the automation engine handles
        EventBus.emit("toggle_automation_power", state)

    def get_mode_string(self):
        # Read the current mode from config if the engine doesn't broadcast it
        # The engine stores the queue ID in state or config
        mode = self.config.get("queue_id", 450)
        if mode == 450: return "ARAM Mode"
        elif mode == 1900: return "Classic Mode"
        elif mode == 420: return "Solo/Duo Mode"
        elif mode == 440: return "Flex Mode"
        elif mode == 400: return "Draft Mode"
        return f"{self.config.get('aram_mode', 'ARAM')} Mode"
