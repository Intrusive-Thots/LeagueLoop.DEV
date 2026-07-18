"""
PySide6 Play Page Component
Handles play controls, matchmaking queue states, and quick automation toggles.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QSizePolicy
)
from PySide6.QtCore import Qt, QMetaObject, Slot, Q_ARG
from PySide6.QtGui import QColor

from ui.qt.widgets import ScrollableList, make_card, make_button
from ui.qt.theme import get_theme_color, get_theme_radius, get_theme_spacing
from ui.qt.pages.settings_page import SettingsToggleRow
from services.queue_service import get_queue_service
from services.league_service import get_league_service
from services.settings_service import get_settings_service
from services.window_service import get_window_service
from core.events import EventBus
from utils.logger import Logger
from utils.thread_utils import run_in_background

class PlayPage(QWidget):
    """Modern dashboard for active matchmaking and core engine automation toggles."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        self.queue_service = get_queue_service()
        self.league_service = get_league_service()
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # Scroll area for compact height compatibility
        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)
        
        # ── 1. SESSION HEADER CARD ──
        self.header_card = make_card(self)
        self.header_layout = QVBoxLayout(self.header_card)
        self.header_layout.setSpacing(6)
        
        self.lbl_game_mode = QLabel("ARAM MODE", self)
        self.lbl_game_mode.setStyleSheet("font-weight: bold; color: #F0E6D2; font-size: 14px;")
        self.header_layout.addWidget(self.lbl_game_mode)
        
        self.lbl_phase = QLabel("Phase: Idle", self)
        self.lbl_phase.setStyleSheet("color: #6C757D; font-size: 11px;")
        self.header_layout.addWidget(self.lbl_phase)
        
        # Queue progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #151F2F;
                border: 1px solid #1E2839;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: #C8AA6E;
                border-radius: 3px;
            }}
        """)
        self.header_layout.addWidget(self.progress_bar)
        
        self.lbl_timer = QLabel("0:00 / 0:00", self)
        self.lbl_timer.setStyleSheet("color: #C8AA6E; font-size: 11px;")
        self.header_layout.addWidget(self.lbl_timer)
        
        self.scroll.add_widget(self.header_card)
        
        # ── 2. MATCHMAKING ACTIONS CARD ──
        self.actions_card = make_card(self)
        self.actions_layout = QVBoxLayout(self.actions_card)
        self.actions_layout.setSpacing(8)
        
        # Find Match Button
        self.btn_find_match = make_button(self, text="▶  Find Match", style="primary")
        self.btn_find_match.clicked.connect(self._on_find_match_clicked)
        self.actions_layout.addWidget(self.btn_find_match)
        
        # Row for Dodge & Requeue
        self.row_quick = QWidget(self)
        self.row_quick_layout = QHBoxLayout(self.row_quick)
        self.row_quick_layout.setContentsMargins(0, 0, 0, 0)
        self.row_quick_layout.setSpacing(6)
        
        self.btn_requeue = make_button(self, text="Requeue", style="secondary")
        self.btn_requeue.clicked.connect(self._on_requeue_clicked)
        self.row_quick_layout.addWidget(self.btn_requeue)
        
        self.btn_dodge = make_button(self, text="Dodge", style="danger")
        self.btn_dodge.clicked.connect(self._on_dodge_clicked)
        self.row_quick_layout.addWidget(self.btn_dodge)
        
        self.actions_layout.addWidget(self.row_quick)
        
        # Play Again Button
        self.btn_play_again = make_button(self, text="🔄  Play Again", style="primary")
        self.btn_play_again.clicked.connect(self._on_play_again_clicked)
        self.btn_play_again.setVisible(False)
        self.actions_layout.addWidget(self.btn_play_again)
        
        # Launch Client Button
        self.btn_launch_client = make_button(self, text="🚀  Launch Client", style="secondary")
        self.btn_launch_client.clicked.connect(self._on_launch_client_clicked)
        self.btn_launch_client.setVisible(False)
        self.actions_layout.addWidget(self.btn_launch_client)
        
        self.scroll.add_widget(self.actions_card)
        
        # ── 3. AUTOMATION SETTINGS CARD ──
        self.toggles_card = make_card(self)
        self.toggles_layout = QVBoxLayout(self.toggles_card)
        self.toggles_layout.setSpacing(10)
        
        self.lbl_toggles_title = QLabel("AUTOMATION ENGINES", self)
        self.lbl_toggles_title.setStyleSheet("font-weight: bold; color: #C8AA6E; font-size: 11px; margin-bottom: 4px;")
        self.toggles_layout.addWidget(self.lbl_toggles_title)
        
        # Add all individual toggles
        self.row_accept = SettingsToggleRow(
            self, "Auto Accept Match",
            self.config.get("auto_accept", True),
            lambda val: self._save_config("auto_accept", val)
        )
        self.toggles_layout.addWidget(self.row_accept)
        
        self.row_priority = SettingsToggleRow(
            self, "ARAM Priority Sniper",
            self.config.get("priority_picker", {}).get("enabled", False),
            self._on_toggle_priority
        )
        self.toggles_layout.addWidget(self.row_priority)
        
        self.row_auto_join = SettingsToggleRow(
            self, "Friend Auto-Join",
            self.config.get("auto_join_enabled", True),
            lambda val: self._save_config("auto_join_enabled", val)
        )
        self.toggles_layout.addWidget(self.row_auto_join)
        
        self.row_auto_runes = SettingsToggleRow(
            self, "Auto Runes Equip",
            self.config.get("auto_runes_enabled", False),
            lambda val: self._save_config("auto_runes_enabled", val)
        )
        self.toggles_layout.addWidget(self.row_auto_runes)
        
        self.row_auto_honor = SettingsToggleRow(
            self, "Auto Honor Teammate",
            self.config.get("auto_honor_enabled", False),
            lambda val: self._save_config("auto_honor_enabled", val)
        )
        self.toggles_layout.addWidget(self.row_auto_honor)
        
        self.row_skip_stats = SettingsToggleRow(
            self, "Skip Stats Screen",
            self.config.get("skip_stats_enabled", True),
            lambda val: self._save_config("skip_stats_enabled", val)
        )
        self.toggles_layout.addWidget(self.row_skip_stats)
        
        self.row_auto_add_played = SettingsToggleRow(
            self, "Auto-Add Played Champs",
            self.config.get("aram_auto_add_played", False),
            lambda val: self._save_config("aram_auto_add_played", val)
        )
        self.toggles_layout.addWidget(self.row_auto_add_played)
        
        self.row_auto_ban = SettingsToggleRow(
            self, "Auto-Ban Champions",
            self.config.get("auto_ban_enabled", False),
            lambda val: self._save_config("auto_ban_enabled", val)
        )
        self.toggles_layout.addWidget(self.row_auto_ban)
        
        self.scroll.add_widget(self.toggles_card)
        
        # Subscribe to EventBus
        EventBus.on("automation_queue_state", self._on_queue_state)
        EventBus.on("queue_timer_tick", self._on_queue_timer_tick)
        EventBus.on("league_connected", self._on_connected)
        EventBus.on("league_disconnected", self._on_disconnected)
        EventBus.on("setting_changed", self._on_setting_changed)
        
        # Setup initial status
        self.update_client_states()

    def _save_config(self, key, val):
        self.config.set(key, val)
        from ui.qt.widgets.toast import ToastManager
        label = key.replace("_", " ").title()
        status = "Enabled" if val else "Disabled"
        ToastManager.get_instance().show(f"{label} {status}", icon="⚙️", theme="success" if val else "error")

    def _on_toggle_priority(self, val):
        cfg = self.config.get("priority_picker", {})
        cfg["enabled"] = val
        self.config.set("priority_picker", cfg)
        from ui.qt.widgets.toast import ToastManager
        status = "Enabled" if val else "Disabled"
        ToastManager.get_instance().show(f"ARAM Picker {status}", icon="⚔️", theme="success" if val else "error")

    def _on_setting_changed(self, key, val):
        # Safely synchronize toggle rows if settings are changed externally
        QMetaObject.invokeMethod(self, "_sync_setting_ui", Qt.QueuedConnection, Q_ARG(str, key), Q_ARG(bool, bool(val)))

    @Slot(str, bool)
    def _sync_setting_ui(self, key, val):
        if key == "auto_accept":
            self.row_accept.toggle.setChecked(val)
        elif key == "priority_picker":
            # val might be dict or bool
            enabled = self.config.get("priority_picker", {}).get("enabled", False)
            self.row_priority.toggle.setChecked(enabled)
        elif key == "auto_join_enabled":
            self.row_auto_join.toggle.setChecked(val)
        elif key == "auto_runes_enabled":
            self.row_auto_runes.toggle.setChecked(val)
        elif key == "auto_honor_enabled":
            self.row_auto_honor.toggle.setChecked(val)
        elif key == "skip_stats_enabled":
            self.row_skip_stats.toggle.setChecked(val)
        elif key == "aram_auto_add_played":
            self.row_auto_add_played.toggle.setChecked(val)
        elif key == "auto_ban_enabled":
            self.row_auto_ban.toggle.setChecked(val)

    def update_client_states(self):
        is_conn = self.league_service.is_connected
        mode = self.config.get("aram_mode", "ARAM")
        self.lbl_game_mode.setText(f"{mode.upper()} MODE")
        
        # Show/Hide Launch Client Button based on Riot Client presence
        # We can dynamically retrieve Riot Client running status from accounts manager if available
        # But a simpler heuristic is: if not connected, show Launch Client.
        self.btn_launch_client.setVisible(not is_conn)
        self.btn_find_match.setEnabled(is_conn)
        self.btn_requeue.setEnabled(is_conn)
        self.btn_dodge.setEnabled(is_conn)
        
        if not is_conn:
            self.lbl_phase.setText("Phase: Disconnected from LCU")
            self.btn_find_match.setText("▶  Find Match")

    def _on_connected(self):
        QMetaObject.invokeMethod(self, "update_client_states", Qt.QueuedConnection)

    def _on_disconnected(self):
        QMetaObject.invokeMethod(self, "update_client_states", Qt.QueuedConnection)

    # ── Matchmaking Control Actions ──
    def _on_find_match_clicked(self):
        if not self.league_service.is_connected:
            return
        run_in_background(self.queue_service.find_match)

    def _on_requeue_clicked(self):
        if not self.league_service.is_connected:
            return
        def requeue_task():
            self.queue_service.cancel_matchmaking()
            import time
            time.sleep(0.5)
            self.queue_service.find_match()
        run_in_background(requeue_task)

    def _on_dodge_clicked(self):
        if not self.league_service.is_connected:
            return
        run_in_background(self.queue_service.force_dodge)

    def _on_play_again_clicked(self):
        if not self.league_service.is_connected:
            return
        run_in_background(self.queue_service.play_again)

    def _on_launch_client_clicked(self):
        # Trigger client launch command on main coordinator window
        win = self.window()
        if hasattr(win, "ctk_app") and win.ctk_app:
            if hasattr(win.ctk_app, "_hotkey_launch_client"):
                run_in_background(win.ctk_app._hotkey_launch_client)

    # ── Queue State Listeners ──
    def _on_queue_state(self, phase, state):
        QMetaObject.invokeMethod(self, "update_queue_ui", Qt.QueuedConnection, Q_ARG(str, phase))

    @Slot(str)
    def update_queue_ui(self, phase):
        if not phase:
            phase = "None"
        self.lbl_phase.setText(f"Phase: {phase}")
        
        # Toggle buttons styling/visibility depending on phase
        is_searching = (phase == "Matchmaking")
        self.btn_find_match.setText("⏹  Cancel Search" if is_searching else "▶  Find Match")
        
        # Play again only visible if game is finished/idle
        self.btn_play_again.setVisible(phase in ["None", "EndOfGame"])
        
        if not is_searching:
            self.progress_bar.setValue(0)
            self.lbl_timer.setText("0:00 / 0:00")

    def _on_queue_timer_tick(self, elapsed, estimate):
        QMetaObject.invokeMethod(self, "update_timer_ui", Qt.QueuedConnection, Q_ARG(int, elapsed), Q_ARG(int, estimate))

    @Slot(int, int)
    def update_timer_ui(self, elapsed, estimate):
        if estimate <= 0:
            estimate = 120
            
        # Compute progress percentage
        pct = min(100, int((elapsed / estimate) * 100))
        self.progress_bar.setValue(pct)
        
        # Format display text
        elapsed_m, elapsed_s = divmod(elapsed, 60)
        estimate_m, estimate_s = divmod(estimate, 60)
        self.lbl_timer.setText(f"{elapsed_m}:{elapsed_s:02d} / {estimate_m}:{estimate_s:02d}")
