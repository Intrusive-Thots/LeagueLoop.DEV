"""
PySide6 Theme Tokens and QSS Generator for LeagueLoop.
Adheres to Riot Hextech design language and high-contrast dark theme principles.
"""
from __future__ import annotations

# Riot Hextech Palette Design Tokens
COLOR_BACKGROUND_DARK = "#010A13"
COLOR_BACKGROUND_PANEL = "#091428"
COLOR_BACKGROUND_CARD = "#0A1428"
COLOR_BACKGROUND_HOVER = "#1E282D"

COLOR_GOLD_PRIMARY = "#C8AA6E"
COLOR_GOLD_LIGHT = "#F0E6D2"
COLOR_GOLD_DARK = "#785A28"

COLOR_BLUE_ACCENT = "#0AC8B9"
COLOR_BLUE_LIGHT = "#005A82"

COLOR_TEXT_PRIMARY = "#F0E6D2"
COLOR_TEXT_SECONDARY = "#A09B8C"
COLOR_TEXT_MUTED = "#5C5B57"

COLOR_BORDER = "#1E282D"
COLOR_BORDER_ACCENT = "#785A28"
COLOR_BORDER_GOLD = "#C8AA6E"

COLOR_SUCCESS = "#0AC8B9"
COLOR_DANGER = "#E84057"
COLOR_WARNING = "#E0A92E"


def get_global_stylesheet() -> str:
    """Returns the core Qt Style Sheet (QSS) for LeagueLoop."""
    return f"""
    QWidget {{
        background-color: {COLOR_BACKGROUND_DARK};
        color: {COLOR_TEXT_PRIMARY};
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 13px;
        selection-background-color: {COLOR_GOLD_DARK};
        selection-color: {COLOR_GOLD_LIGHT};
    }}

    QFrame#panel {{
        background-color: {COLOR_BACKGROUND_PANEL};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
    }}

    QPushButton {{
        background-color: {COLOR_BACKGROUND_PANEL};
        color: {COLOR_GOLD_LIGHT};
        border: 1px solid {COLOR_BORDER_ACCENT};
        border-radius: 4px;
        padding: 6px 14px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        background-color: {COLOR_BACKGROUND_HOVER};
        border: 1px solid {COLOR_GOLD_PRIMARY};
        color: #FFFFFF;
    }}

    QPushButton:pressed {{
        background-color: {COLOR_GOLD_DARK};
        border: 1px solid {COLOR_GOLD_LIGHT};
    }}

    QPushButton#accent {{
        background-color: {COLOR_GOLD_DARK};
        color: #FFFFFF;
        border: 1px solid {COLOR_GOLD_PRIMARY};
    }}

    QPushButton#accent:hover {{
        background-color: {COLOR_GOLD_PRIMARY};
        color: {COLOR_BACKGROUND_DARK};
    }}

    QLineEdit, QPlainTextEdit, QTextEdit {{
        background-color: {COLOR_BACKGROUND_PANEL};
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 6px;
        color: {COLOR_TEXT_PRIMARY};
    }}

    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border: 1px solid {COLOR_GOLD_PRIMARY};
    }}

    QScrollBar:vertical {{
        background: {COLOR_BACKGROUND_DARK};
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {COLOR_BACKGROUND_HOVER};
        min-height: 20px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {COLOR_GOLD_DARK};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
