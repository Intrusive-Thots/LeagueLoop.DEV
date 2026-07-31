"""
Champions ViewModel
Manages the champion grid logic, prioritizing, and EventBus subscriptions for ChampionsPage.
"""
from PySide6.QtCore import Signal
from ui.qt.viewmodels.base_viewmodel import BaseViewModel
from services.settings_service import get_settings_service
from services.league_service import get_league_service
from services.stats_scraper import get_stats_scraper
from core.events import EventBus

class ChampionsViewModel(BaseViewModel):
    # Signals
    league_connected = Signal(object)
    masteries_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        self.league_service = get_league_service()
        self.stats_scraper = get_stats_scraper()

        EventBus.on("league_connected", self._on_league_connected)

    def get_setting(self, key, default=None):
        return self.config.get(key, default)

    def set_setting(self, key, value):
        self.config.set(key, value)

    def save_settings(self):
        self.config.save()

    def get_stats_sync(self):
        return self.stats_scraper.get_stats_sync()

    def get_league_service(self):
        return self.league_service

    def _on_league_connected(self, event_data):
        self.league_connected.emit(event_data)
