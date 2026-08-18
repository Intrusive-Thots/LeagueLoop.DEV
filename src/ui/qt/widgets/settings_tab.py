"""
Settings (UI/UX Master Plan §23).

Organised by the user's mental model rather than by implementation, and every
setting states its name, current state and a one-sentence explanation.
"""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSeparator
from ui.qt.components.setting_row import LLSettingRow
from ui.qt.theme.colors import TEXT_MUTED, TEXT_SECONDARY
from ui.qt.theme.spacing import (
    CONTENT_MARGIN,
    CONTROL_HEIGHT_MD,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from ui.qt.theme.typography import TEXT_CAPTION, TEXT_PAGE_TITLE
from ui.qt.widgets.hotkey_dialog import QtHotkeyDialog

HOTKEYS = [
    ("hotkey_launch_client", "Launch Client"),
    ("hotkey_toggle_automation", "Toggle Automation"),
    ("hotkey_find_match", "Find Match"),
    ("hotkey_compact_mode", "Compact Mode"),
]


class QtSettingsTab(QWidget):
    """User preferences, grouped by mental model."""

    status_saved = Signal(str)

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.config = getattr(container, "config", None) if container else None
        self.lcu = getattr(container, "lcu", None) if container else None

        self._setup_ui()
        self._load_config_state()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        title = QLabel("Settings", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        root.addWidget(title)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        body = QVBoxLayout(holder)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(SPACE_MD)

        # --- General -------------------------------------------------------
        general = LLCard(title="General", parent=holder)

        self.row_tray = LLSettingRow(
            "Run in system tray",
            "Closing the window keeps LeagueLoop running in the tray.",
            parent=general,
        )
        self.row_tray.toggled.connect(lambda v: self._set_cfg("run_in_tray", v))
        general.add_widget(self.row_tray)
        general.add_widget(LLSeparator(parent=general))

        self.row_stealth = LLSettingRow(
            "Stealth mode",
            "Restores silently and suppresses background alerts.",
            parent=general,
        )
        self.row_stealth.toggled.connect(lambda v: self._set_cfg("stealth_mode", v))
        general.add_widget(self.row_stealth)
        general.add_widget(LLSeparator(parent=general))

        self.row_ontop = LLSettingRow(
            "Always on top",
            "Keeps the window above the League Client.",
            parent=general,
        )
        self.row_ontop.toggled.connect(lambda v: self._set_cfg("always_on_top", v))
        general.add_widget(self.row_ontop)
        body.addWidget(general)

        # --- Timing --------------------------------------------------------
        timing = LLCard(title="Timing", parent=holder)

        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0.0, 10.0)
        self.spin_delay.setSingleStep(0.5)
        self.spin_delay.setSuffix(" s")
        self.spin_delay.setFixedWidth(90)
        self.spin_delay.setFixedHeight(CONTROL_HEIGHT_MD)
        self.spin_delay.valueChanged.connect(
            lambda v: self._set_cfg("accept_delay", float(v))
        )
        self.row_delay = LLSettingRow(
            "Accept delay",
            "Waits this long before accepting a Ready Check, so it looks human.",
            control=self.spin_delay,
            parent=timing,
        )
        timing.add_widget(self.row_delay)
        body.addWidget(timing)

        # --- Presence ------------------------------------------------------
        presence = LLCard(title="Presence", parent=holder)

        status_row = QHBoxLayout()
        status_row.setSpacing(SPACE_SM)
        self.txt_status = QLineEdit(presence)
        self.txt_status.setPlaceholderText("Custom status shown to your friends")
        self.txt_status.setFixedHeight(CONTROL_HEIGHT_MD)
        self.txt_status.returnPressed.connect(self._on_save_status)
        status_row.addWidget(self.txt_status, 1)

        self.btn_save_status = LLButton(
            "Apply", variant=ButtonVariant.PRIMARY, parent=presence
        )
        self.btn_save_status.clicked.connect(self._on_save_status)
        status_row.addWidget(self.btn_save_status)
        presence.add_layout(status_row)

        hint = QLabel(
            "Shown on your Riot profile. Applied immediately when connected.",
            presence,
        )
        hint.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        presence.add_widget(hint)
        body.addWidget(presence)

        # --- Hotkeys (§24) --------------------------------------------------
        hotkeys = LLCard(title="Hotkeys", parent=holder)
        self.hotkey_labels: Dict[str, QLabel] = {}
        for index, (key, label) in enumerate(HOTKEYS):
            if index:
                hotkeys.add_widget(LLSeparator(parent=hotkeys))

            control_widget = QWidget(hotkeys)
            ctrl_layout = QHBoxLayout(control_widget)
            ctrl_layout.setContentsMargins(0, 0, 0, 0)
            ctrl_layout.setSpacing(SPACE_SM)

            value = QLabel("", control_widget)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value.setStyleSheet(
                TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
            )
            ctrl_layout.addWidget(value)

            btn_rebind = LLButton("Rebind", variant=ButtonVariant.SECONDARY, size=ButtonSize.SM, parent=control_widget)
            btn_rebind.clicked.connect(lambda _, k=key, l=label: self._on_rebind_hotkey(k, l))
            ctrl_layout.addWidget(btn_rebind)

            row = LLSettingRow(label, "", control=control_widget, parent=hotkeys)
            hotkeys.add_widget(row)
            self.hotkey_labels[key] = value

        body.addWidget(hotkeys)

        # --- Advanced -------------------------------------------------------
        advanced = LLCard(title="Advanced", parent=holder)
        self.row_devmode = LLSettingRow(
            "Developer mode",
            "Shows raw events, LCU traffic and UI metrics in Diagnostics.",
            parent=advanced,
        )
        self.row_devmode.toggled.connect(lambda v: self._set_cfg("developer_mode", v))
        advanced.add_widget(self.row_devmode)
        body.addWidget(advanced)

        body.addStretch(1)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

    # --------------------------------------------------------------- state
    def _load_config_state(self) -> None:
        if not self.config:
            return
        self.row_tray.set_checked(bool(self.config.get("run_in_tray", True)))
        self.row_stealth.set_checked(bool(self.config.get("stealth_mode", False)))
        self.row_ontop.set_checked(bool(self.config.get("always_on_top", True)))
        self.row_devmode.set_checked(bool(self.config.get("developer_mode", False)))
        self.spin_delay.setValue(float(self.config.get("accept_delay", 2.0)))
        self.txt_status.setText(str(self.config.get("custom_status", "")))

        for key, _label in HOTKEYS:
            value = self.config.get(key, "")
            widget = self.hotkey_labels.get(key)
            if widget is not None:
                widget.setText(str(value).upper() if value else "Not set")

    def _set_cfg(self, key: str, value) -> None:
        if self.config:
            self.config.set(key, value)

    def _on_save_status(self) -> None:
        text = self.txt_status.text().strip()
        self._set_cfg("custom_status", text)
        if self.lcu and getattr(self.lcu, "is_connected", False):
            try:
                self.lcu.request("PUT", "/lol-chat/v1/me", {"statusMessage": text})
            except Exception:
                pass
        self.status_saved.emit(text)

    def _on_rebind_hotkey(self, key: str, label: str) -> None:
        curr = str(self.config.get(key, "")) if self.config else ""
        dlg = QtHotkeyDialog(action_name=label, current_key=curr, parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_key = dlg.recorded_sequence
            self._set_cfg(key, new_key)
            widget = self.hotkey_labels.get(key)
            if widget is not None:
                widget.setText(new_key.upper() if new_key else "Not set")

    @property
    def chk_stealth(self):
        return self.row_stealth.toggle
