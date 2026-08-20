"""
LLTextField — labelled text input (UI/UX Master Plan §33, §55, §63).

A field is a label, a control, and one line underneath that is either an
explanation or an error — never both, never a silent failure. Validation
messages replace the helper text in place rather than appearing as a popup,
so the eye never has to leave the field it is fixing.

Password fields get a reveal toggle. Nobody can retype a 20-character
password blind, and hiding it by default while making it *checkable* is the
combination that avoids both shoulder-surfing and typos.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.focus import install_focus_visible
from ui.qt.theme.colors import (
    BORDER_ACTIVE,
    BORDER_DEFAULT,
    COLOR_DANGER,
    FOCUS_RING,
    SURFACE_SUNKEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.radii import RADIUS_SM
from ui.qt.theme.spacing import CONTROL_HEIGHT_MD, SPACE_SM, SPACE_XS, SPACE_XXS
from ui.qt.theme.typography import (
    FONT_FAMILY,
    TEXT_CAPTION,
    TEXT_MICRO,
    WEIGHT_REGULAR,
)


class LLTextField(QWidget):
    """Label + input + helper/error line."""

    text_changed = Signal(str)
    returned = Signal()

    def __init__(
        self,
        label: str,
        placeholder: str = "",
        helper: str = "",
        password: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._helper_text = helper
        self._is_password = password

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_XXS)

        self.label = QLabel(label.upper(), self)
        self.label.setStyleSheet(
            TEXT_MICRO.qss(color=TEXT_SECONDARY) + " background: transparent;"
        )
        layout.addWidget(self.label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACE_XS)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText(placeholder)
        self.input.setFixedHeight(CONTROL_HEIGHT_MD)
        self.input.setAccessibleName(label)
        if password:
            self.input.setEchoMode(QLineEdit.Password)
        install_focus_visible(self.input)
        self.input.textChanged.connect(self._on_text_changed)
        self.input.returnPressed.connect(self.returned.emit)
        row.addWidget(self.input, 1)

        self.reveal: Optional[QLabel] = None
        if password:
            from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton

            self.reveal = LLButton(
                "Show", variant=ButtonVariant.GHOST, size=ButtonSize.SM, parent=self
            )
            self.reveal.setCheckable(True)
            self.reveal.setToolTip("Show the password")
            self.reveal.toggled.connect(self._on_reveal_toggled)
            row.addWidget(self.reveal)

        layout.addLayout(row)

        self.message = QLabel(helper, self)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        self._apply_input_style(error=False)
        self._apply_message_style(error=False)
        self.message.setVisible(bool(helper))

    # ------------------------------------------------------------- styling
    def _apply_input_style(self, error: bool) -> None:
        border = COLOR_DANGER if error else BORDER_DEFAULT
        self.input.setStyleSheet(f"""
            QLineEdit {{
                font-family: {FONT_FAMILY};
                font-size: 13px;
                font-weight: {WEIGHT_REGULAR};
                color: {TEXT_PRIMARY};
                background-color: {SURFACE_SUNKEN};
                border: 1px solid {border};
                border-radius: {RADIUS_SM}px;
                padding: 0px {SPACE_SM}px;
                selection-background-color: {BORDER_ACTIVE};
                selection-color: {SURFACE_SUNKEN};
            }}
            QLineEdit:hover {{
                border: 1px solid {COLOR_DANGER if error else BORDER_ACTIVE};
            }}
            QLineEdit[keyboardFocus="true"] {{
                border: 1px solid {FOCUS_RING};
            }}
            QLineEdit:disabled {{
                color: {TEXT_MUTED};
                border: 1px solid {BORDER_DEFAULT};
            }}
        """)

    def _apply_message_style(self, error: bool) -> None:
        color = COLOR_DANGER if error else TEXT_MUTED
        self.message.setStyleSheet(
            TEXT_CAPTION.qss(color=color) + " background: transparent;"
        )

    # -------------------------------------------------------------- events
    def _on_text_changed(self, value: str) -> None:
        # Typing is the user fixing the problem; stop shouting at them while
        # they do it (§55 — errors clear on correction, not on resubmit).
        if self.has_error():
            self.clear_error()
        self.text_changed.emit(value)

    def _on_reveal_toggled(self, shown: bool) -> None:
        self.input.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password)
        if self.reveal is not None:
            self.reveal.setText("Hide" if shown else "Show")
            self.reveal.setToolTip(
                "Hide the password" if shown else "Show the password"
            )

    # --------------------------------------------------------------- state
    def text(self) -> str:
        return self.input.text()

    def set_text(self, value: str) -> None:
        self.input.setText(value or "")

    def set_enabled(self, enabled: bool) -> None:
        self.input.setEnabled(enabled)
        if self.reveal is not None:
            self.reveal.setEnabled(enabled)

    def has_error(self) -> bool:
        return bool(self.message.property("llError"))

    def set_error(self, message: str) -> None:
        self.message.setProperty("llError", True)
        self.message.setText(message)
        self.message.setVisible(True)
        self._apply_input_style(error=True)
        self._apply_message_style(error=True)
        self.input.setAccessibleDescription(message)

    def clear_error(self) -> None:
        self.message.setProperty("llError", False)
        self.message.setText(self._helper_text)
        self.message.setVisible(bool(self._helper_text))
        self._apply_input_style(error=False)
        self._apply_message_style(error=False)
        self.input.setAccessibleDescription(self._helper_text)

    def focus(self) -> None:
        self.input.setFocus(Qt.OtherFocusReason)
