"""
Hotkey Recorder Dialog — Interactive keybinding recorder for QtSettingsTab.
"""
from __future__ import annotations

from ui.qt.services.popup_size import size_to_content
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.qt.components.button import ButtonVariant, LLButton
from ui.qt.theme.colors import BORDER_DEFAULT, GOLD_LIGHT, GOLD_PRIMARY, TEXT_MUTED, TEXT_PRIMARY
from ui.qt.theme.radii import RADIUS_MD
from ui.qt.theme.spacing import SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import TEXT_BODY, TEXT_PAGE_TITLE


class QtHotkeyDialog(QDialog):
    """Captures keypresses to rebind a global shortcut."""

    def __init__(
        self,
        action_name: str,
        current_key: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.action_name = action_name
        self.current_key = current_key
        self.recorded_sequence: str = current_key

        self.setWindowTitle(f"Rebind Hotkey: {action_name}")
        # Was setFixedSize(360, 200), which clipped the instruction text at
        # 125% Windows scaling and above — the size was measured once, at
        # 100%, and then frozen.
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #0A1428;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD}px;
            }}
        """)

        self._setup_ui()
        size_to_content(self, min_size=(360, 200), max_size=(520, 320))

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        layout.setSpacing(SPACE_MD)

        title = QLabel(f"Rebind: {self.action_name}", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=GOLD_LIGHT))
        layout.addWidget(title)

        self.lbl_key = QLabel(self.current_key.upper() if self.current_key else "Press any key...", self)
        self.lbl_key.setAlignment(Qt.AlignCenter)
        self.lbl_key.setStyleSheet(f"""
            QLabel {{
                background-color: #010A13;
                border: 2px dashed {GOLD_PRIMARY};
                border-radius: {RADIUS_MD}px;
                color: {TEXT_PRIMARY};
                font-size: 16px;
                font-weight: bold;
                padding: 16px;
            }}
        """)
        layout.addWidget(self.lbl_key)

        hint = QLabel("Press Escape to cancel, or Backspace to clear shortcut.", self)
        hint.setStyleSheet(TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_clear = LLButton("Clear", variant=ButtonVariant.SECONDARY, parent=self)
        btn_clear.clicked.connect(self._on_clear)
        btn_row.addWidget(btn_clear)

        btn_cancel = LLButton("Cancel", variant=ButtonVariant.SECONDARY, parent=self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = LLButton("Save", variant=ButtonVariant.PRIMARY, parent=self)
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        if key == Qt.Key_Escape:
            self.reject()
            return
        elif key in (Qt.Key_Backspace, Qt.Key_Delete):
            self._on_clear()
            return

        modifiers = event.modifiers()
        parts = []
        if modifiers & Qt.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.ShiftModifier:
            parts.append("Shift")

        key_text = QKeySequence(key).toString()
        if key_text:
            parts.append(key_text)

        self.recorded_sequence = "+".join(parts)
        self.lbl_key.setText(self.recorded_sequence.upper())
        event.accept()

    def _on_clear(self) -> None:
        self.recorded_sequence = ""
        self.lbl_key.setText("NONE (DISABLED)")
