"""
PySide6 Scrollable Area Primitives
─────────────────────────────────
Implements custom scroll areas matching Design Token specifications.
"""
from PySide6.QtWidgets import QScrollArea, QWidget, QVBoxLayout
from PySide6.QtCore import Qt


class ScrollableList(QScrollArea):
    """Custom scrollable area wrapper with integrated styling and layouts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Transparent background, no borders
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # Container widget for layout
        self.container = QWidget(self)
        self.container.setStyleSheet("background-color: transparent;")
        
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(4)
        self.container_layout.addStretch()  # Keep items packed at top

        self.setWidget(self.container)

    def add_widget(self, widget):
        """Helper to add a widget to the scrollable list container layout."""
        # Insert before the stretch at the end
        self.container_layout.insertWidget(self.container_layout.count() - 1, widget)
