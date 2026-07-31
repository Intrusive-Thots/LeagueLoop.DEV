"""
PySide6 Champion Hover Card
Popup tooltip overlay detailing stats, roles, and masteries.
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from ui.qt.theme import get_theme_color

class ChampionHoverCard(QFrame):
    """Popup tooltip overlay detailing stats, roles, and masteries."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hoverCard")
        self.setFixedSize(140, 110)

        border = get_theme_color("colors.accent.gold", "#C8AA6E")
        self.setStyleSheet(f"""
            QFrame#hoverCard {{
                background-color: #0A1428;
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        self.lbl_name = QLabel("Name", self)
        self.lbl_name.setStyleSheet("color: #F0E6D2; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl_name)

        self.lbl_roles = QLabel("Roles: --", self)
        self.lbl_roles.setStyleSheet("color: #8A95A5; font-size: 9px;")
        layout.addWidget(self.lbl_roles)

        self.lbl_mastery = QLabel("Mastery: --", self)
        self.lbl_mastery.setStyleSheet("color: #C8AA6E; font-size: 9px;")
        layout.addWidget(self.lbl_mastery)

        self.lbl_points = QLabel("Points: --", self)
        self.lbl_points.setStyleSheet("color: #8A95A5; font-size: 8px;")
        layout.addWidget(self.lbl_points)

        self.lbl_winrate = QLabel("Win Rate: --", self)
        self.lbl_winrate.setStyleSheet("color: #8A95A5; font-size: 9px; font-weight: bold;")
        layout.addWidget(self.lbl_winrate)

        self.setVisible(False)
