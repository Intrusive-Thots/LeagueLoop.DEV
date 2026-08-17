"""
Riot Design System Theme package for PySide6.
"""
from __future__ import annotations

from ui.qt.theme.colors import *
from ui.qt.theme.spacing import *
from ui.qt.theme.radii import *

COLOR_BACKGROUND_DARK = SURFACE_APP_BACKGROUND
COLOR_BACKGROUND_PANEL = SURFACE_PANEL
COLOR_BACKGROUND_CARD = SURFACE_PANEL_ELEVATED
COLOR_BACKGROUND_HOVER = SURFACE_PANEL_HOVER

COLOR_GOLD_PRIMARY = GOLD_PRIMARY
COLOR_GOLD_LIGHT = GOLD_LIGHT
COLOR_GOLD_DARK = GOLD_DARK

COLOR_BLUE_ACCENT = BLUE_ACCENT
COLOR_BLUE_LIGHT = BLUE_DARK

COLOR_TEXT_PRIMARY = TEXT_PRIMARY
COLOR_TEXT_SECONDARY = TEXT_SECONDARY
COLOR_TEXT_MUTED = TEXT_MUTED

COLOR_BORDER = BORDER_DEFAULT
COLOR_BORDER_ACCENT = BORDER_ACCENT
COLOR_BORDER_GOLD = BORDER_ACTIVE


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
