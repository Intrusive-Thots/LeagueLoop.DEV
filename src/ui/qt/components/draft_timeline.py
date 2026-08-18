"""
LLDraftTimeline — compact draft progress (UI/UX Master Plan §12).

    READY  >  ROLE  >  PICK  >  BAN  >  CONFIRM
      OK       OK      now     ...     ...

Gives immediate orientation: which phase am I in, what is already done, what
is still coming. Completed / current / pending each carry a distinct glyph as
well as a colour (§62).
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ui.qt.theme.colors import (
    COLOR_SUCCESS,
    GOLD_PRIMARY,
    TEXT_MUTED,
)
from ui.qt.theme.spacing import SPACE_SM, SPACE_XS
from ui.qt.theme.typography import TEXT_MICRO

DEFAULT_PHASES = ("READY", "ROLE", "PICK", "BAN", "CONFIRM")


class StepState(Enum):
    DONE = "done"
    CURRENT = "current"
    PENDING = "pending"


#: Distinct glyph per state so the strip reads without colour (§62).
_STEP_SPEC = {
    StepState.DONE: (COLOR_SUCCESS, "\u2713"),      # check
    StepState.CURRENT: (GOLD_PRIMARY, "\u25cf"),    # filled dot
    StepState.PENDING: (TEXT_MUTED, "\u25cb"),      # hollow dot
}


class LLDraftTimeline(QWidget):
    """Horizontal phase strip for champion select."""

    def __init__(
        self,
        phases: Sequence[str] = DEFAULT_PHASES,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._phases = list(phases)
        self._current = 0
        self._labels: List[Tuple[QLabel, QLabel]] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_SM)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        for index, phase in enumerate(self._phases):
            if index:
                sep = QLabel("\u203a", self)
                sep.setStyleSheet(
                    TEXT_MICRO.qss(color=TEXT_MUTED) + " background: transparent;"
                )
                layout.addWidget(sep)

            glyph = QLabel(self)
            glyph.setFixedWidth(10)
            glyph.setAlignment(Qt.AlignCenter)
            layout.addWidget(glyph)

            name = QLabel(phase, self)
            layout.addWidget(name)

            self._labels.append((glyph, name))

        layout.addStretch(1)
        self.set_current(0)

    # ---------------------------------------------------------------- API
    def phases(self) -> List[str]:
        return list(self._phases)

    def set_current(self, index: int) -> None:
        """Highlight `index`; everything before it reads as done."""
        self._current = max(0, min(len(self._phases) - 1, int(index)))
        for i, (glyph, name) in enumerate(self._labels):
            if i < self._current:
                state = StepState.DONE
            elif i == self._current:
                state = StepState.CURRENT
            else:
                state = StepState.PENDING

            color, mark = _STEP_SPEC[state]
            glyph.setText(mark)
            glyph.setStyleSheet(
                TEXT_MICRO.qss(color=color) + " background: transparent;"
            )
            name.setStyleSheet(
                TEXT_MICRO.qss(color=color) + " background: transparent;"
            )

    def set_current_phase(self, phase: str) -> None:
        """Highlight by phase name; unknown names leave the timeline alone."""
        target = str(phase).upper()
        if target in self._phases:
            self.set_current(self._phases.index(target))

    @property
    def current_index(self) -> int:
        return self._current
