"""
LLBadge — compact labelled pill (UI/UX Master Plan §33, §62).

Used for counts, priority numbers, queue names, and "RECOMMENDED" /
"BACKUP" markers in the draft surfaces. Like LLStatus it pairs its
semantic color with text, so color is never the only signal (§62).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from ui.qt.theme.colors import (
    COLOR_DANGER,
    COLOR_DANGER_SUBTLE,
    COLOR_INFO,
    COLOR_INFO_SUBTLE,
    COLOR_NEUTRAL,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_SUCCESS,
    COLOR_SUCCESS_SUBTLE,
    COLOR_WARNING,
    COLOR_WARNING_SUBTLE,
    GOLD_PRIMARY,
    GOLD_SUBTLE,
)
from ui.qt.theme.radii import RADIUS_SM
from ui.qt.theme.spacing import SPACE_SM, SPACE_XS
from ui.qt.theme.typography import TEXT_MICRO
from ui.qt.components.status import Tone

#: Badges sit on a single text line; fixed so they never stretch a row.
BADGE_HEIGHT = 22

_BADGE_SPEC = {
    Tone.NEUTRAL: (COLOR_NEUTRAL, COLOR_NEUTRAL_SUBTLE),
    Tone.SUCCESS: (COLOR_SUCCESS, COLOR_SUCCESS_SUBTLE),
    Tone.WARNING: (COLOR_WARNING, COLOR_WARNING_SUBTLE),
    Tone.DANGER: (COLOR_DANGER, COLOR_DANGER_SUBTLE),
    Tone.INFO: (COLOR_INFO, COLOR_INFO_SUBTLE),
    Tone.ACCENT: (GOLD_PRIMARY, GOLD_SUBTLE),
}


class LLBadge(QLabel):
    """A small pill label carrying a short piece of state."""

    def __init__(
        self,
        text: str = "",
        tone: Tone = Tone.NEUTRAL,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self._tone = tone
        self.setAlignment(Qt.AlignCenter)
        # A badge hugs its text. Without this it stretches to fill whatever
        # row it is dropped into (e.g. the full height of the header band).
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setFixedHeight(BADGE_HEIGHT)
        self._apply_style()

    def set_tone(self, tone: Tone) -> None:
        self._tone = tone
        self._apply_style()

    def set_badge(self, text: str, tone: Optional[Tone] = None) -> None:
        self.setText(text)
        if tone is not None:
            self._tone = tone
        self._apply_style()

    @property
    def tone(self) -> Tone:
        return self._tone

    def _apply_style(self) -> None:
        fg, bg = _BADGE_SPEC.get(self._tone, _BADGE_SPEC[Tone.NEUTRAL])
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {fg};
                border-radius: {RADIUS_SM}px;
                padding: {SPACE_XS // 2}px {SPACE_SM}px;
                {TEXT_MICRO.qss()}
            }}
        """)
