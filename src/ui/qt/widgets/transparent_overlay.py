"""
Resizable transparent overlay QWidget (Windows-friendly).

- Frameless + translucent background
- Edge/corner resize when not click-through
- Optional true click-through (Win32 WS_EX_TRANSPARENT) so mouse events pass to windows below
"""

from __future__ import annotations

import sys
from enum import IntEnum, auto
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QApplication, QWidget
from utils.logger import Logger

# Win32 extended styles (click-through)
_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000


class _Edge(IntEnum):
    NONE = 0
    LEFT = auto()
    RIGHT = auto()
    TOP = auto()
    BOTTOM = auto()
    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_RIGHT = auto()


_CURSOR_FOR_EDGE = {
    _Edge.LEFT: Qt.CursorShape.SizeHorCursor,
    _Edge.RIGHT: Qt.CursorShape.SizeHorCursor,
    _Edge.TOP: Qt.CursorShape.SizeVerCursor,
    _Edge.BOTTOM: Qt.CursorShape.SizeVerCursor,
    _Edge.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    _Edge.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
    _Edge.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    _Edge.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
}


class TransparentOverlayWidget(QWidget):
    """
    Resizable, always-on-top, translucent QWidget.

    Parameters
    ----------
    click_through:
        When True on Windows, mouse input passes through the window to apps below.
        Resize / drag are disabled while click-through is on (toggle off to reshape).
    show_border:
        Draw a faint border so the overlay is visible while empty.
    """

    click_through_changed = Signal(bool)
    geometry_committed = Signal(QRect)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        click_through: bool = False,
        show_border: bool = True,
        border_color: QColor | None = None,
        fill_color: QColor | None = None,
        resize_margin: int = 8,
        min_size: QSize | None = None,
        stay_on_top: bool = True,
    ) -> None:
        super().__init__(parent)

        self._click_through = False
        self._show_border = show_border
        self._border_color = border_color or QColor(120, 200, 255, 140)
        self._fill_color = fill_color or QColor(10, 14, 20, 40)
        self._resize_margin = max(4, int(resize_margin))
        self._min_size = min_size or QSize(120, 80)

        self._drag_origin: Optional[QPoint] = None
        self._geom_origin: Optional[QRect] = None
        self._active_edge = _Edge.NONE
        self._unlocked = True  # when False, ignore drag/resize even if not click-through

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if stay_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setMinimumSize(self._min_size)
        self.resize(360, 220)

        # Apply after native window exists
        self.set_click_through(click_through)

    # ------------------------------------------------------------------ API
    @property
    def click_through(self) -> bool:
        return self._click_through

    def set_click_through(self, enabled: bool) -> None:
        """Enable/disable true click-through (Win32). No-op style elsewhere."""
        enabled = bool(enabled)
        if self._click_through == enabled and self.isVisible():
            # still re-apply styles after show
            pass
        self._click_through = enabled
        self._apply_win32_exstyle()
        if enabled:
            self.unsetCursor()
            self._active_edge = _Edge.NONE
        self.click_through_changed.emit(enabled)
        self.update()

    def set_interaction_unlocked(self, unlocked: bool) -> None:
        """When locked (and not click-through), window ignores drag/resize."""
        self._unlocked = bool(unlocked)
        if not self._unlocked:
            self.unsetCursor()
            self._active_edge = _Edge.NONE

    def set_overlay_colors(
        self,
        *,
        fill: QColor | None = None,
        border: QColor | None = None,
    ) -> None:
        if fill is not None:
            self._fill_color = QColor(fill)
        if border is not None:
            self._border_color = QColor(border)
        self.update()

    # ------------------------------------------------------------- Win32
    def _hwnd(self) -> int:
        return int(self.winId())

    def _apply_win32_exstyle(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = self._hwnd()
            if not hwnd:
                return

            get_long = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
            set_long = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW

            ex = int(get_long(hwnd, _GWL_EXSTYLE))
            ex |= _WS_EX_LAYERED | _WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE
            if self._click_through:
                ex |= _WS_EX_TRANSPARENT
            else:
                ex &= ~_WS_EX_TRANSPARENT
            set_long(hwnd, _GWL_EXSTYLE, ex)
        except Exception as exc:
            # Overlay still works without click-through
            Logger.debug("TransparentOverlay", "_apply_win32_exstyle suppressed an error", exc=exc)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # winId is valid after show
        self._apply_win32_exstyle()

    # ---------------------------------------------------------- painting
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._fill_color)
        painter.drawRoundedRect(rect, 10, 10)

        if self._show_border:
            pen = QPen(self._border_color)
            pen.setWidth(1)
            # Dashed border when click-through so it's clear the overlay is "pass-through"
            if self._click_through:
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 10, 10)

        painter.end()

    # ----------------------------------------------------- hit / resize
    def _edge_at(self, pos: QPoint) -> _Edge:
        if self._click_through or not self._unlocked:
            return _Edge.NONE

        m = self._resize_margin
        r = self.rect()
        x, y = pos.x(), pos.y()
        left = x <= m
        right = x >= r.width() - m
        top = y <= m
        bottom = y >= r.height() - m

        if top and left:
            return _Edge.TOP_LEFT
        if top and right:
            return _Edge.TOP_RIGHT
        if bottom and left:
            return _Edge.BOTTOM_LEFT
        if bottom and right:
            return _Edge.BOTTOM_RIGHT
        if left:
            return _Edge.LEFT
        if right:
            return _Edge.RIGHT
        if top:
            return _Edge.TOP
        if bottom:
            return _Edge.BOTTOM
        return _Edge.NONE

    def _update_cursor(self, edge: _Edge) -> None:
        if edge == _Edge.NONE:
            self.unsetCursor()
        else:
            self.setCursor(_CURSOR_FOR_EDGE[edge])

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._click_through or not self._unlocked:
            return super().mousePressEvent(event)

        pos = event.position().toPoint()
        self._active_edge = self._edge_at(pos)
        self._drag_origin = event.globalPosition().toPoint()
        self._geom_origin = QRect(self.geometry())
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._click_through or not self._unlocked:
            return super().mouseMoveEvent(event)

        if self._drag_origin is None or self._geom_origin is None:
            self._update_cursor(self._edge_at(event.position().toPoint()))
            return super().mouseMoveEvent(event)

        delta = event.globalPosition().toPoint() - self._drag_origin
        g = QRect(self._geom_origin)
        edge = self._active_edge
        min_w, min_h = self._min_size.width(), self._min_size.height()

        if edge == _Edge.NONE:
            # Move whole window
            g.translate(delta)
        else:
            if edge in (_Edge.LEFT, _Edge.TOP_LEFT, _Edge.BOTTOM_LEFT):
                new_left = g.left() + delta.x()
                if g.right() - new_left + 1 >= min_w:
                    g.setLeft(new_left)
            if edge in (_Edge.RIGHT, _Edge.TOP_RIGHT, _Edge.BOTTOM_RIGHT):
                new_right = g.right() + delta.x()
                if new_right - g.left() + 1 >= min_w:
                    g.setRight(new_right)
            if edge in (_Edge.TOP, _Edge.TOP_LEFT, _Edge.TOP_RIGHT):
                new_top = g.top() + delta.y()
                if g.bottom() - new_top + 1 >= min_h:
                    g.setTop(new_top)
            if edge in (_Edge.BOTTOM, _Edge.BOTTOM_LEFT, _Edge.BOTTOM_RIGHT):
                new_bottom = g.bottom() + delta.y()
                if new_bottom - g.top() + 1 >= min_h:
                    g.setBottom(new_bottom)

        # Keep on virtual desktop somewhat
        screen = QGuiApplication.screenAt(g.center()) or QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            if g.right() < avail.left() + 40:
                g.moveRight(avail.left() + 40)
            if g.left() > avail.right() - 40:
                g.moveLeft(avail.right() - 40)
            if g.bottom() < avail.top() + 40:
                g.moveBottom(avail.top() + 40)
            if g.top() > avail.bottom() - 40:
                g.moveTop(avail.bottom() - 40)

        self.setGeometry(g)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            self._drag_origin = None
            self._geom_origin = None
            self._active_edge = _Edge.NONE
            self.geometry_committed.emit(self.geometry())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Double-click toggles click-through for quick lock/unlock of the overlay
        if event.button() == Qt.MouseButton.LeftButton and self._unlocked:
            self.set_click_through(not self._click_through)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


def _demo() -> int:
    """Manual smoke: drag to move, edges to resize, double-click to toggle click-through."""
    app = QApplication(sys.argv)
    w = TransparentOverlayWidget(click_through=False, show_border=True)
    w.setWindowTitle("LeagueLoop Transparent Overlay")
    w.show()

    # Center on primary screen
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        w.move(geo.center() - w.rect().center())

    print(
        "TransparentOverlayWidget demo\n"
        "  drag interior  = move\n"
        "  drag edges     = resize\n"
        "  double-click   = toggle click-through\n"
        "  Esc / close    = quit"
    )
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(_demo())
