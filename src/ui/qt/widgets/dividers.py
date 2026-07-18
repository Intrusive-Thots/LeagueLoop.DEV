"""
PySide6 Dividers Primitives
───────────────────────────
Implements horizontal separators using QFrame.
"""
from PySide6.QtWidgets import QFrame


class RiotDivider(QFrame):
    """Horizontal divider line styled using QSS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet("""
            QFrame {
                background-color: #1E2328;
                border: none;
            }
        """)


def make_divider(parent, padx=0, pady=0, side="top"):
    """Create a horizontal divider matching the factory.py API."""
    divider = RiotDivider(parent)
    # Note: side and padding (padx/pady) are typically handled by layouts in Qt,
    # but we expose the divider object directly for insertion.
    return divider
