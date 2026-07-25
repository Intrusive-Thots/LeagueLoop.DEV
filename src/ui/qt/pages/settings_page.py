"""
PySide6 Settings Page Component
Manages advanced configurations, hotkeys, status updates, and presets.
Refactored to MVVM architecture.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel
)

from ui.qt.widgets.scrollable_list import ScrollableList
from ui.qt.widgets.components import SectionHeader, CleanSettingRow
from ui.qt.widgets.inputs import SettingsSliderRow, SettingsHotkeyRow
from ui.qt.viewmodels.settings_viewmodel import SettingsViewModel
from ui.qt.widgets.toast import ToastManager


class SettingsPage(ScrollableList):
    """The PySide6 Settings Page using SettingsViewModel."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewmodel = SettingsViewModel(self)
        self.viewmodel.config_changed.connect(self._on_config_changed)
        
        self.container_layout.setContentsMargins(14, 14, 14, 14)
        self.container_layout.setSpacing(10)
        
        self.setup_ui()

    def setup_ui(self):
        # ─── 1. LOBBY & MATCHMAKING ───
        self.add_widget(SectionHeader("Lobby & Matchmaking", "Queue accept behaviors and delays"))
        
        row_accept = CleanSettingRow(
            "Auto-Accept Ready Check",
            "Automatically accept queue pops",
            self.viewmodel.get_setting("auto_accept", True),
            self
        )
        row_accept.toggled.connect(lambda v: self.viewmodel.set_setting("auto_accept", v))
        self.add_widget(row_accept)
        
        accept_delay = float(self.viewmodel.get_setting("accept_delay", 2.0))
        row_delay = SettingsSliderRow(
            self,
            label_text="Accept Delay",
            initial_value=accept_delay,
            on_change=lambda v: self.viewmodel.set_setting("accept_delay", float(v))
        )
        self.add_widget(row_delay)
        
        row_requeue = CleanSettingRow(
            "Auto-Requeue After Dodge",
            "Re-enter queue if someone dodges",
            self.viewmodel.get_setting("auto_requeue_after_dodge", True),
            self
        )
        row_requeue.toggled.connect(lambda v: self.viewmodel.set_setting("auto_requeue_after_dodge", v))
        self.add_widget(row_requeue)
        
        # ─── 2. CHAMPION SELECT AUTOMATION ───
        self.add_widget(SectionHeader("Champion Select", "Bench sniping, rune import, and skins"))
        
        row_pick = CleanSettingRow(
            "Auto-Pick Priority Champion",
            "Automatically claim high priority champions",
            self.viewmodel.get_setting("auto_pick", True),
            self
        )
        row_pick.toggled.connect(lambda v: self.viewmodel.set_setting("auto_pick", v))
        self.add_widget(row_pick)
        
        row_ban = CleanSettingRow(
            "Auto-Ban Blacklist Champion",
            "Ban configured blacklist targets",
            self.viewmodel.get_setting("auto_ban", False),
            self
        )
        row_ban.toggled.connect(lambda v: self.viewmodel.set_setting("auto_ban", v))
        self.add_widget(row_ban)
        
        row_runes = CleanSettingRow(
            "Auto-Import Optimal Runes",
            "Apply high win rate rune pages",
            self.viewmodel.get_setting("auto_runes", True),
            self
        )
        row_runes.toggled.connect(lambda v: self.viewmodel.set_setting("auto_runes", v))
        self.add_widget(row_runes)
        
        row_skin = CleanSettingRow(
            "Auto-Equip Favorite Skin",
            "Equip your favorite owned skin",
            self.viewmodel.get_setting("auto_skin", True),
            self
        )
        row_skin.toggled.connect(lambda v: self.viewmodel.set_setting("auto_skin", v))
        self.add_widget(row_skin)
        
        # ─── 3. APP PREFERENCES ───
        self.add_widget(SectionHeader("App Preferences", "Client integration and background tray"))
        
        row_autolaunch = CleanSettingRow(
            "Auto-Launch Client on Disconnect",
            "Relaunch League client automatically",
            self.viewmodel.get_setting("auto_launch_client", False),
            self
        )
        row_autolaunch.toggled.connect(lambda v: self.viewmodel.set_setting("auto_launch_client", v))
        self.add_widget(row_autolaunch)
        
        row_tray = CleanSettingRow(
            "Minimize to System Tray",
            "Keep running silently in tray",
            self.viewmodel.get_setting("run_in_tray", True),
            self
        )
        row_tray.toggled.connect(lambda v: self.viewmodel.set_setting("run_in_tray", v))
        self.add_widget(row_tray)
        
        row_discord = CleanSettingRow(
            "Discord Rich Presence",
            "Broadcast active mode and status to Discord",
            self.viewmodel.get_setting("discord_rpc_enabled", True),
            self
        )
        row_discord.toggled.connect(lambda v: self.viewmodel.set_setting("discord_rpc_enabled", v))
        self.add_widget(row_discord)

        # ─── 4. GLOBAL HOTKEYS ───
        self.add_widget(SectionHeader("Global Hotkeys", "Keyboard shortcuts for instant automation"))
        
        hotkeys = [
            ("Toggle Automation", "hotkey_toggle_automation", "f3"),
            ("Trigger Matchmaking", "hotkey_find_match", "f4"),
        ]
        
        for label_text, config_key, default_val in hotkeys:
            current_val = self.viewmodel.get_setting(config_key, default_val)
            row_hk = SettingsHotkeyRow(
                self,
                label_text=label_text,
                config_key=config_key,
                default_val=current_val,
                on_change=lambda val, k=config_key: self.viewmodel.set_setting(k, val)
            )
            self.add_widget(row_hk)

    def _on_config_changed(self, key: str, val: object):
        toast = ToastManager.get_instance()
        if toast:
            toast.show(f"Saved: {key}", icon="⚙️", theme="info")
