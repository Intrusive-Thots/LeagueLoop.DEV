"""
Header ViewModel
Manages the state and EventBus subscriptions for the main navigation header.
"""
from PySide6.QtCore import Signal
from ui.qt.viewmodels.base_viewmodel import BaseViewModel
from core.events import EventBus

class HeaderViewModel(BaseViewModel):
    # Signals emitted to the UI thread
    timer_text_changed = Signal(str)
    timer_visibility_changed = Signal(bool)
    profile_text_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Subscribe to background events
        EventBus.on("queue_timer_tick", self._on_timer_tick)
        EventBus.on("automation_queue_state", self._on_queue_state)
        EventBus.on("summoner_changed", self._on_summoner_changed)
        EventBus.on("league_disconnected", self._on_league_disconnected)

    def _on_timer_tick(self, current, estimated):
        cur_min, cur_sec = divmod(int(current), 60)
        est_min, est_sec = divmod(int(estimated), 60)
        text = f"⏳ {cur_min}:{cur_sec:02d} / {est_min}:{est_sec:02d}"
        self.timer_text_changed.emit(text)

    def _on_queue_state(self, phase, search_state):
        is_searching = phase in ["Matchmaking"] or (search_state and search_state.get("isSearching", False))
        self.timer_visibility_changed.emit(bool(is_searching))

    def _on_summoner_changed(self, info):
        if info:
            name = info.get("displayName", "")
            level = info.get("summonerLevel", 0)
            text = f"👤 {name} (Lv.{level})" if name else ""
            self.profile_text_changed.emit(text)

    def _on_league_disconnected(self):
        self.profile_text_changed.emit("")
        self.timer_visibility_changed.emit(False)
