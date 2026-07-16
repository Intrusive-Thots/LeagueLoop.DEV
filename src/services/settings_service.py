"""
Settings Service
Wraps ConfigManager and emits EventBus events on settings changes.
"""
from services.asset_manager import ConfigManager
from core.events import EventBus
from utils.logger import Logger

class SettingsService:
    def __init__(self, config_manager: ConfigManager):
        self._config = config_manager

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, val, save=True):
        old_val = self._config.get(key)
        if old_val != val:
            self._config.set(key, val, save=save)
            Logger.info("SettingsService", f"Setting changed: {key} = {val}")
            EventBus.emit(f"setting_changed:{key}", val)
            EventBus.emit("setting_changed", key, val)

    def set_batch(self, updates: dict, save=True):
        for key, val in updates.items():
            self.set(key, val, save=False)
        if save:
            self._config.save()
            
    def save(self):
        self._config.save()

# Global singleton will be instantiated with the app config manager
_instance = None

def get_settings_service(config_manager: ConfigManager = None) -> SettingsService:
    global _instance
    if _instance is None and config_manager is not None:
        _instance = SettingsService(config_manager)
    return _instance
