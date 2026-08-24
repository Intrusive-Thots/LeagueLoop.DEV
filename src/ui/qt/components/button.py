"""
LLButton / LLIconButton — the button primitives (UI/UX Master Plan §2.2, §33, §63).

§2.2 asks every screen to have exactly one obvious primary action, so the
variants are deliberately ranked: PRIMARY reads loudest, then SECONDARY,
then GHOST. DANGER is reserved for destructive actions (§40).

Every variant defines hover / pressed / disabled / focus states (§63).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton, QWidget

from ui.qt.theme.colors import (
    BORDER_ACCENT,
    BORDER_DEFAULT,
    BORDER_SUBTLE,
    COLOR_DANGER,
    COLOR_DANGER_SUBTLE,
    FOCUS_RING,
    FOCUS_RING_WIDTH,
    GOLD_DARK,
    GOLD_DISABLED,
    GOLD_LIGHT,
    GOLD_PRIMARY,
    SURFACE_PANEL,
    SURFACE_PANEL_HOVER,
    TEXT_DISABLED,
    TEXT_ON_ACCENT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.radii import RADIUS_SM
from ui.qt.theme.spacing import (
    CONTROL_HEIGHT_LG,
    CONTROL_HEIGHT_MD,
    CONTROL_HEIGHT_SM,
    ICON_MD,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from ui.qt.theme.typography import FONT_FAMILY, WEIGHT_BOLD, WEIGHT_MEDIUM
from ui.qt.components.focus import install_focus_visible


class ButtonVariant(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DANGER = "danger"
    GHOST = "ghost"


class ButtonSize(Enum):
    SM = "sm"
    MD = "md"
    LG = "lg"


_SIZE_SPEC = {
    ButtonSize.SM: (CONTROL_HEIGHT_SM, SPACE_MD, 12),
    ButtonSize.MD: (CONTROL_HEIGHT_MD, SPACE_LG, 13),
    ButtonSize.LG: (CONTROL_HEIGHT_LG, SPACE_LG + SPACE_SM, 14),
}


class LLButton(QPushButton):
    """A token-styled button with ranked emphasis variants."""

    def __init__(
        self,
        text: str = "",
        variant: ButtonVariant = ButtonVariant.SECONDARY,
        size: ButtonSize = ButtonSize.MD,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self._variant = variant
        self._size = size
        self.setCursor(Qt.PointingHandCursor)
        install_focus_visible(self)
        self._apply_style()

    def set_variant(self, variant: ButtonVariant) -> None:
        self._variant = variant
        self._apply_style()

    @property
    def variant(self) -> ButtonVariant:
        return self._variant

    def _apply_style(self) -> None:
        height, pad_x, font_size = _SIZE_SPEC[self._size]
        self.setMinimumHeight(height)

        if self._variant is ButtonVariant.PRIMARY:
            bg, fg, border = GOLD_DARK, GOLD_LIGHT, GOLD_PRIMARY
            hover_bg, hover_fg = GOLD_PRIMARY, TEXT_ON_ACCENT
            pressed_bg = GOLD_DARK
            weight = WEIGHT_BOLD
        elif self._variant is ButtonVariant.DANGER:
            bg, fg, border = "transparent", COLOR_DANGER, COLOR_DANGER
            hover_bg, hover_fg = COLOR_DANGER_SUBTLE, COLOR_DANGER
            pressed_bg = COLOR_DANGER_SUBTLE
            weight = WEIGHT_MEDIUM
        elif self._variant is ButtonVariant.GHOST:
            bg, fg, border = "transparent", TEXT_SECONDARY, "transparent"
            hover_bg, hover_fg = SURFACE_PANEL_HOVER, TEXT_PRIMARY
            pressed_bg = SURFACE_PANEL
            weight = WEIGHT_MEDIUM
        else:  # SECONDARY
            bg, fg, border = SURFACE_PANEL, GOLD_LIGHT, BORDER_ACCENT
            hover_bg, hover_fg = SURFACE_PANEL_HOVER, TEXT_PRIMARY
            pressed_bg = GOLD_DARK
            weight = WEIGHT_MEDIUM

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {RADIUS_SM}px;
                padding: 0px {pad_x}px;
                font-family: {FONT_FAMILY};
                font-size: {font_size}px;
                font-weight: {weight};
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                color: {hover_fg};
            }}
            QPushButton:pressed {{
                background-color: {pressed_bg};
            }}
            QPushButton:disabled {{
                background-color: transparent;
                color: {TEXT_DISABLED};
                border: 1px solid {BORDER_SUBTLE};
            }}
            QPushButton[keyboardFocus="true"] {{
                border: {FOCUS_RING_WIDTH}px solid {FOCUS_RING};
                outline: none;
            }}
        """)

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        if self._size == ButtonSize.SM:
            return QSize(min(96, hint.width()), hint.height())
        return hint


class LLIconButton(QPushButton):
    """
    A square, icon-only button (window controls, toolbar affordances).

    Sits in a fixed-size container so swapping the glyph never shifts
    surrounding layout (§36).
    """

    def __init__(
        self,
        glyph: str = "",
        tooltip: str = "",
        size: int = CONTROL_HEIGHT_MD,
        danger_hover: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(glyph, parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        install_focus_visible(self)
        if tooltip:
            self.setToolTip(tooltip)
            self.setAccessibleName(tooltip)

        hover_bg = COLOR_DANGER if danger_hover else SURFACE_PANEL_HOVER
        hover_fg = "#FFFFFF" if danger_hover else TEXT_PRIMARY

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                border-radius: {RADIUS_SM}px;
                font-family: {FONT_FAMILY};
                font-size: {ICON_MD - 4}px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                color: {hover_fg};
            }}
            QPushButton:pressed {{
                background-color: {BORDER_DEFAULT};
            }}
            QPushButton:disabled {{
                color: {TEXT_DISABLED};
            }}
            QPushButton[keyboardFocus="true"] {{
                border: {FOCUS_RING_WIDTH}px solid {FOCUS_RING};
                outline: none;
            }}
        """)
