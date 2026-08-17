"""
LeagueLoop Design System — single source of truth for the PySide6 UI.

This package is the canonical token set for the new Qt surfaces
(UI/UX Master Plan §34). Widgets import tokens from here and must not
hardcode colors, sizes, radii, or font sizes.

    colors      §61, §62   surfaces, accent, semantic feedback
    spacing     §34        spacing scale, layout regions, control/icon sizes
    radii       §34        radius scale
    typography  §35        the type scale
    elevation   §34, §39   the 4-level elevation system
    motion      §29        durations, easing, reduced-motion switch

NOTE ON THE LEGACY TOKENS: `src/ui/theme/design_tokens.json` still backs the
CustomTkinter shell via `ui/theme/token_loader.py`. It is intentionally left
alone so the live app's appearance does not shift mid-migration. Once the Qt
shell replaces it (Master Plan §73 Stage 10), the JSON should be deleted and
this package remains the only token source.
"""
from __future__ import annotations

from ui.qt.theme.colors import *  # noqa: F401,F403
from ui.qt.theme.spacing import *  # noqa: F401,F403
from ui.qt.theme.radii import *  # noqa: F401,F403
from ui.qt.theme.typography import *  # noqa: F401,F403
from ui.qt.theme.elevation import *  # noqa: F401,F403
from ui.qt.theme.motion import *  # noqa: F401,F403

