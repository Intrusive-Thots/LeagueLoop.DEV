"""
PySide6 Navigation Sidebar Widget for LeagueLoop.
Provides collapsible navigation tabs with Hextech visual styling and signals.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.qt.theme import (
    COLOR_BACKGROUND_DARK,
    COLOR_BACKGROUND_HOVER,
    COLOR_BACKGROUND_PANEL,
    COLOR_BORDER,
    COLOR_BORDER_GOLD,
    COLOR_GOLD_LIGHT,
    COLOR_GOLD_PRIMARY,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class QtSidebarButton(QPushButton):
    """Custom navigation sidebar item with active accent border."""

    def __init__(self, key: str, label: str, icon_text: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.key = key
        self.label_text = label
        self.icon_text = icon_text
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setText(f"  {icon_text}  {label}" if icon_text else f"  {label}")
        self._update_style()

    def _update_style(self) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding-left: 12px;
                font-size: 13px;
                font-weight: 500;
                color: {COLOR_TEXT_SECONDARY};
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
            }}
            QPushButton:hover {{
                color: {COLOR_TEXT_PRIMARY};
                background-color: {COLOR_BACKGROUND_HOVER};
                border-left: 3px solid {COLOR_GOLD_PRIMARY};
            }}
            QPushButton:checked {{
                color: {COLOR_GOLD_LIGHT};
                background-color: {COLOR_BACKGROUND_PANEL};
                border-left: 3px solid {COLOR_GOLD_PRIMARY};
                font-weight: bold;
            }}
        """)


class QtNavigationSidebar(QFrame):
    """Left navigation sidebar containing application tabs."""

    tab_selected = Signal(str)

    DEFAULT_TABS = [
        ("play", "Play", "⚔️"),
        ("aram", "ARAM", "❄️"),
        ("priority", "Priority", "⭐"),
        ("loot", "Loot Opener", "🎁"),
        ("accounts", "Accounts", "👤"),
        ("diagnostics", "Diagnostics", "📊"),
        ("settings", "Settings", "⚙️"),
    ]

    def __init__(self, tabs: Optional[List[tuple]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(200)
        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {COLOR_BACKGROUND_DARK};
                border-right: 1px solid {COLOR_BORDER};
            }}
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 16, 0, 16)
        self.layout.setSpacing(4)

        # Header / Brand Label
        self.brand_label = QLabel("  LEAGUELOOP", self)
        self.brand_label.setStyleSheet(f"""
            color: {COLOR_GOLD_PRIMARY};
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 1.5px;
            padding-left: 12px;
            margin-bottom: 12px;
        """)
        self.layout.addWidget(self.brand_label)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons: Dict[str, QtSidebarButton] = {}

        tab_list = tabs or self.DEFAULT_TABS
        for key, name, icon in tab_list:
            btn = QtSidebarButton(key, name, icon, self)
            btn.clicked.connect(lambda checked, k=key: self._on_btn_clicked(k))
            self.button_group.addButton(btn)
            self.layout.addWidget(btn)
            self.buttons[key] = btn

        self.layout.addStretch()

        # Status / Footer
        self.status_label = QLabel("  v2.0.0-DEV", self)
        self.status_label.setStyleSheet(f"""
            color: {COLOR_TEXT_MUTED};
            font-size: 11px;
            padding-left: 12px;
        """)
        self.layout.addWidget(self.status_label)

        # Select first tab by default
        if tab_list:
            self.select_tab(tab_list[0][0])

    def _on_btn_clicked(self, key: str) -> None:
        self.tab_selected.emit(key)

    def select_tab(self, key: str) -> None:
        """Programmatically activate a tab by key."""
        btn = self.buttons.get(key)
        if btn:
            btn.setChecked(True)
            self.tab_selected.emit(key)
