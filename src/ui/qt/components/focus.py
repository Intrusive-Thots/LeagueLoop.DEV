"""
Focus-visible support (UI/UX Master Plan §30, §63).

§63 asks for a clearly visible focus indicator *for keyboard navigation*.
Qt's `:focus` pseudo-state does not distinguish how focus arrived, so
styling it directly puts a ring on every clicked button — which reads as a
stuck selection and adds visual noise.

This module mirrors the web's `:focus-visible`: it sets a `keyboardFocus`
dynamic property when focus arrives via Tab / Backtab / a shortcut, so
stylesheets can target `[keyboardFocus="true"]` and show the ring only when
it is actually useful.

    install_focus_visible(button)

    QPushButton[keyboardFocus="true"] { border: 2px solid <FOCUS_RING>; }
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget

#: Focus reasons that mean "the user is navigating with the keyboard".
_KEYBOARD_REASONS = (
    Qt.FocusReason.TabFocusReason,
    Qt.FocusReason.BacktabFocusReason,
    Qt.FocusReason.ShortcutFocusReason,
)


def _repolish(widget: QWidget) -> None:
    """Force a style re-evaluation after a dynamic property changes."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


class _FocusVisibleFilter(QObject):
    """Event filter that maintains the `keyboardFocus` property."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        etype = event.type()

        if etype == QEvent.Type.FocusIn:
            is_keyboard = event.reason() in _KEYBOARD_REASONS
            if obj.property("keyboardFocus") != is_keyboard:
                obj.setProperty("keyboardFocus", is_keyboard)
                if isinstance(obj, QWidget):
                    _repolish(obj)

        elif etype == QEvent.Type.FocusOut:
            if obj.property("keyboardFocus"):
                obj.setProperty("keyboardFocus", False)
                if isinstance(obj, QWidget):
                    _repolish(obj)

        return False  # never consume the event


def install_focus_visible(widget: QWidget) -> None:
    """Enable keyboard-only focus rings on `widget`."""
    widget.setProperty("keyboardFocus", False)
    # Parent the filter to the widget so its lifetime is managed automatically.
    widget.installEventFilter(_FocusVisibleFilter(widget))
