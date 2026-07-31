"""
PySide6 Card Container Primitives
─────────────────────────────────
Implements gold-bordered cards, sections, and collapsible details frames.
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtCore import Qt


class RiotCard(QFrame):
    """League-styled card frame with gold-tinted header, divider, and content area."""

    def __init__(self, parent=None, title=None, collapsible=False, start_collapsed=False):
        super().__init__(parent)
        self.setObjectName("cardFrame")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(10)

        self.header_widget = None
        self.collapsible = collapsible
        self.is_expanded = not start_collapsed

        if title or collapsible:
            self.header_widget = QWidget(self)
            self.header_layout = QHBoxLayout(self.header_widget)
            self.header_layout.setContentsMargins(0, 0, 0, 0)
            self.header_layout.setSpacing(6)

            if collapsible:
                self.btn_toggle = QPushButton("▼" if self.is_expanded else "▶", self.header_widget)
                self.btn_toggle.setFixedSize(18, 18)
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

            self.lbl_title = QLabel(title or "SECTION", self.header_widget)
            self.lbl_title.setStyleSheet("font-weight: bold; color: #C8AA6E; font-size: 11px; letter-spacing: 0.5px;")
            self.header_layout.addWidget(self.lbl_title)
            self.header_layout.addStretch()

            self.main_layout.addWidget(self.header_widget)

            self.divider = QFrame(self)
            self.divider.setFixedHeight(1)
            self.divider.setStyleSheet("background-color: #1A283C; border: none;")
            self.main_layout.addWidget(self.divider)

        self.content_frame = QFrame(self)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)

        self.main_layout.addWidget(self.content_frame)

        if collapsible and start_collapsed:
            self.content_frame.setVisible(False)
            if title or collapsible:
                self.divider.setVisible(False)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.content_frame.setVisible(self.is_expanded)
        if self.header_widget:
            self.btn_toggle.setText("▼" if self.is_expanded else "▶")
            self.divider.setVisible(self.is_expanded)


def make_card(parent=None, title=None, collapsible=False, start_collapsed=False):
    """Creates a RiotCard frame."""
    return RiotCard(parent, title=title, collapsible=collapsible, start_collapsed=start_collapsed)
