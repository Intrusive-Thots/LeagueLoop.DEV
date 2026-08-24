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

from PySide6.QtCore import QSize, Qt, Signal
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


#: Fixed column widths so controls line up across every row in a card.
CONTROL_COLUMN_WIDTH = 72
ACTION_COLUMN_WIDTH = 96


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
        self.name_label.setMinimumWidth(0)
        self.name_label.setStyleSheet(
            TEXT_BODY_STRONG.qss(color=TEXT_PRIMARY) + " background: transparent;"
        )
        text_col.addWidget(self.name_label)

        self.description_label = QLabel(description, self)
        self.description_label.setWordWrap(True)
        self.description_label.setMinimumWidth(0)
        self.description_label.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.description_label.setVisible(bool(description))
        text_col.addWidget(self.description_label)

        layout.addLayout(text_col, 1)

        # --- detail (e.g. "3 priorities configured") ----------------------
        self.detail_label = QLabel(detail, self)
        self.detail_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.detail_label.setMinimumWidth(0)
        self.detail_label.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.detail_label.setVisible(bool(detail))
        layout.addWidget(self.detail_label)
        layout.addSpacing(SPACE_MD)

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
        # Column width so every switch in a card lines up. Rows used to place
        # the control immediately after a variable-width detail label, so a row
        # reading "3 priorities configured" pushed its switch left of the row
        # above it and the right edge came out ragged.
        #
        # Fixed only for the switch we own. A *supplied* control gets a
        # minimum instead: forcing a width on someone else's composite widget
        # clips it — the hotkey rows, which pack a key label beside a Rebind
        # button, rendered as "IFT+L" with the button cut in half.
        if self.toggle is not None:
            self.control.setFixedWidth(CONTROL_COLUMN_WIDTH)
        else:
            self.control.setMinimumWidth(CONTROL_COLUMN_WIDTH)
        layout.addWidget(self.control, 0, Qt.AlignVCenter)

        # --- optional configuration action --------------------------------
        # The slot is always reserved, so switches align whether or not the
        # row has an action.
        self.action_button: Optional[LLButton] = None
        action_slot = QWidget(self)
        action_slot.setFixedWidth(ACTION_COLUMN_WIDTH)
        action_slot.minimumSizeHint = lambda: QSize(ACTION_COLUMN_WIDTH, action_slot.sizeHint().height())
        action_slot.setStyleSheet("background: transparent;")
        slot_layout = QHBoxLayout(action_slot)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.setSpacing(0)

        if action_label:
            # SECONDARY, not GHOST: this is a real destination, and a ghost
            # button on a card reads as a caption rather than a control.
            self.action_button = LLButton(
                action_label,
                variant=ButtonVariant.SECONDARY,
                size=ButtonSize.SM,
                parent=action_slot,
            )
            self.action_button.setToolTip("Open {}".format(action_label.lower()))
            self.action_button.clicked.connect(self.action_clicked.emit)
            slot_layout.addWidget(self.action_button)
        slot_layout.addStretch(1)
        layout.addWidget(action_slot, 0, Qt.AlignVCenter)

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

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        hint = super().minimumSizeHint()
        return QSize(300, hint.height())
