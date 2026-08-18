"""
QtNavigationSidebar — primary navigation (UI/UX Master Plan §4).

Top-level destinations only. The brand lockup and live status now live in
the persistent header (§2.4), so the sidebar stays a single-purpose
navigation column rather than repeating identity and state.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    FOCUS_RING,
    FOCUS_RING_WIDTH,
    GOLD_LIGHT,
    GOLD_PRIMARY,
    SURFACE_APP_BACKGROUND,
    SURFACE_PANEL,
    SURFACE_PANEL_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.spacing import (
    ICON_MD,
    NAV_ITEM_HEIGHT,
    SIDEBAR_WIDTH,
    SPACE_LG,
    SPACE_MD,
    SPACE_XS,
)
from ui.qt.theme.typography import FONT_FAMILY, WEIGHT_BOLD, WEIGHT_MEDIUM
from ui.qt.components.focus import install_focus_visible


class QtSidebarButton(QPushButton):
    """A navigation item with hover / checked / focus states (§63)."""

    def __init__(
        self,
        key: str,
        label: str,
        icon_text: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.key = key
        self.label_text = label
        self.icon_text = icon_text

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(NAV_ITEM_HEIGHT)
        self.setText(f"  {icon_text}   {label}" if icon_text else f"  {label}")
        self.setAccessibleName(label)
        self.setToolTip(label)
        install_focus_visible(self)
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding-left: {SPACE_MD}px;
                font-family: {FONT_FAMILY};
                font-size: 13px;
                font-weight: {WEIGHT_MEDIUM};
                color: {TEXT_SECONDARY};
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
                background-color: {SURFACE_PANEL_HOVER};
                border-left: 3px solid {GOLD_PRIMARY};
            }}
            QPushButton:checked {{
                color: {GOLD_LIGHT};
                background-color: {SURFACE_PANEL};
                border-left: 3px solid {GOLD_PRIMARY};
                font-weight: {WEIGHT_BOLD};
            }}
            QPushButton[keyboardFocus="true"] {{
                border: {FOCUS_RING_WIDTH}px solid {FOCUS_RING};
                outline: none;
            }}
        """)


class QtNavigationSidebar(QFrame):
    """Left navigation column."""

    tab_selected = Signal(str)

    DEFAULT_TABS = [
        ("play", "Play", "⚔"),
        ("champ_select", "Champ Select", "◆"),
        ("automation", "Automation", "⚙"),
        ("aram", "ARAM", "❄"),
        ("priority", "Priority", "★"),
        ("loot", "Loot", "🎁"),
        ("accounts", "Accounts", "👤"),
        ("diagnostics", "Diagnostics", "📊"),
        ("settings", "Settings", "⚙"),
    ]

    def __init__(
        self,
        tabs: Optional[List[tuple]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {SURFACE_APP_BACKGROUND};
                border-right: 1px solid {BORDER_DEFAULT};
            }}
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, SPACE_LG, 0, SPACE_LG)
        self._layout.setSpacing(SPACE_XS)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons: Dict[str, QtSidebarButton] = {}

        tab_list = tabs or self.DEFAULT_TABS
        for key, name, icon in tab_list:
            btn = QtSidebarButton(key, name, icon, self)
            btn.clicked.connect(lambda _checked, k=key: self._on_btn_clicked(k))
            self.button_group.addButton(btn)
            self._layout.addWidget(btn)
            self.buttons[key] = btn

        self._layout.addStretch(1)

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
