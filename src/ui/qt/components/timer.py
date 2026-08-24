"""
LLTimer — semantic countdown (UI/UX Master Plan §13).

The plan is explicit that a timer must communicate meaning, not just digits:

    bad          better
    00:08        SELECT NOW
                 00:08

So the widget pairs the digits with a state label and an icon, and never
relies on colour alone (§13, §62). States are SAFE / ATTENTION / URGENT /
EXPIRED, derived from the remaining seconds.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.qt.theme.colors import (
    COLOR_DANGER,
    COLOR_NEUTRAL,
    COLOR_SUCCESS,
    COLOR_WARNING,
    TEXT_MUTED,
)
from ui.qt.theme.spacing import SPACE_SM, SPACE_XS, ICON_SM
from ui.qt.theme.typography import TEXT_DISPLAY, TEXT_MICRO

#: Seconds at or below which each state applies.
URGENT_BELOW = 8.0
ATTENTION_BELOW = 15.0


class TimerState(Enum):
    SAFE = "safe"
    ATTENTION = "attention"
    URGENT = "urgent"
    EXPIRED = "expired"


#: Icon + text + colour, never colour alone (§13).
_STATE_SPEC = {
    TimerState.SAFE: (COLOR_SUCCESS, "\u25cf"),      # filled dot
    TimerState.ATTENTION: (COLOR_WARNING, "\u25b3"),  # hollow triangle
    TimerState.URGENT: (COLOR_DANGER, "\u25b2"),      # filled triangle
    TimerState.EXPIRED: (COLOR_NEUTRAL, "\u2715"),    # cross
}


def classify(remaining_s: float) -> TimerState:
    """Map remaining seconds onto a semantic state."""
    if remaining_s <= 0:
        return TimerState.EXPIRED
    if remaining_s <= URGENT_BELOW:
        return TimerState.URGENT
    if remaining_s <= ATTENTION_BELOW:
        return TimerState.ATTENTION
    return TimerState.SAFE


def format_clock(remaining_s: float) -> str:
    total = max(0, int(remaining_s))
    return "{:02d}:{:02d}".format(total // 60, total % 60)


class LLTimer(QWidget):
    """A countdown that says what it means."""

    def __init__(
        self,
        label: str = "",
        remaining_s: float = 0.0,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._state = TimerState.SAFE
        self._label_text = label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_XS // 2)
        layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top = QHBoxLayout()
        top.setSpacing(SPACE_XS)
        top.setAlignment(Qt.AlignRight)

        self.icon = QLabel(self)
        self.icon.setFixedWidth(ICON_SM)
        self.icon.setAlignment(Qt.AlignCenter)
        top.addWidget(self.icon)

        self.caption = QLabel(self)
        top.addWidget(self.caption)
        layout.addLayout(top)

        self.digits = QLabel(self)
        self.digits.setAlignment(Qt.AlignRight)
        layout.addWidget(self.digits)

        self.set_remaining(remaining_s, label)

    def set_remaining(self, remaining_s: float, label: Optional[str] = None) -> None:
        if label is not None:
            self._label_text = label
        self._state = classify(remaining_s)
        color, glyph = _STATE_SPEC[self._state]

        caption = self._label_text or self._state.name.title()
        if self._state is TimerState.EXPIRED:
            caption = "TIME UP"

        self.icon.setText(glyph)
        self.icon.setStyleSheet(
            TEXT_MICRO.qss(color=color) + " background: transparent;"
        )
        self.caption.setText(caption.upper())
        self.caption.setStyleSheet(
            TEXT_MICRO.qss(color=color) + " background: transparent;"
        )
        self.digits.setText(format_clock(remaining_s))
        self.digits.setStyleSheet(
            TEXT_DISPLAY.qss(color=color if self._state is not TimerState.SAFE else TEXT_MUTED)
            + " background: transparent;"
        )
        self.setToolTip("{} - {} remaining".format(caption, format_clock(remaining_s)))

    @property
    def state(self) -> TimerState:
        return self._state
