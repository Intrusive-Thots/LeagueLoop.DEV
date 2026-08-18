"""
LLSettingRow — one configurable setting (UI/UX Master Plan §7, §23).

Both the automation control centre and the settings screen require the same
four things per control, and the plan is explicit about it:

    name
    current state
    one-sentence explanation
    the control itself
    (optionally) a configuration action

So this is one component rather than two divergent ones.

    Auto Pick                                  [detail]  ( ON )  [ Edit ]
    Uses your priority list
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.toggle import LLToggle
from ui.qt.theme.colors import TEXT_MUTED, TEXT_PRIMARY
from ui.qt.theme.spacing import ROW_HEIGHT, SPACE_MD, SPACE_SM, SPACE_XS
from ui.qt.theme.typography import TEXT_BODY_STRONG, TEXT_CAPTION


class LLSettingRow(QWidget):
    """A labelled setting with an explanation, a toggle and optional action."""

    toggled = Signal(bool)
    action_clicked = Signal()

    def __init__(
        self,
        name: str,
        description: str = "",
        checked: bool = False,
        detail: str = "",
        action_label: str = "",
        control: Optional[QWidget] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setMinimumHeight(ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACE_XS, 0, SPACE_XS)
        layout.setSpacing(SPACE_MD)

        # --- name + explanation ------------------------------------------
        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        self.name_label = QLabel(name, self)
        self.name_label.setStyleSheet(
            TEXT_BODY_STRONG.qss(color=TEXT_PRIMARY) + " background: transparent;"
        )
        text_col.addWidget(self.name_label)

        self.description_label = QLabel(description, self)
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.description_label.setVisible(bool(description))
        text_col.addWidget(self.description_label)

        layout.addLayout(text_col, 1)

        # --- detail (e.g. "3 priorities configured") ----------------------
        self.detail_label = QLabel(detail, self)
        self.detail_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.detail_label.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.detail_label.setVisible(bool(detail))
        layout.addWidget(self.detail_label)

        # --- control ------------------------------------------------------
        # Defaults to a switch, but any widget can be supplied so settings
        # rows (delays, text fields, dropdowns) reuse this one component
        # rather than growing a parallel implementation (§33).
        self.toggle: Optional[LLToggle] = None
        if control is None:
            self.toggle = LLToggle(checked, parent=self)
            self.toggle.toggled_on.connect(self._on_toggled)
            self.control = self.toggle
        else:
            control.setParent(self)
            self.control = control
        layout.addWidget(self.control, 0, Qt.AlignVCenter)

        # --- optional configuration action --------------------------------
        self.action_button: Optional[LLButton] = None
        if action_label:
            self.action_button = LLButton(
                action_label,
                variant=ButtonVariant.GHOST,
                size=ButtonSize.SM,
                parent=self,
            )
            self.action_button.clicked.connect(self.action_clicked.emit)
            layout.addWidget(self.action_button, 0, Qt.AlignVCenter)

        self._sync_tooltip()

    # ------------------------------------------------------------------ API
    def is_checked(self) -> bool:
        return bool(self.toggle and self.toggle.isChecked())

    def set_checked(self, checked: bool) -> None:
        if self.toggle is not None:
            self.toggle.setChecked(checked)
            self._sync_tooltip()

    def set_detail(self, detail: str) -> None:
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))

    def set_description(self, description: str) -> None:
        self.description_label.setText(description)
        self.description_label.setVisible(bool(description))

    def set_enabled_state(self, enabled: bool, reason: str = "") -> None:
        """Disable the control, explaining why rather than silently greying."""
        self.control.setEnabled(enabled)
        if self.action_button is not None:
            self.action_button.setEnabled(enabled)
        self.name_label.setEnabled(enabled)
        self.description_label.setEnabled(enabled)
        if reason:
            self.setToolTip(reason)
        else:
            self._sync_tooltip()

    def _on_toggled(self, checked: bool) -> None:
        self._sync_tooltip()
        self.toggled.emit(checked)

    def _sync_tooltip(self) -> None:
        base = self.name_label.text()
        desc = self.description_label.text()
        if self.toggle is not None:
            base = "{} - {}".format(base, "On" if self.toggle.isChecked() else "Off")
        self.setToolTip("{}{}".format(base, "\n" + desc if desc else ""))
