"""
PySide6 Play Tab Widget for LeagueLoop.
Provides matchmaking controls, automation toggles, and live client phase monitoring.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.qt.theme import (
    COLOR_BACKGROUND_CARD,
    COLOR_BACKGROUND_DARK,
    COLOR_BACKGROUND_HOVER,
    COLOR_BACKGROUND_PANEL,
    COLOR_BLUE_ACCENT,
    COLOR_BORDER,
    COLOR_BORDER_GOLD,
    COLOR_DANGER,
    COLOR_GOLD_LIGHT,
    COLOR_GOLD_PRIMARY,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class QtPlayTab(QWidget):
    """Primary lobby and matchmaking automation control surface."""

    def __init__(self, container=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.container = container
        self.config = container.config if container else None
        self.lcu = container.lcu if container else None
        self.automation = container.automation if container else None

        self._setup_ui()
        self._load_config_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header Title
        header = QLabel("Lobby & Automation", self)
        header.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {COLOR_GOLD_PRIMARY};
        """)
        layout.addWidget(header)

        # Status Card
        self.status_card = QFrame(self)
        self.status_card.setObjectName("panel")
        status_layout = QHBoxLayout(self.status_card)
        status_layout.setContentsMargins(16, 12, 16, 12)

        self.phase_indicator = QLabel("● Client Idle (None)", self.status_card)
        self.phase_indicator.setStyleSheet(f"""
            color: {COLOR_BLUE_ACCENT};
            font-size: 13px;
            font-weight: 600;
        """)
        status_layout.addWidget(self.phase_indicator)
        status_layout.addStretch()

        self.btn_find_match = QPushButton("⚔️ Find Match", self.status_card)
        self.btn_find_match.setObjectName("accent")
        self.btn_find_match.setCursor(Qt.PointingHandCursor)
        self.btn_find_match.clicked.connect(self._on_find_match)
        status_layout.addWidget(self.btn_find_match)

        layout.addWidget(self.status_card)

        # Automation Toggles Card
        toggles_card = QFrame(self)
        toggles_card.setObjectName("panel")
        toggles_layout = QVBoxLayout(toggles_card)
        toggles_layout.setContentsMargins(16, 16, 16, 16)
        toggles_layout.setSpacing(12)

        toggles_title = QLabel("AUTOMATION CONTROLS", toggles_card)
        toggles_title.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
        toggles_layout.addWidget(toggles_title)

        grid = QGridLayout()
        grid.setSpacing(12)

        self.chk_auto_accept = QCheckBox("Auto Accept Ready Check", toggles_card)
        self.chk_auto_accept.toggled.connect(lambda v: self._set_cfg("auto_accept", v))
        grid.addWidget(self.chk_auto_accept, 0, 0)

        self.chk_auto_lock = QCheckBox("Auto Lock-In Champion", toggles_card)
        self.chk_auto_lock.toggled.connect(lambda v: self._set_cfg("auto_lock_in", v))
        grid.addWidget(self.chk_auto_lock, 0, 1)

        self.chk_auto_requeue = QCheckBox("Auto Requeue on Dodge", toggles_card)
        self.chk_auto_requeue.toggled.connect(lambda v: self._set_cfg("auto_requeue", v))
        grid.addWidget(self.chk_auto_requeue, 1, 0)

        self.chk_auto_skin = QCheckBox("Auto Random Skin", toggles_card)
        self.chk_auto_skin.toggled.connect(lambda v: self._set_cfg("auto_random_skin", v))
        grid.addWidget(self.chk_auto_skin, 1, 1)

        toggles_layout.addLayout(grid)
        layout.addWidget(toggles_card)

        layout.addStretch()

    def _load_config_state(self) -> None:
        if not self.config:
            return
        self.chk_auto_accept.setChecked(bool(self.config.get("auto_accept", False)))
        self.chk_auto_lock.setChecked(bool(self.config.get("auto_lock_in", False)))
        self.chk_auto_requeue.setChecked(bool(self.config.get("auto_requeue", False)))
        self.chk_auto_skin.setChecked(bool(self.config.get("auto_random_skin", True)))

    def _set_cfg(self, key: str, val: bool) -> None:
        if self.config:
            self.config.set(key, val)

    def _on_find_match(self) -> None:
        if self.lcu and self.lcu.is_connected:
            self.lcu.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
            self.phase_indicator.setText("● Matchmaking (Searching...)")

    def update_phase(self, phase: str) -> None:
        """Update live status indicator badge."""
        self.phase_indicator.setText(f"● Client Phase: {phase}")
