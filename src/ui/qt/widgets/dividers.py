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


def make_divider(parent):
    """Create a horizontal divider."""
    return RiotDivider(parent)
