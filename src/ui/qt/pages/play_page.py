"""
PySide6 Play Page Component
Version One design: clean status rows, single CTA, inline friends, minimal automation toggles.
Refactored to MVVM architecture.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
)
from PySide6.QtCore import Qt, Slot

from ui.qt.widgets.components import (
    SectionHeader, PrimaryButton
)
from ui.qt.widgets.scrollable_list import ScrollableList
from ui.qt.viewmodels.play_viewmodel import PlayViewModel
from ui.qt.widgets.toast import ToastManager

class PlayPage(QWidget):
    """Version One Play dashboard using PlayViewModel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewmodel = PlayViewModel(self)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)

        # ── 1. STATUS ROW (V1: "ARAM Machine ● Active / Queue ● Connected") ──
        self.status_row = QWidget(self)
        status_layout = QHBoxLayout(self.status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(16)

        # Mode selector
        self.combo_mode = QComboBox(self.status_row)
        self.combo_mode.setFixedHeight(28)
        self.combo_mode.setStyleSheet("""
            QComboBox {
                background-color: transparent;
                border: none;
                color: #F0E6D2;
                font-weight: bold;
                font-size: 12px;
                padding-left: 0px;
            }
            QComboBox:hover { color: #C8AA6E; }
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
        current_mode = self.viewmodel.config.get("aram_mode", "ARAM")
        idx = self.combo_mode.findText(current_mode)
        if idx >= 0:
            self.combo_mode.setCurrentIndex(idx)
        self.combo_mode.currentTextChanged.connect(self.viewmodel.set_game_mode)
        status_layout.addWidget(self.combo_mode)

        # Connection dot
        self.lbl_connection = QLabel("● Active", self.status_row)
        self.lbl_connection.setStyleSheet("color: #2ECC71; font-size: 11px; font-weight: bold;")
        status_layout.addWidget(self.lbl_connection)

        status_layout.addStretch()

        # Queue status dot  
        self.lbl_queue_status = QLabel("● Ready", self.status_row)
        self.lbl_queue_status.setStyleSheet("color: #2ECC71; font-size: 11px; font-weight: bold;")
        status_layout.addWidget(self.lbl_queue_status)

        self.scroll.add_widget(self.status_row)

        # ── 2. PRIMARY CTA (V1: single "Find Match" gold button) ──
        self.btn_find_match = PrimaryButton("Find Match", parent=self)
        self.btn_find_match.setFixedHeight(36)
        self.btn_find_match.clicked.connect(self.viewmodel.find_match)
        self.scroll.add_widget(self.btn_find_match)

        # Automations have been moved to AutomationsPage

        # ── 4. FRIENDS LIST (V1: inline friends below toggles) ──
        self.scroll.add_widget(SectionHeader("Friends"))

        self.friends_container = QWidget(self)
        self.friends_layout = QVBoxLayout(self.friends_container)
        self.friends_layout.setContentsMargins(0, 0, 0, 0)
        self.friends_layout.setSpacing(4)

        self.lbl_friends_empty = QLabel("No friends online.", self.friends_container)
        self.lbl_friends_empty.setStyleSheet("color: #6C757D; font-size: 11px; padding: 8px 0;")
        self.friends_layout.addWidget(self.lbl_friends_empty)

        self.scroll.add_widget(self.friends_container)

        # ── BIND TO VIEWMODEL ──
        self.viewmodel.connection_status_changed.connect(self._on_connection_changed)
        self.viewmodel.queue_status_changed.connect(self._on_queue_status_changed)
        self.viewmodel.friends_list_updated.connect(self._on_friends_list_updated)
        self.viewmodel.action_completed.connect(self._on_action_completed)


    @Slot(bool)
    def _on_connection_changed(self, active: bool):
        if active:
            self.lbl_connection.setText("● Active")
            self.lbl_connection.setStyleSheet("color: #2ECC71; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_connection.setText("● Disconnected")
            self.lbl_connection.setStyleSheet("color: #E74C3C; font-size: 11px; font-weight: bold;")

    @Slot(str, str)
    def _on_queue_status_changed(self, phase: str, state_text: str):
        if phase == "Matchmaking":
            self.lbl_queue_status.setText("● In Queue")
            self.lbl_queue_status.setStyleSheet("color: #C8AA6E; font-size: 11px; font-weight: bold;")
            self.btn_find_match.setText("Cancel Match")
        elif phase in ["ChampSelect", "InProgress"]:
            self.lbl_queue_status.setText(f"● {phase}")
            self.lbl_queue_status.setStyleSheet("color: #2ECC71; font-size: 11px; font-weight: bold;")
            self.btn_find_match.setText("In Game")
        else:
            self.lbl_queue_status.setText("● Ready")
            self.lbl_queue_status.setStyleSheet("color: #2ECC71; font-size: 11px; font-weight: bold;")
            self.btn_find_match.setText("Find Match")

    @Slot(list)
    def _on_friends_list_updated(self, friend_data: list):
        # Clear existing items
        while self.friends_layout.count():
            item = self.friends_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not friend_data:
            lbl = QLabel("No friends online.", self.friends_container)
            lbl.setStyleSheet("color: #6C757D; font-size: 11px; padding: 8px 0;")
            self.friends_layout.addWidget(lbl)
            return

        for f in friend_data:
            row = QWidget(self.friends_container)
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(0, 2, 0, 2)
            
            dot_color = "#2ECC71" if f["status"] == "online" else "#E67E22"
            lbl_name = QLabel(f"●  {f['name']}", row)
            lbl_name.setStyleSheet(f"color: {dot_color}; font-size: 11px;")
            r_layout.addWidget(lbl_name, stretch=1)
            
            self.friends_layout.addWidget(row)

    @Slot(bool, str)
    def _on_action_completed(self, success: bool, message: str):
        toast = ToastManager.get_instance()
        if toast:
            if success:
                toast.show(message, icon="🎮", theme="info")
            else:
                toast.show(message, icon="⚠️", theme="error")
