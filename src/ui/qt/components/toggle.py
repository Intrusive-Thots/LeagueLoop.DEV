"""
LLToggle — the switch control (UI/UX Master Plan §33, §63).

A painted switch rather than a checkbox: the automation surfaces read as
"ON / OFF" state (§7), and a switch communicates that faster than a tick.

Carries every state §63 requires - hover, pressed, disabled, focus, checked -
and pairs its colour with an ON/OFF label so it is not colour-only (§62).
Knob movement uses the shared motion tokens and honours reduced motion (§30).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget

from ui.qt.components.focus import install_focus_visible
from ui.qt.theme.colors import (
    BORDER_ACCENT,
    BORDER_DEFAULT,
    COLOR_SUCCESS,
    FOCUS_RING,
    GOLD_LIGHT,
    SURFACE_SUNKEN,
    TEXT_DISABLED,
    TEXT_MUTED,
)
from ui.qt.theme.motion import DURATION_HOVER, duration
from ui.qt.theme.typography import FONT_FAMILY_PRIMARY, WEIGHT_BOLD

TRACK_W = 40
TRACK_H = 22
KNOB_R = 8
LABEL_W = 26


class LLToggle(QAbstractButton):
    """An on/off switch with an adjacent ON/OFF label."""

    toggled_on = Signal(bool)

    def __init__(self, checked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(TRACK_W + LABEL_W + 6, TRACK_H)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.StrongFocus)
        install_focus_visible(self)

        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.toggled.connect(self._on_toggled)
        self._update_accessible()

    # ------------------------------------------------------- animation
    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = float(value)
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _on_toggled(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setDuration(duration(DURATION_HOVER))
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()
        self._update_accessible()
        self.toggled_on.emit(checked)

    def _update_accessible(self) -> None:
        self.setAccessibleDescription("On" if self.isChecked() else "Off")

    # --------------------------------------------------------- painting
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        enabled = self.isEnabled()
        checked = self.isChecked()

        if not enabled:
            track_fill = QColor(SURFACE_SUNKEN)
            track_edge = QColor(BORDER_DEFAULT)
            knob = QColor(TEXT_DISABLED)
            text = QColor(TEXT_DISABLED)
        elif checked:
            track_fill = QColor(COLOR_SUCCESS)
            track_fill.setAlpha(60)
            track_edge = QColor(COLOR_SUCCESS)
            knob = QColor(COLOR_SUCCESS)
            text = QColor(COLOR_SUCCESS)
        else:
            track_fill = QColor(SURFACE_SUNKEN)
            track_edge = QColor(BORDER_ACCENT if self.underMouse() else BORDER_DEFAULT)
            knob = QColor(TEXT_MUTED)
            text = QColor(TEXT_MUTED)

        track = QRectF(0, (self.height() - TRACK_H) / 2, TRACK_W, TRACK_H)
        painter.setBrush(track_fill)
        painter.setPen(QPen(track_edge, 1))
        painter.drawRoundedRect(track, TRACK_H / 2, TRACK_H / 2)

        if self.hasFocus() and self.property("keyboardFocus"):
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(FOCUS_RING), 2))
            painter.drawRoundedRect(track.adjusted(-1, -1, 1, 1), TRACK_H / 2, TRACK_H / 2)

        travel = TRACK_W - 2 * (KNOB_R + 3)
        cx = track.left() + KNOB_R + 3 + travel * self._offset
        painter.setPen(Qt.NoPen)
        painter.setBrush(knob)
        painter.drawEllipse(QRectF(cx - KNOB_R, track.center().y() - KNOB_R,
                                   KNOB_R * 2, KNOB_R * 2))

        font = QFont(FONT_FAMILY_PRIMARY)
        font.setPixelSize(10)
        font.setWeight(QFont.Weight(WEIGHT_BOLD))
        painter.setFont(font)
        painter.setPen(text)
        painter.drawText(
            QRectF(TRACK_W + 6, 0, LABEL_W, self.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            "ON" if checked else "OFF",
        )
        painter.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)
