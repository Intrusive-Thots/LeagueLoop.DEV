"""
LLToast / LLToastManager — In-app floating feedback notifications.
Aligned with UI/UX Master Plan §21 & §62.
"""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.status import Tone, tone_color, tone_glyph
from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    GOLD_PRIMARY,
    SURFACE_PANEL_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from ui.qt.theme.radii import RADIUS_MD
from ui.qt.theme.spacing import SPACE_MD, SPACE_SM, SPACE_XS
from ui.qt.theme.typography import FONT_FAMILY, TEXT_BODY, TEXT_CAPTION, WEIGHT_BOLD, WEIGHT_MEDIUM


class LLToast(QFrame):
    """A floating notification badge with semantic color, title, and message."""

    dismissed = Signal(object)  # emits self

    def __init__(
        self,
        title: str,
        message: str = "",
        tone: Tone = Tone.INFO,
        duration_ms: int = 3500,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.tone = tone
        self.duration_ms = duration_ms

        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(320)

        color = tone_color(tone)
        glyph = tone_glyph(tone)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE_PANEL_ELEVATED};
                border: 1px solid {BORDER_DEFAULT};
                border-left: 4px solid {color};
                border-radius: {RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        layout.setSpacing(SPACE_SM)

        # Glyph
        lbl_glyph = QLabel(glyph, self)
        lbl_glyph.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 14px;
                font-weight: {WEIGHT_BOLD};
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(lbl_glyph, 0, Qt.AlignTop)

        # Text Column
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        lbl_title = QLabel(title, self)
        lbl_title.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                font-weight: {WEIGHT_BOLD};
                background: transparent;
                border: none;
            }}
        """)
        text_col.addWidget(lbl_title)

        if message:
            lbl_msg = QLabel(message, self)
            lbl_msg.setWordWrap(True)
            lbl_msg.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_MUTED};
                    font-family: {FONT_FAMILY};
                    font-size: 11px;
                    font-weight: {WEIGHT_MEDIUM};
                    background: transparent;
                    border: none;
                }}
            """)
            text_col.addWidget(lbl_msg)

        layout.addLayout(text_col, 1)

        # Close button
        btn_close = QPushButton("✕", self)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedSize(18, 18)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_MUTED};
                background: transparent;
                border: none;
                font-size: 10px;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
            }}
        """)
        btn_close.clicked.connect(self.dismiss)
        layout.addWidget(btn_close, 0, Qt.AlignTop)

        if duration_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.dismiss)
            self._timer.start(duration_ms)

    def dismiss(self) -> None:
        """Dismiss the toast and notify the manager."""
        self.dismissed.emit(self)
        self.hide()
        self.deleteLater()


class LLToastManager:
    """Manages active toast notifications anchored to a target window."""

    _instance: Optional[LLToastManager] = None

    def __init__(self, target_widget: Optional[QWidget] = None):
        self.target = target_widget
        self.active_toasts: List[LLToast] = []

    @classmethod
    def instance(cls, target_widget: Optional[QWidget] = None) -> LLToastManager:
        if cls._instance is None or (target_widget and cls._instance.target != target_widget):
            cls._instance = LLToastManager(target_widget)
        return cls._instance

    def show_toast(
        self,
        title: str,
        message: str = "",
        tone: Tone = Tone.INFO,
        duration_ms: int = 3500,
    ) -> LLToast:
        """Create and position a toast notification."""
        parent = self.target if self.target and self.target.isVisible() else None
        toast = LLToast(title, message, tone=tone, duration_ms=duration_ms, parent=parent)
        toast.dismissed.connect(self._on_toast_dismissed)
        self.active_toasts.append(toast)
        toast.show()
        self.reposition()
        return toast

    def _on_toast_dismissed(self, toast: LLToast) -> None:
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)
            self.reposition()

    def reposition(self) -> None:
        """Stack toasts in the bottom-right corner of the parent or primary window."""
        if not self.target:
            return

        margin = 16
        gap = 8
        target_rect = self.target.geometry()

        bottom_y = self.target.height() - margin
        right_x = self.target.width() - 320 - margin

        for toast in reversed(self.active_toasts):
            h = toast.sizeHint().height() or 54
            toast.setGeometry(right_x, bottom_y - h, 320, h)
            toast.raise_()
            bottom_y -= (h + gap)
