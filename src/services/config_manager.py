"""
Application configuration management for LeagueLoop.

Extracted from asset_manager for modularity and clearer ownership.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from utils.logger import Logger
from utils.path_utils import get_asset_path, get_data_dir

USER_DATA_DIR = get_data_dir()
USER_CONFIG_FILE = os.path.join(USER_DATA_DIR, "config.json")
BUNDLED_CONFIG_FILE = get_asset_path("config.json")

DEFAULT_CONFIG = {
    "auto_accept": False,
    "auto_requeue": False,
    "auto_pick": "",  # Legacy/Global Fallback
    "auto_pick_backup": "",
    "auto_ban": "",
    "custom_status": "🎮 LeagueLoop ⚙️ https://github.com/Intrusive-Thots/LeagueLoop.DEV",
    "auto_aram_swap": False,
    "auto_set_roles": False,
    "auto_hover": False,
    "auto_lock_in": False,
    "auto_random_skin": True,
    "accept_delay": 2.0,
    "polling_rate_champ_select": 0.5,  # Default to Fast for CS
    # Role-Based Picks (3 slots per role)
    "pick_TOP_1": "",
    "pick_TOP_2": "",
    "pick_TOP_3": "",
    "pick_JUNGLE_1": "",
    "pick_JUNGLE_2": "",
    "pick_JUNGLE_3": "",
    "pick_MIDDLE_1": "",
    "pick_MIDDLE_2": "",
    "pick_MIDDLE_3": "",
    "pick_BOTTOM_1": "",
    "pick_BOTTOM_2": "",
    "pick_BOTTOM_3": "",
    "pick_UTILITY_1": "",
    "pick_UTILITY_2": "",
    "pick_UTILITY_3": "",
    # Role-Based Bans
    "ban_TOP_1": "",
    "ban_TOP_2": "",
    "ban_TOP_3": "",
    "ban_JUNGLE_1": "",
    "ban_JUNGLE_2": "",
    "ban_JUNGLE_3": "",
    "ban_MIDDLE_1": "",
    "ban_MIDDLE_2": "",
    "ban_MIDDLE_3": "",
    "ban_BOTTOM_1": "",
    "ban_BOTTOM_2": "",
    "ban_BOTTOM_3": "",
    "ban_UTILITY_1": "",
    "ban_UTILITY_2": "",
    "ban_UTILITY_3": "",
    "always_on_top": True,
    "poro_snacks": 0,
    "stealth_mode": False,
    "hotkey_launch_client": "ctrl+shift+l",
    "hotkey_toggle_automation": "ctrl+shift+a",
    "hotkey_find_match": "ctrl+shift+f",
    "hotkey_compact_mode": "ctrl+shift+m",
    "priority_picker": {
        "enabled": True,
        "list": [
            "Nautilus",
            "Xerath",
            "Nunu & Willump",
            "Master Yi",
            "Veigar",
            "Lux",
            "Heimerdinger",
            "Nidalee",
            "Pyke",
            "Jhin"
        ]
    },
    "arena_pairs": [],
    "arena_auto_lock": False,
    "arena_synergy_enabled": True,
    "run_in_tray": True,
    "skip_stats_enabled": True,
    "auto_runes_enabled": False,
    "aram_auto_add_played": False
}


class ConfigManager:
    """Manages application configuration."""

    def __init__(self) -> None:
        """Initializes the ConfigManager."""
        self.cfg = DEFAULT_CONFIG.copy()

        # 1. Load bundled template first (transfers dev configurations to users)
        if os.path.exists(BUNDLED_CONFIG_FILE):
            try:
                with open(BUNDLED_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.cfg.update(json.load(f))
            except Exception as e:
                Logger.debug("Config", f"Bundled config load failed: {e}")

        # 2. Override with the user's local runtime config
        if os.path.exists(USER_CONFIG_FILE):
            try:
                with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.cfg.update(json.load(f))
            except Exception as e:
                Logger.error("config_manager.py", f"Handled exception: {type(e).__name__}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.cfg.get(key, default)

    def set(self, key: str, val: Any, save: bool = True) -> None:
        """Set a configuration value and optionally save to file."""
        self.cfg[key] = val
        if save:
            self.save()

    def set_batch(self, updates: dict, save: bool = True) -> None:
        """Set multiple configuration values and optionally save to file."""
        self.cfg.update(updates)
        if save:
            self.save()

    def save(self) -> None:
        """Save configuration to file securely in AppData using atomic write."""
        try:
            tmp_path = USER_CONFIG_FILE + ".tmp"
            os.makedirs(os.path.dirname(os.path.abspath(USER_CONFIG_FILE)), exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=4)
            os.replace(tmp_path, USER_CONFIG_FILE)
        except Exception as e:
            Logger.error("config_manager.py", f"Failed saving config: {e}")
