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

from PySide6.QtCore import QSize, Qt
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
from ui.qt.theme.spacing import SPACE_SM, SPACE_XS, GLYPH_WIDTH
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
        # The *detail* sentence is a different matter: "Launch the League
        # Client or switch to a stored account" is a paragraph, and refusing
        # to wrap it set a 480px floor on the card, the tab and the window.
        # So the short label keeps its minimum and the detail wraps, which
        # means the row's height is no longer fixed.
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_XS if compact else SPACE_SM)
        # No AlignLeft here. With it, the row is given only its size hint and
        # the wrapping detail label collapses to zero width — present in the
        # tree, invisible on screen, which is worse than being clipped.
        layout.setAlignment(Qt.AlignTop)

        self._glyph = QLabel(self)
        self._glyph.setAlignment(Qt.AlignCenter)
        # Fixed-width glyph container so switching states never shifts layout (§36).
        self._glyph.setFixedWidth(GLYPH_WIDTH)
        layout.addWidget(self._glyph)

        self._label = QLabel(self)
        self._label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        layout.addWidget(self._label)

        self._detail = QLabel(self)
        self._detail.setVisible(False)
        self._detail.setWordWrap(True)
        self._detail.setMinimumWidth(0)
        self._detail.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self._detail.minimumSizeHint = lambda: QSize(0, self._detail.fontMetrics().height())
        layout.addWidget(self._detail, 1)

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

    def detail(self) -> str:
        """
        The explanatory line, without the leading separator.

        `text()` alone loses half the meaning — "Not connected" without
        "Start the League Client" is the sort of status that sends someone
        looking in the wrong place.
        """
        return self._detail.text().lstrip("· ").strip()

    def sizeHint(self):
        from PySide6.QtCore import QSize
        w = self._glyph.minimumSizeHint().width() + self._label.minimumSizeHint().width() + 16
        if self._detail.isVisible() and self._detail.text():
            w += self._detail.minimumSizeHint().width() + 8
        return QSize(w, super().sizeHint().height())

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        # Glyph + Label + spacing
        w = self._glyph.minimumSizeHint().width() + self._label.minimumSizeHint().width() + 16
        return QSize(w, super().minimumSizeHint().height())
