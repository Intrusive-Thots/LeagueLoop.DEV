"""
LLToast & QtToastManager (LLToastManager) — Non-blocking Floating Feedback (UI/UX Master Plan §19, §33).

Provides transient feedback toasts that slide/fade into view when actions occur
(e.g., account switched, loot opened, backup pick locked, config saved) and
auto-dismiss after a configurable duration without blocking user workflow.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer
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
    SURFACE_PANEL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.radii import RADIUS_MD
from ui.qt.theme.spacing import SPACE_MD, SPACE_SM, SPACE_XS
from ui.qt.theme.typography import TEXT_BODY, TEXT_BODY_STRONG, TEXT_CAPTION


class LLToast(QFrame):
    """A single floating toast card."""

    def __init__(
        self,
        message: str,
        title: str = "",
        tone: Tone = Tone.INFO,
        duration_ms: int = 4000,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.tone = tone
        self._manager: Optional["QtToastManager"] = None

        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        border_col = tone_color(tone)
        glyph = tone_glyph(tone)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE_PANEL};
                border: 1px solid {border_col};
                border-left: 4px solid {border_col};
                border-radius: {RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        layout.setSpacing(SPACE_SM)

        # Glyph indicator
        lbl_glyph = QLabel(glyph, self)
        lbl_glyph.setStyleSheet(f"color: {border_col}; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        lbl_glyph.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        layout.addWidget(lbl_glyph)

        # Text column
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        if title:
            lbl_title = QLabel(title, self)
            lbl_title.setStyleSheet(TEXT_BODY_STRONG.qss(color=TEXT_PRIMARY) + " background: transparent; border: none;")
            text_col.addWidget(lbl_title)

        lbl_msg = QLabel(message, self)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet(TEXT_CAPTION.qss(color=TEXT_SECONDARY) + " background: transparent; border: none;")
        text_col.addWidget(lbl_msg)
        layout.addLayout(text_col, 1)

        # Dismiss button
        btn_close = QPushButton("✕", self)
        btn_close.setFixedSize(18, 18)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_MUTED};
                background: transparent;
                border: none;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
            }}
        """)
        btn_close.clicked.connect(self.dismiss)
        layout.addWidget(btn_close)

        self.setFixedWidth(300)

        # Opacity animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")

        # Timer for auto-dismiss
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self.dismiss)

    def show_animated(self) -> None:
        self.show()
        self.opacity_anim.stop()
        self.opacity_anim.setDuration(250)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.opacity_anim.start()

    def dismiss(self) -> None:
        if self._manager and self in self._manager._active_toasts:
            self._manager._active_toasts.remove(self)
        self.opacity_anim.stop()
        self.opacity_anim.setDuration(200)
        self.opacity_anim.setStartValue(self.opacity_effect.opacity())
        self.opacity_anim.setEndValue(0.0)
        self.opacity_anim.setEasingCurve(QEasingCurve.InCubic)
        self.opacity_anim.finished.connect(self._on_dismiss_finished)
        self.opacity_anim.start()

    def _on_dismiss_finished(self) -> None:
        self.hide()
        self.deleteLater()


class QtToastManager:
    """Manages positioning and stacking of toast notifications on a host window."""

    _instance: Optional["QtToastManager"] = None

    def __init__(self, host_window: Optional[QWidget] = None):
        self.host_window = host_window
        self._active_toasts: List[LLToast] = []

    @classmethod
    def instance(cls, host_window: Optional[QWidget] = None) -> Optional["QtToastManager"]:
        if cls._instance is None and host_window is not None:
            cls._instance = QtToastManager(host_window)
        elif host_window is not None and cls._instance is not None:
            cls._instance.host_window = host_window
        return cls._instance

    @property
    def active_toasts(self) -> List[LLToast]:
        return list(self._active_toasts)

    def show_toast(
        self,
        title: str,
        message: str,
        tone: Tone = Tone.INFO,
        duration_ms: int = 4000,
    ) -> LLToast:
        """Alias for standard toast creation."""
        return self.show(message=message, title=title, tone=tone, duration_ms=duration_ms)

    def show(
        self,
        message: str,
        title: str = "",
        tone: Tone = Tone.INFO,
        duration_ms: int = 4000,
    ) -> LLToast:
        """Create, position, and display a new toast notification."""
        toast = LLToast(
            message=message,
            title=title,
            tone=tone,
            duration_ms=duration_ms,
            parent=self.host_window,
        )
        toast._manager = self
        self._active_toasts.append(toast)
        toast.destroyed.connect(lambda: self._on_toast_destroyed(toast))

        self._reposition_toasts()
        toast.show_animated()
        return toast

    def show_success(self, message: str, title: str = "Success") -> LLToast:
        return self.show(message, title=title, tone=Tone.SUCCESS)

    def show_error(self, message: str, title: str = "Error") -> LLToast:
        return self.show(message, title=title, tone=Tone.DANGER)

    def show_warning(self, message: str, title: str = "Warning") -> LLToast:
        return self.show(message, title=title, tone=Tone.WARNING)

    def show_info(self, message: str, title: str = "Notice") -> LLToast:
        return self.show(message, title=title, tone=Tone.INFO)

    def _on_toast_destroyed(self, toast: LLToast) -> None:
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)
        self._reposition_toasts()

    def _reposition_toasts(self) -> None:
        """Position toasts stacked in the top-right corner of the host window."""
        if not self.host_window:
            return
        margin_right = 24
        margin_top = 24
        spacing = 10

        host_rect = self.host_window.rect()
        current_y = margin_top

        for toast in self._active_toasts:
            if not toast.isVisible() and not toast.isHidden():
                continue
            toast_w = toast.width()
            x = host_rect.width() - toast_w - margin_right
            toast.move(x, current_y)
            current_y += toast.sizeHint().height() + spacing


# Backward compatibility alias
LLToastManager = QtToastManager
