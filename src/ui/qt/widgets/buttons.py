"""
PySide6 Buttons Primitives
─────────────────────────
Implements Riot-styled button equivalents using QSS and QPushButton.
"""
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt


class RiotButton(QPushButton):
    """Custom button emulating Riot's styles via QSS and objectNames."""

    def __init__(self, text, style="primary", parent=None, command=None, **kwargs):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)

        # Map style variant names to QSS objectNames
        if style == "primary":
            self.setObjectName("primaryBtn")
        elif style == "secondary":
            self.setObjectName("secondaryBtn")
        elif style == "danger":
            self.setObjectName("dangerBtn")
        elif style == "ghost":
            # Ghost buttons have no border, transparent background
            self.setObjectName("ghostBtn")
            self.setStyleSheet("""
                QPushButton#ghostBtn {
                    background-color: transparent;
                    border: none;
                    color: #F0E6D2;
                }
                QPushButton#ghostBtn:hover {
                    background-color: #1C2630;
                }
            """)
        else:
            self.setObjectName("primaryBtn")

        if command:
            self.clicked.connect(command)


def make_button(parent, text, style="primary", width=None, command=None, icon=None, **kw):
    """Factory wrapper for RiotButton matching the factory.py signature."""
    btn = RiotButton(text, style=style, parent=parent, command=command)
    if width:
        btn.setFixedWidth(width)
    if "height" in kw:
        btn.setFixedHeight(kw["height"])
    return btn