from ui.qt.theme.colors import (
    BORDER_ACCENT,
    BORDER_ACTIVE,
    BORDER_DEFAULT,
    BORDER_SUBTLE,
    BLUE_ACCENT,
    BLUE_DARK,
    FOCUS_RING,
    FOCUS_RING_WIDTH,
    GOLD_DARK,
    GOLD_DISABLED,
    GOLD_LIGHT,
    GOLD_PRIMARY,
    SURFACE_APP_BACKGROUND,
    SURFACE_PANEL,
    SURFACE_PANEL_ELEVATED,
    SURFACE_PANEL_HOVER,
    SURFACE_SUNKEN,
    TEXT_DISABLED,
    TEXT_MUTED,
    TEXT_ON_ACCENT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.radii import RADIUS_MD, RADIUS_SM
from ui.qt.theme.spacing import CONTROL_HEIGHT_MD, SPACE_SM, SPACE_XS
from ui.qt.theme.typography import FONT_FAMILY, WEIGHT_MEDIUM, WEIGHT_BOLD

# ---------------------------------------------------------------------------
# Backwards-compatible aliases.
#
# The first Qt widgets were written against COLOR_*-prefixed names. They are
# kept so existing imports keep working; new code should prefer the canonical
# token names above.
# ---------------------------------------------------------------------------
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
    """
    Base application stylesheet, composed entirely from tokens.

    Component-specific styling lives in the `ui.qt.components` widgets, not
    here — this covers app-wide defaults and the built-in Qt controls
    (inputs, scrollbars, checkboxes, tables) so every surface starts
    consistent and keyboard focus is always visible (§63).
    """
    return f"""
    /*
     * Inherited defaults only — deliberately NO background-color on the
     * universal selector. Setting one makes every child widget paint the app
     * background over its parent card, which reads as a stray dark rectangle
     * behind every label and checkbox. Containers opt in below instead.
     */
    QWidget {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY};
        font-size: 13px;
        selection-background-color: {GOLD_DARK};
        selection-color: {GOLD_LIGHT};
    }}

    QMainWindow, QDialog {{
        background-color: {SURFACE_APP_BACKGROUND};
    }}

    QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}

    /* Content widgets never paint their own background. */
    QLabel, QCheckBox, QRadioButton {{
        background: transparent;
    }}

    QFrame#panel {{
        background-color: {SURFACE_PANEL};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_MD}px;
    }}

    /* --- Buttons -------------------------------------------------------- */
    QPushButton {{
        background-color: {SURFACE_PANEL};
        color: {GOLD_LIGHT};
        border: 1px solid {BORDER_ACCENT};
        border-radius: {RADIUS_SM}px;
        padding: {SPACE_XS}px {SPACE_SM + SPACE_XS}px;
        min-height: {CONTROL_HEIGHT_MD - 2 * SPACE_XS}px;
        font-weight: {WEIGHT_MEDIUM};
    }}
    QPushButton:hover {{
        background-color: {SURFACE_PANEL_HOVER};
        border: 1px solid {GOLD_PRIMARY};
        color: {TEXT_PRIMARY};
    }}
    QPushButton:pressed {{
        background-color: {GOLD_DARK};
        border: 1px solid {GOLD_LIGHT};
    }}
    QPushButton:disabled {{
        background-color: {SURFACE_PANEL};
        color: {TEXT_DISABLED};
        border: 1px solid {BORDER_SUBTLE};
    }}
    /* Keyboard-only focus ring — see ui.qt.components.focus */
    QPushButton[keyboardFocus="true"] {{
        border: {FOCUS_RING_WIDTH}px solid {FOCUS_RING};
        outline: none;
    }}

    QPushButton#accent {{
        background-color: {GOLD_DARK};
        color: {GOLD_LIGHT};
        border: 1px solid {GOLD_PRIMARY};
        font-weight: {WEIGHT_BOLD};
    }}
    QPushButton#accent:hover {{
        background-color: {GOLD_PRIMARY};
        color: {TEXT_ON_ACCENT};
    }}
    QPushButton#accent:disabled {{
        background-color: {SURFACE_PANEL};
        color: {TEXT_DISABLED};
        border: 1px solid {GOLD_DISABLED};
    }}

    /* --- Inputs --------------------------------------------------------- */
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {SURFACE_SUNKEN};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM}px;
        padding: {SPACE_XS}px {SPACE_SM}px;
        min-height: {CONTROL_HEIGHT_MD - 2 * SPACE_XS}px;
        color: {TEXT_PRIMARY};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: {FOCUS_RING_WIDTH}px solid {FOCUS_RING};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        color: {TEXT_DISABLED};
        border: 1px solid {BORDER_SUBTLE};
    }}

    /* --- Checkboxes (§63: every state is defined) ------------------------ */
    QCheckBox {{
        spacing: {SPACE_SM}px;
        color: {TEXT_PRIMARY};
        padding: {SPACE_XS}px 0px;
    }}
    QCheckBox:disabled {{
        color: {TEXT_DISABLED};
    }}
    QCheckBox:focus {{
        outline: none;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: {RADIUS_SM}px;
        border: 1px solid {BORDER_ACCENT};
        background-color: {SURFACE_SUNKEN};
    }}
    QCheckBox::indicator:hover {{
        border: 1px solid {GOLD_PRIMARY};
    }}
    QCheckBox::indicator:checked {{
        background-color: {GOLD_PRIMARY};
        border: 1px solid {GOLD_PRIMARY};
    }}
    QCheckBox::indicator:disabled {{
        border: 1px solid {BORDER_SUBTLE};
        background-color: {SURFACE_PANEL};
    }}

    /* --- Scrollbars ----------------------------------------------------- */
    QScrollBar:vertical {{
        background: transparent;
        width: {SPACE_SM}px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {SURFACE_PANEL_HOVER};
        min-height: 24px;
        border-radius: {RADIUS_SM}px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {GOLD_DARK};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: {SPACE_SM}px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {SURFACE_PANEL_HOVER};
        min-width: 24px;
        border-radius: {RADIUS_SM}px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* --- Tables (Diagnostics) ------------------------------------------- */
    QTableWidget {{
        background-color: {SURFACE_PANEL};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_MD}px;
        gridline-color: {BORDER_SUBTLE};
        color: {TEXT_PRIMARY};
    }}
    QHeaderView::section {{
        background-color: {SURFACE_APP_BACKGROUND};
        color: {GOLD_PRIMARY};
        font-weight: {WEIGHT_BOLD};
        border: none;
        border-bottom: 1px solid {BORDER_DEFAULT};
        padding: {SPACE_SM}px {SPACE_XS}px;
    }}

    QToolTip {{
        background-color: {SURFACE_PANEL_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_ACCENT};
        border-radius: {RADIUS_SM}px;
        padding: {SPACE_XS}px {SPACE_SM}px;
    }}
    """
