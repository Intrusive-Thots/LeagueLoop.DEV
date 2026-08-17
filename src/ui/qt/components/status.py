"""
LLStatus — the universal status component (UI/UX Master Plan §20).

One reusable way to say "what is happening" anywhere in the app:

    ● Connected
    ● Automation enabled
    ● Waiting
    ⚠ Reconnecting
    ✕ Disconnected

Every status is a glyph + text (+ optional detail). Per §20 and §62 the
color is never the sole meaning carrier — each tone owns a distinct glyph,
so the component still reads correctly in grayscale or for color-blind users.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from ui.qt.theme.colors import (
    COLOR_DANGER,
    COLOR_INFO,
    COLOR_NEUTRAL,
    COLOR_SUCCESS,
    COLOR_WARNING,
    GOLD_PRIMARY,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from ui.qt.theme.spacing import SPACE_SM, SPACE_XS
from ui.qt.theme.typography import TEXT_BODY, TEXT_CAPTION


class Tone(Enum):
    """Semantic tone of a status (§62)."""

    NEUTRAL = "neutral"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    INFO = "info"
    ACCENT = "accent"


#: Each tone pairs a color with a distinct glyph so meaning survives without color.
_TONE_SPEC = {
    Tone.NEUTRAL: (COLOR_NEUTRAL, "○"),
    Tone.SUCCESS: (COLOR_SUCCESS, "●"),
    Tone.WARNING: (COLOR_WARNING, "⚠"),
    Tone.DANGER: (COLOR_DANGER, "✕"),
    Tone.INFO: (COLOR_INFO, "◆"),
    Tone.ACCENT: (GOLD_PRIMARY, "●"),
}


def tone_color(tone: Tone) -> str:
    """Public accessor so other widgets can match a status color."""
    return _TONE_SPEC.get(tone, _TONE_SPEC[Tone.NEUTRAL])[0]


def tone_glyph(tone: Tone) -> str:
    return _TONE_SPEC.get(tone, _TONE_SPEC[Tone.NEUTRAL])[1]


class LLStatus(QWidget):
    """
    A single status readout: glyph + label + optional detail.

    Parameters
    ----------
    text:
        The status itself, in product vocabulary (§56) — "Connected",
        "Disconnected", "Waiting" — never log-speak.
    tone:
        Semantic tone driving color and glyph.
    detail:
        Optional secondary text, rendered muted after a separator.
    compact:
        Drop the detail and tighten spacing (for dense header use).
    """

    def __init__(
        self,
        text: str = "",
        tone: Tone = Tone.NEUTRAL,
        detail: Optional[str] = None,
        compact: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._tone = tone
        self._compact = compact

        # A status must never be squeezed narrower than its own text — a
        # clipped "In queue" reading as "In que" is worse than a tight row.
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_XS if compact else SPACE_SM)
        layout.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self._glyph = QLabel(self)
        self._glyph.setAlignment(Qt.AlignCenter)
        # Fixed-width glyph container so switching states never shifts layout (§36).
        self._glyph.setFixedWidth(12)
        layout.addWidget(self._glyph)

        self._label = QLabel(self)
        layout.addWidget(self._label)

        self._detail = QLabel(self)
        self._detail.setVisible(False)
        layout.addWidget(self._detail)

        self.set_status(text, tone, detail)

    # ------------------------------------------------------------------ API
    def set_status(
        self,
        text: str,
        tone: Optional[Tone] = None,
        detail: Optional[str] = None,
    ) -> None:
        """Update text, tone and detail in one call."""
        if tone is not None:
            self._tone = tone

        color, glyph = _TONE_SPEC.get(self._tone, _TONE_SPEC[Tone.NEUTRAL])

        self._glyph.setText(glyph)
        self._glyph.setStyleSheet(f"color: {color}; {TEXT_BODY.qss()}")

        self._label.setText(text)
        self._label.setStyleSheet(TEXT_BODY.qss(color=TEXT_PRIMARY))

        if detail and not self._compact:
            self._detail.setText(f"·  {detail}")
            self._detail.setStyleSheet(TEXT_CAPTION.qss(color=TEXT_MUTED))
            self._detail.setVisible(True)
        else:
            self._detail.setVisible(False)

        # Screen-reader / tooltip fallback (§30, §64)
        self.setToolTip(f"{text} — {detail}" if detail else text)

    def set_tone(self, tone: Tone) -> None:
        self.set_status(self._label.text(), tone, self._detail.text().lstrip("· ") or None)

    @property
    def tone(self) -> Tone:
        return self._tone

    def text(self) -> str:
        return self._label.text()
