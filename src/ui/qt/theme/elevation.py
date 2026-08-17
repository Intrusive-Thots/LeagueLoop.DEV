"""
Elevation Tokens for LeagueLoop UI (UI/UX Master Plan §34, §39).

A deliberately small elevation system:
    0 — flat
    1 — raised
    2 — floating
    3 — modal

§39 prefers surface contrast and spacing over borders everywhere, so
elevation is applied sparingly and always via these tokens.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

ELEVATION_FLAT = 0
ELEVATION_RAISED = 1
ELEVATION_FLOATING = 2
ELEVATION_MODAL = 3


@dataclass(frozen=True)
class Elevation:
    """Shadow parameters for one elevation level."""

    blur: int
    y_offset: int
    alpha: int  # 0-255

    def is_flat(self) -> bool:
        return self.blur == 0 and self.y_offset == 0


ELEVATIONS = {
    ELEVATION_FLAT: Elevation(blur=0, y_offset=0, alpha=0),
    ELEVATION_RAISED: Elevation(blur=8, y_offset=2, alpha=100),
    ELEVATION_FLOATING: Elevation(blur=18, y_offset=6, alpha=115),
    ELEVATION_MODAL: Elevation(blur=32, y_offset=10, alpha=140),
}


def apply_elevation(widget: QWidget, level: int = ELEVATION_RAISED) -> Optional[QGraphicsDropShadowEffect]:
    """
    Apply an elevation shadow to a widget.

    Returns the effect (or None for flat) so callers can animate or clear it.
    Passing ELEVATION_FLAT removes any existing shadow.
    """
    spec = ELEVATIONS.get(level, ELEVATIONS[ELEVATION_FLAT])
    if spec.is_flat():
        widget.setGraphicsEffect(None)
        return None

    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(spec.blur)
    effect.setXOffset(0)
    effect.setYOffset(spec.y_offset)
    effect.setColor(QColor(0, 0, 0, spec.alpha))
    widget.setGraphicsEffect(effect)
    return effect


__all__ = [
    "ELEVATION_FLAT",
    "ELEVATION_RAISED",
    "ELEVATION_FLOATING",
    "ELEVATION_MODAL",
    "Elevation",
    "ELEVATIONS",
    "apply_elevation",
]
