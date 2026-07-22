"""
PySide6 Play Page Component
Handles play controls, matchmaking queue states, and quick automation toggles.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, QMetaObject, Slot, Q_ARG
from PySide6.QtGui import QColor

from ui.qt.widgets import ScrollableList, make_card, make_button
from ui.qt.theme import get_theme_color
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
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(10)
        
        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)
        
        # ── 1. SESSION HERO CARD ──
        self.header_card = make_card(title="MATCHMAKING DASHBOARD")
        
        # Game Mode Selector Row
        self.mode_row = QWidget(self)
        self.mode_layout = QHBoxLayout(self.mode_row)
        self.mode_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_layout.setSpacing(8)

        self.lbl_mode_title = QLabel("Game Mode:", self.mode_row)
        self.lbl_mode_title.setStyleSheet("font-weight: bold; color: #F0E6D2; font-size: 13px;")
        self.mode_layout.addWidget(self.lbl_mode_title)

        self.combo_mode = QComboBox(self.mode_row)
        self.combo_mode.setFixedHeight(28)
        self.combo_mode.setStyleSheet("""
            QComboBox {
                background-color: #0E1826;
                border: 1px solid #C8AA6E;
                border-radius: 4px;
                color: #F0E6D2;
                font-weight: bold;
                font-size: 11px;
                padding-left: 8px;
                padding-right: 20px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #1E2D42;
            }
            QComboBox QAbstractItemView {
                background-color: #0E1826;
                color: #F0E6D2;
                selection-background-color: #1E2D42;
                border: 1px solid #C8AA6E;
            }
        """)

        supported_modes = [
            "ARAM", "ARAM Mayhem", "Ranked Solo/Duo", "Ranked Flex", "Draft Pick", "Quickplay",
            "Arena", "TFT Normal", "TFT Ranked", "TFT Hyper Roll", "TFT Double Up", "Co-op vs. AI"
        ]
        self.combo_mode.addItems(supported_modes)
        
        current_mode = self.config.get("aram_mode", "ARAM")
        idx = self.combo_mode.findText(current_mode)
        if idx >= 0:
            self.combo_mode.setCurrentIndex(idx)

        self.combo_mode.currentTextChanged.connect(self._on_game_mode_changed)
        self.mode_layout.addWidget(self.combo_mode, stretch=1)

        self.header_card.add_widget(self.mode_row)
        
        self.lbl_phase = QLabel("Phase: Disconnected", self)
        self.lbl_phase.setStyleSheet("color: #A8B8CC; font-size: 11px; font-weight: bold;")
        self.header_card.add_widget(self.lbl_phase)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0A1424;
                border: 1px solid #1A2B3E;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #C8AA6E;
                border-radius: 2px;
            }
        """)
        self.header_card.add_widget(self.progress_bar)
        
        self.lbl_timer = QLabel("0:00 / 0:00", self)
        self.lbl_timer.setStyleSheet("color: #C8AA6E; font-size: 11px; font-weight: bold;")
        self.header_card.add_widget(self.lbl_timer)
        
        self.scroll.add_widget(self.header_card)
        
        # ── 2. MATCHMAKING ACTIONS CARD ──
        self.actions_card = make_card(title="QUEUE CONTROLS")
        
        self.btn_find_match = make_button(self, text="START MATCHMAKING", style="primary")
        self.btn_find_match.setFixedHeight(36)
        self.btn_find_match.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0E6D2, stop:0.5 #C8AA6E, stop:1 #A88A4E);
                color: #080E18;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #FFF2D6;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:0.5 #DCC186, stop:1 #C8AA6E);
                border-color: #FFFFFF;
                color: #000000;
            }
            QPushButton:pressed {
                background: #8A6F3B;
                border-color: #A88A4E;
            }
            QPushButton:disabled {
                color: #8C99A8;
                background-color: #121E2E;
                border: 1px solid #1E2D42;
            }
        """)
        self.btn_find_match.clicked.connect(self._on_find_match_clicked)
        self.actions_card.add_widget(self.btn_find_match)
        
        self.row_quick = QWidget(self.actions_card)
        self.row_quick_layout = QHBoxLayout(self.row_quick)
        self.row_quick_layout.setContentsMargins(0, 0, 0, 0)
        self.row_quick_layout.setSpacing(8)
        
        self.btn_requeue = make_button(self.row_quick, text="Requeue", style="secondary")
        self.btn_requeue.clicked.connect(self._on_requeue_clicked)
        self.row_quick_layout.addWidget(self.btn_requeue)
        
        self.btn_dodge = make_button(self.row_quick, text="Dodge Lobby", style="danger")
        self.btn_dodge.clicked.connect(self._on_dodge_clicked)
        self.row_quick_layout.addWidget(self.btn_dodge)
        
        self.actions_card.add_widget(self.row_quick)
        
        self.btn_launch_client = make_button(self.actions_card, text="🚀 LAUNCH LEAGUE CLIENT", style="secondary")
        self.btn_launch_client.clicked.connect(self._on_launch_client_clicked)
        self.actions_card.add_widget(self.btn_launch_client)
        
        self.scroll.add_widget(self.actions_card)
        
        # ── 3. AUTOMATION QUICK TOGGLES CARD ──
        self.toggles_card = make_card(title="AUTOMATION ENGINES")
        
        self.row_autolaunch = SettingsToggleRow(
            self,
            label_text="Auto-Launch Client on Disconnect",
            initial_state=self.config.get("auto_launch_client", False),
            on_toggle=lambda v: self.config.set("auto_launch_client", v)
        )
        self.toggles_card.add_widget(self.row_autolaunch)
        
        self.row_accept = SettingsToggleRow(
            self,
            label_text="Auto-Accept Ready Check",
            initial_state=self.config.get("auto_accept", True),
            on_toggle=lambda v: self.config.set("auto_accept", v)
        )
        self.toggles_card.add_widget(self.row_accept)
        
        self.row_pick = SettingsToggleRow(
            self,
            label_text="Auto-Pick Priority Champion",
            initial_state=self.config.get("auto_pick", True),
            on_toggle=lambda v: self.config.set("auto_pick", v)
        )
        self.toggles_card.add_widget(self.row_pick)
        
        self.row_runes = SettingsToggleRow(
            self,
            label_text="Auto-Import Optimal Runes",
            initial_state=self.config.get("auto_runes", True),
            on_toggle=lambda v: self.config.set("auto_runes", v)
        )
        self.toggles_card.add_widget(self.row_runes)
        
        self.row_honor = SettingsToggleRow(
            self,
            label_text="Auto-Honor Teammates",
            initial_state=self.config.get("auto_honor", True),
            on_toggle=lambda v: self.config.set("auto_honor", v)
        )
        self.toggles_card.add_widget(self.row_honor)
        
        self.scroll.add_widget(self.toggles_card)
        
        EventBus.on("automation_queue_state", self._on_queue_state_changed)
        EventBus.on("queue_timer_tick", self._on_timer_tick)
        EventBus.on("setting_changed", self._on_setting_changed)

    def _on_game_mode_changed(self, new_mode):
        self.config.set("aram_mode", new_mode)
        from ui.qt.widgets.toast import ToastManager
        toast = ToastManager.get_instance()
        if toast:
            toast.show(f"Game Mode set to {new_mode}", icon="🎮", theme="info")

    def _on_find_match_clicked(self):
        def task():
            success = self.queue_service.find_match()
            from ui.qt.widgets.toast import ToastManager
            if success:
                ToastManager.get_instance().show("Searching for Match...", icon="🎮", theme="info")
            else:
                ToastManager.get_instance().show("Queue Search Failed", icon="⚠️", theme="error")
        run_in_background(task)

    def _on_requeue_clicked(self):
        def task():
            success, msg = self.queue_service.requeue()
            from ui.qt.widgets.toast import ToastManager
            if success:
                ToastManager.get_instance().show("Requeued Match", icon="🔄", theme="success")
            else:
                ToastManager.get_instance().show(f"Requeue Failed: {msg}", icon="⚠️", theme="error")
        run_in_background(task)

    def _on_dodge_clicked(self):
        def task():
            success, msg = self.queue_service.force_dodge()
            from ui.qt.widgets.toast import ToastManager
            if success:
                ToastManager.get_instance().show("Dodged Lobby", icon="🚪", theme="warning")
            else:
                ToastManager.get_instance().show(f"Dodge Failed: {msg}", icon="⚠️", theme="error")
        run_in_background(task)

    def _on_launch_client_clicked(self):
        def task():
            from utils.client_detector import launch_league_client
            from ui.qt.widgets.toast import ToastManager
            success, msg = launch_league_client()
            if success:
                ToastManager.get_instance().show(msg, icon="🚀", theme="info")
            else:
                ToastManager.get_instance().show(f"Launch Failed: {msg}", icon="⚠️", theme="error")
        run_in_background(task)

    def _on_queue_state_changed(self, phase, state):
        QMetaObject.invokeMethod(self, "_update_queue_ui_async", Qt.QueuedConnection, Q_ARG(str, phase))

    @Slot(str)
    def _update_queue_ui_async(self, phase):
        self.lbl_phase.setText(f"Phase: {phase}")
        if phase == "Matchmaking":
            self.lbl_phase.setStyleSheet("color: #2ECC71; font-weight: bold;")
            self.btn_find_match.setText("CANCEL MATCHMAKING")
        elif phase in ["ChampSelect", "InProgress"]:
            self.lbl_phase.setStyleSheet("color: #C8AA6E; font-weight: bold;")
            self.btn_find_match.setText("IN GAME")
        else:
            self.lbl_phase.setStyleSheet("color: #A8B8CC; font-weight: bold;")
            self.btn_find_match.setText("START MATCHMAKING")

    def _on_timer_tick(self, current, estimated):
        QMetaObject.invokeMethod(self, "_update_timer_async", Qt.QueuedConnection, Q_ARG(float, current), Q_ARG(float, estimated))

    @Slot(float, float)
    def _update_timer_async(self, current, estimated):
        cur_min, cur_sec = divmod(int(current), 60)
        est_min, est_sec = divmod(int(estimated), 60)
        self.lbl_timer.setText(f"{cur_min}:{cur_sec:02d} / {est_min}:{est_sec:02d}")
        if estimated > 0:
            pct = min(100, int((current / estimated) * 100))
            self.progress_bar.setValue(pct)
        else:
            self.progress_bar.setValue(0)

    def _on_setting_changed(self, key, value):
        pass
