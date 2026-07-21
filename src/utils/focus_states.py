"""
Keyboard Focus State System
────────────────────────────
Adds visible focus indicators and scroll-into-view helpers for PySide6 widgets.
"""
from PySide6.QtWidgets import QWidget, QAbstractScrollArea
from ui.qt.theme import get_color


def apply_focus_ring(widget: QWidget, color: str = None, width: int = 2):
    """
    Applies an explicit focus border highlight to a PySide6 QWidget.
    """
    focus_color = color or get_color("accent_gold", "#C8AA6E")
    style = f"QWidget:focus {{ border: {width}px solid {focus_color}; }}"
    widget.setStyleSheet(widget.styleSheet() + f"\n{style}")


def scroll_to_widget(scroll_area: QAbstractScrollArea, widget: QWidget):
    """Scrolls a QScrollArea to bring a child widget into view."""
    try:
        scroll_area.ensureWidgetVisible(widget)
    except Exception:
        pass
