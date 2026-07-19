"""
PySide6 Coach Page Component
Handles draft assistance, pick/ban priority profiles, and live synergy metrics.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTabWidget, QScrollArea, QFrame, QPushButton
)
from PySide6.QtCore import Qt, QMetaObject, Slot
from ui.qt.widgets import ScrollableList, make_card, make_button
from ui.qt.theme import get_theme_color
from services.settings_service import get_settings_service
from services.draft_service import get_draft_service
from core.events import EventBus

class CoachPage(QWidget):
    """The PySide6 AI Coach Page supporting draft strategy planning and recommendations."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        self.draft_service = get_draft_service()
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(10)
        
        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)
        
        # ── 1. DRAFT PROFILES CARD ──
        self.profiles_card = make_card(title="DRAFT PRIORITY PLANNER")
        
        self.lbl_info = QLabel("Configure champion priority preferences by role.", self)
        self.lbl_info.setStyleSheet("color: #A0A5B5; font-size: 11px;")
        self.profiles_card.add_widget(self.lbl_info)
        
        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet("""
            QTabWidget::panel {
                border: 1px solid #1E2D42;
                background-color: #0A1424;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #080E18;
                color: #A0A5B5;
                padding: 6px 12px;
                border: 1px solid #1E2D42;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #0F1A2A;
                color: #C8AA6E;
                font-weight: bold;
            }
        """)
        
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        for r in roles:
            w = QWidget()
            l = QVBoxLayout(w)
            l.setContentsMargins(8, 8, 8, 8)
            lbl = QLabel(f"Priority list for role: {r}", w)
            lbl.setStyleSheet("color: #F0E6D2; font-size: 11px;")
            l.addWidget(lbl)
            self.tabs.addTab(w, r)
            
        self.profiles_card.add_widget(self.tabs)
        self.scroll.add_widget(self.profiles_card)
        
        # ── 2. LIVE DRAFT ADVISOR CARD ──
        self.advisor_card = make_card(title="LIVE DRAFT ADVISOR")
        
        self.lbl_status = QLabel("Draft Advisor is waiting for champion select to start...", self)
        self.lbl_status.setStyleSheet("color: #6C757D; font-size: 11px; font-style: italic;")
        self.lbl_status.setWordWrap(True)
        self.advisor_card.add_widget(self.lbl_status)
        
        self.scroll.add_widget(self.advisor_card)
