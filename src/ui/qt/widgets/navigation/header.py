from PySide6.QtCore import Qt, QPoint, QVariantAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton
)

from services.window_service import get_window_service
from ui.qt.widgets.icons import RiotIconWidget
from ui.qt.viewmodels.header_viewmodel import HeaderViewModel

# ─────────────────────────────────────────────
# TAB BUTTON (Version One horizontal tab style)
# ─────────────────────────────────────────────

class TabButton(QPushButton):
    """Minimal top-tab button matching Version One's horizontal nav."""
    def __init__(self, label, page_index, parent=None):
        super().__init__(label, parent)
        self.page_index = page_index
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        self.setFocusPolicy(Qt.StrongFocus)
        self.is_active = False
        
        self._color = QColor("#6C757D")
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(120)
        self.anim.valueChanged.connect(self._on_anim)
        
        self._update_style()

    def set_active(self, active):
        self.is_active = active
        self._update_style()

    def _on_anim(self, color):
        self._color = color
        self._update_style()

    def _update_style(self):
        c = self._color.name()
        if self.is_active:
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-bottom: 2px solid #C8AA6E;
                    color: #C8AA6E;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 0 8px;
                    font-family: "Inter", sans-serif;
                }
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-bottom: 2px solid transparent;
                    color: {c};
                    font-weight: 500;
                    font-size: 12px;
                    padding: 0 8px;
                    font-family: "Inter", sans-serif;
                }}
            """)

    def enterEvent(self, event):
        super().enterEvent(event)
        if not self.is_active:
            self.anim.stop()
            self.anim.setStartValue(self._color)
            self.anim.setEndValue(QColor("#F0E6D2"))
            self.anim.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if not self.is_active:
            self.anim.stop()
            self.anim.setStartValue(self._color)
            self.anim.setEndValue(QColor("#6C757D"))
            self.anim.start()


# ─────────────────────────────────────────────
# HEADER BAR (Version One style)
# ─────────────────────────────────────────────

class HeaderBar(QWidget):
    """Custom premium title bar with integrated top-tab navigation."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(40)
        self.setObjectName("headerBarFrame")
        
        self.setStyleSheet("""
            QWidget#headerBarFrame {
                background-color: #080E18;
                border-bottom: 1px solid #142236;
            }
            QLabel {
                font-family: "Inter", sans-serif;
                background: transparent;
            }
            QPushButton {
                border: none;
                background-color: transparent;
                padding: 0px;
                margin: 0px;
                border-radius: 4px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 6, 0)
        layout.setSpacing(0)
        
        # 1. App Title
        self.logo_lbl = QLabel("League Loop", self)
        self.logo_lbl.setStyleSheet("font-weight: bold; color: #C8AA6E; font-size: 12px; margin-right: 16px;")
        layout.addWidget(self.logo_lbl)
        
        # 2. Tab Navigation (Version One: Play | Automation | Champions | Settings)
        self.tab_container = QWidget(self)
        self.tab_layout = QHBoxLayout(self.tab_container)
        self.tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_layout.setSpacing(4)
        
        self.tabs = []
        tab_defs = [
            ("Play", 0),
            ("Automations", 1),
            ("Config", 2),
            ("Misc", 3),
        ]
        for label, idx in tab_defs:
            tab = TabButton(label, idx, self.tab_container)
            tab.clicked.connect(lambda checked=False, i=idx: self.parent.switch_page(i))
            self.tab_layout.addWidget(tab)
            self.tabs.append(tab)
        
        layout.addWidget(self.tab_container)
        layout.addStretch()
        
        # 3. Queue Timer Badge
        self.timer_lbl = QLabel("⏳ 0:00", self)
        self.timer_lbl.setStyleSheet("color: #C8AA6E; font-size: 11px; font-weight: bold; background: #0E1A2E; padding: 2px 8px; border-radius: 4px; border: 1px solid #1E2D42;")
        self.timer_lbl.setVisible(False)
        layout.addWidget(self.timer_lbl)
        
        # 4. Profile Badge
        self.profile_lbl = QLabel("", self)
        self.profile_lbl.setStyleSheet("color: #C8AA6E; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.profile_lbl)
        
        # 5. Window Controls (Dock, Min, Close)
        self.btn_dock = QPushButton(self)
        self.btn_dock.setFixedSize(26, 26)
        self.btn_dock.setCursor(Qt.PointingHandCursor)
        btn_dock_layout = QHBoxLayout(self.btn_dock)
        btn_dock_layout.setContentsMargins(4, 4, 4, 4)
        self.dock_icon_widget = RiotIconWidget("dock", size=16, color="#C8AA6E", parent=self.btn_dock)
        btn_dock_layout.addWidget(self.dock_icon_widget)
        self.btn_dock.clicked.connect(self._toggle_dock)
        layout.addWidget(self.btn_dock)
        
        self.btn_min = QPushButton(self)
        self.btn_min.setFixedSize(26, 26)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        btn_min_layout = QHBoxLayout(self.btn_min)
        btn_min_layout.setContentsMargins(4, 4, 4, 4)
        btn_min_layout.addWidget(RiotIconWidget("minimize", size=16, color="#C8AA6E", parent=self.btn_min))
        self.btn_min.clicked.connect(self.parent.showMinimized)
        layout.addWidget(self.btn_min)
        
        self.btn_close = QPushButton(self)
        self.btn_close.setFixedSize(26, 26)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        btn_close_layout = QHBoxLayout(self.btn_close)
        btn_close_layout.setContentsMargins(4, 4, 4, 4)
        btn_close_layout.addWidget(RiotIconWidget("close", size=16, color="#E74C3C", parent=self.btn_close))
        self.btn_close.clicked.connect(self.parent.close)
        layout.addWidget(self.btn_close)
        
        self._drag_position = None
        self._window_service = get_window_service()
        self._update_dock_icon()
        
        # Initialize and bind ViewModel
        self.viewmodel = HeaderViewModel(self)
        self.viewmodel.timer_text_changed.connect(self.timer_lbl.setText)
        self.viewmodel.timer_visibility_changed.connect(self.timer_lbl.setVisible)
        self.viewmodel.profile_text_changed.connect(self.profile_lbl.setText)

    def set_active_tab(self, index):
        for tab in self.tabs:
            tab.set_active(tab.page_index == index)
        
    def _toggle_dock(self):
        is_docked = self._window_service.is_docked
        self._window_service.set_docked_mode(not is_docked)
        self._update_dock_icon()
        
    def _update_dock_icon(self):
        is_docked = self._window_service.is_docked
        self.btn_dock.setToolTip("Docked Mode (Snaps to League)" if is_docked else "Undocked Mode (Free Window)")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_position and not self._window_service.is_docked:
            self.parent.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

