"""
PySide6 Settings Tab Widget for LeagueLoop.
Provides configuration options for stealth mode, accept delay, polling rates, and custom status.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.qt.theme import (
    COLOR_BACKGROUND_CARD,
    COLOR_BACKGROUND_DARK,
    COLOR_BACKGROUND_PANEL,
    COLOR_BORDER,
    COLOR_BORDER_GOLD,
    COLOR_GOLD_PRIMARY,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class QtSettingsTab(QWidget):
    """User preferences and behavioral configuration tab."""

    def __init__(self, container=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.container = container
        self.config = container.config if container else None
        self.lcu = container.lcu if container else None

        self._setup_ui()
        self._load_config_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header Title
        header = QLabel("Application Settings", self)
        header.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {COLOR_GOLD_PRIMARY};
        """)
        layout.addWidget(header)

        # General Card
        card = QFrame(self)
        card.setObjectName("panel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(14)

        card_title = QLabel("GENERAL PREFERENCES", card)
        card_title.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
        card_layout.addWidget(card_title)

        self.chk_stealth = QCheckBox("Stealth Mode (Silent restore & zero background alerts)", card)
        self.chk_stealth.toggled.connect(lambda v: self._set_cfg("stealth_mode", v))
        card_layout.addWidget(self.chk_stealth)

        self.chk_skip_stats = QCheckBox("Auto Skip Post-Game Stats Screen", card)
        self.chk_skip_stats.toggled.connect(lambda v: self._set_cfg("skip_stats_enabled", v))
        card_layout.addWidget(self.chk_skip_stats)

        # Delay Setting
        delay_layout = QHBoxLayout()
        lbl_delay = QLabel("Accept Delay (seconds):", card)
        lbl_delay.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px;")
        self.spin_delay = QDoubleSpinBox(card)
        self.spin_delay.setRange(0.0, 10.0)
        self.spin_delay.setSingleStep(0.5)
        self.spin_delay.valueChanged.connect(lambda v: self._set_cfg("accept_delay", float(v)))
        delay_layout.addWidget(lbl_delay)
        delay_layout.addWidget(self.spin_delay)
        delay_layout.addStretch()
        card_layout.addLayout(delay_layout)

        layout.addWidget(card)

        # Custom Status Card
        status_card = QFrame(self)
        status_card.setObjectName("panel")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 16, 16, 16)
        status_layout.setSpacing(12)

        status_title = QLabel("RIOT CLIENT CUSTOM STATUS", status_card)
        status_title.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
        status_layout.addWidget(status_title)

        self.txt_status = QLineEdit(status_card)
        self.txt_status.setPlaceholderText("Enter custom presence message...")
        status_layout.addWidget(self.txt_status)

        status_btn_layout = QHBoxLayout()
        self.btn_save_status = QPushButton("Save & Apply Status", status_card)
        self.btn_save_status.setObjectName("accent")
        self.btn_save_status.clicked.connect(self._on_save_status)
        status_btn_layout.addWidget(self.btn_save_status)
        status_btn_layout.addStretch()
        status_layout.addLayout(status_btn_layout)

        layout.addWidget(status_card)
        layout.addStretch()

    def _load_config_state(self) -> None:
        if not self.config:
            return
        self.chk_stealth.setChecked(bool(self.config.get("stealth_mode", False)))
        self.chk_skip_stats.setChecked(bool(self.config.get("skip_stats_enabled", True)))
        self.spin_delay.setValue(float(self.config.get("accept_delay", 2.0)))
        self.txt_status.setText(str(self.config.get("custom_status", "")))

    def _set_cfg(self, key: str, val) -> None:
        if self.config:
            self.config.set(key, val)

    def _on_save_status(self) -> None:
        text = self.txt_status.text().strip()
        self._set_cfg("custom_status", text)
        if self.lcu and self.lcu.is_connected:
            self.lcu.request("PUT", "/lol-chat/v1/me", {"statusMessage": text})
