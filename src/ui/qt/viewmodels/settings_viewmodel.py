"""
Settings ViewModel
Manages updating and retrieving application configuration via the Settings Service.
"""
from PySide6.QtCore import Signal
from ui.qt.viewmodels.base_viewmodel import BaseViewModel
from services.settings_service import get_settings_service

class SettingsViewModel(BaseViewModel):
    # Signals
    config_changed = Signal(str, object) # key, new_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()

    def get_setting(self, key: str, default: any = None) -> any:
        return self.config.get(key, default)

    def set_setting(self, key: str, value: any):
        """Proxy to the settings service to centralize state modification."""
        self.config.set(key, value)
        self.config_changed.emit(key, value)
