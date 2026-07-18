"""
PySide6 Card Container Primitives
─────────────────────────────────
Implements gold-bordered cards, sections, and collapsible details frames.
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtCore import Qt, Property, QPropertyAnimation
from ui.qt.theme import get_theme_color


class RiotCard(QFrame):
    """League-styled card frame with gold-tinted header, divider, and content area."""

    def __init__(self, parent=None, title=None, collapsible=False, start_collapsed=False):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        
        # Base Card Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(6)
        
        # Header setup
        self.header_widget = None
        self.collapsible = collapsible
        self.is_expanded = not start_collapsed

        if title or collapsible:
            self.header_widget = QWidget(self)
            self.header_layout = QHBoxLayout(self.header_widget)
            self.header_layout.setContentsMargins(0, 0, 0, 0)
            self.header_layout.setSpacing(4)

            # Chevron
            if collapsible:
                self.btn_toggle = QPushButton("▼" if self.is_expanded else "▶", self.header_widget)
                self.btn_toggle.setFixedSize(16, 16)
                self.btn_toggle.setCursor(Qt.PointingHandCursor)
                self.btn_toggle.setStyleSheet("""
                    QPushButton {
                        border: none;
                        color: #6C757D;
                        font-weight: bold;
                        background: transparent;
                    }
                    QPushButton:hover {
                        color: #F0E6D2;
                    }
                """)
                self.btn_toggle.clicked.connect(self.toggle)
                self.header_layout.addWidget(self.btn_toggle)

            # Title label
            self.lbl_title = QLabel(title or "SECTION", self.header_widget)
            self.lbl_title.setStyleSheet("font-weight: bold; color: #C8AA6E; font-size: 11px;")
            self.header_layout.addWidget(self.lbl_title)
            self.header_layout.addStretch()

            self.main_layout.addWidget(self.header_widget)

            # Divider line
            self.divider = QFrame(self)
            self.divider.setFixedHeight(1)
            self.divider.setStyleSheet("background-color: #1E2328; border: none;")
            self.main_layout.addWidget(self.divider)

        # Content frame
        self.content_frame = QFrame(self)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        self.content_layout.setSpacing(6)
        
        self.main_layout.addWidget(self.content_frame)

        if collapsible and start_collapsed:
            self.content_frame.setVisible(False)
            if title or collapsible:
                self.divider.setVisible(False)

    def toggle(self):
        """Toggle expanding/collapsing the content section."""
        self.is_expanded = not self.is_expanded
        self.content_frame.setVisible(self.is_expanded)
        if self.header_widget:
            self.btn_toggle.setText("▼" if self.is_expanded else "▶")
            self.divider.setVisible(self.is_expanded)


def make_card(parent, title=None, collapsible=False, start_collapsed=False, **kwargs):
    """Creates and returns the content frame inside a RiotCard."""
    card = RiotCard(parent, title=title, collapsible=collapsible, start_collapsed=start_collapsed)
    
    # If the parent has a layout, add the card to it
    if parent and parent.layout():
        parent.layout().addWidget(card)

    return card.content_frame
