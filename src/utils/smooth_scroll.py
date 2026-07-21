"""
Smooth Scroll Enhancement
─────────────────────────
Adds kinetic momentum-based smooth scrolling to PySide6 QScrollArea widgets.
"""
from PySide6.QtWidgets import QScrollArea, QScroller


def apply_smooth_scroll(scroll_area: QScrollArea):
    """
    Enhances a PySide6 QScrollArea with kinetic touch/gesture smooth scrolling.
    """
    try:
        QScroller.grabGesture(scroll_area.viewport(), QScroller.TouchGesture)
    except Exception:
        pass
