"""
PySide6 Dashboard Page Component
Displays modular diagnostic cards, engine health, and active status feeds.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, QMetaObject, Slot
from ui.qt.widgets import ScrollableList, make_card
from services.settings_service import get_settings_service
from services.league_service import get_league_service
from core.events import EventBus

class DashboardPage(QWidget):
    """The main Dashboard Page displaying diagnostic cards and system overview."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        self.league_service = get_league_service()
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(10)
        
        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)
        
        # ── 1. ENGINE HEALTH CARD ──
        self.health_card = make_card(title="AUTOMATION ENGINE DIAGNOSTICS")
        
        self.lbl_status = QLabel("System Ready", self)
        self.lbl_status.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 13px;")
        self.health_card.add_widget(self.lbl_status)
        
        self.row_metrics = QWidget(self)
        self.row_metrics_layout = QHBoxLayout(self.row_metrics)
        self.row_metrics_layout.setContentsMargins(0, 4, 0, 4)
        
        self.lbl_lcu_state = QLabel("LCU: Connected", self)
        self.lbl_lcu_state.setStyleSheet("color: #C8AA6E; font-size: 11px;")
        self.row_metrics_layout.addWidget(self.lbl_lcu_state)
        
        self.row_metrics_layout.addStretch()
        
        self.lbl_queue_mode = QLabel("Queue: ARAM 5v5", self)
        self.lbl_queue_mode.setStyleSheet("color: #A8B8CC; font-size: 11px; font-weight: bold;")
        self.row_metrics_layout.addWidget(self.lbl_queue_mode)
        
        self.health_card.add_widget(self.row_metrics)
        self.scroll.add_widget(self.health_card)
        
        # ── 2. PERFORMANCE & STATS CARD ──
        self.stats_card = make_card(title="PERFORMANCE METRICS")
        
        self.lbl_stats_title = QLabel("Matches Automated: 0", self)
        self.lbl_stats_title.setStyleSheet("color: #F8F6F0; font-weight: bold; font-size: 12px;")
        self.stats_card.add_widget(self.lbl_stats_title)
        
        self.progress_winrate = QProgressBar(self)
        self.progress_winrate.setFixedHeight(6)
        self.progress_winrate.setRange(0, 100)
        self.progress_winrate.setValue(68)
        self.progress_winrate.setTextVisible(False)
        self.progress_winrate.setStyleSheet("""
            QProgressBar {
                background-color: #0A1424;
                border: 1px solid #1A2B3E;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #2ECC71;
                border-radius: 2px;
            }
        """)
        self.stats_card.add_widget(self.progress_winrate)
        
        self.lbl_winrate_caption = QLabel("Target Winrate Confidence: 68%", self)
        self.lbl_winrate_caption.setStyleSheet("color: #A8B8CC; font-size: 10px; font-weight: bold;")
        self.stats_card.add_widget(self.lbl_winrate_caption)
        
        self.scroll.add_widget(self.stats_card)
        
        # ── 3. RECENT ACTIVITY LOG CARD ──
        self.log_card = make_card(title="RECENT SYSTEM EVENTS")
        
        self.lbl_log1 = QLabel("[SYSTEM] LeagueLoop initialized cleanly.", self)
        self.lbl_log1.setStyleSheet("color: #F8F6F0; font-size: 11px;")
        self.log_card.add_widget(self.lbl_log1)
        
        self.lbl_log2 = QLabel("[NETWORK] Remote Link API running on port 8337.", self)
        self.lbl_log2.setStyleSheet("color: #A8B8CC; font-size: 11px;")
        self.btn_open_logs = make_button(self, text="📁 OPEN LOGS FOLDER", style="secondary")
        self.btn_open_logs.clicked.connect(self._on_open_logs_clicked)
        self.log_card.add_widget(self.btn_open_logs)
        
        self.scroll.add_widget(self.log_card)
        
        EventBus.on("league_connected", self._on_connected)
        EventBus.on("league_disconnected", self._on_disconnected)

    def _on_connected(self):
        QMetaObject.invokeMethod(self.lbl_lcu_state, "setText", Qt.QueuedConnection, Slot(str)("LCU: Connected"))

    def _on_disconnected(self):
        QMetaObject.invokeMethod(self.lbl_lcu_state, "setText", Qt.QueuedConnection, Slot(str)("LCU: Disconnected"))

    def _on_open_logs_clicked(self):
        import os
        from utils.logger import Logger
        log_dir = Logger.get_log_dir()
        if os.path.exists(log_dir):
            os.startfile(log_dir)
            from ui.qt.widgets.toast import ToastManager
            ToastManager.get_instance().show("Opened log directory", icon="📁", theme="info")
