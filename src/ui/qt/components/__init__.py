"""
LeagueLoop Qt component library (UI/UX Master Plan §33).

The shared visual vocabulary every screen reuses. Components consume design
tokens from `ui.qt.theme` and own their own hover / pressed / disabled /
focus states, so screens never hand-roll QSS.

Implemented so far:
    LLStatus, Tone   §20  universal status readout
    LLButton         §2.2 ranked-emphasis button
    LLIconButton     §33  icon-only control
    LLCard           §38  meaningful group surface
    LLSection        §39  light titled group
    LLSeparator      §39  subtle rule
    LLBadge          §62  compact state pill

Still to build (see the migration audit): LLToggle, LLTabs, LLSearch,
LLChampionTile, LLChampionGrid, LLPriorityList, LLToast, LLModal,
LLTooltip, LLAvatar, LLActivityRow.
"""
from ui.qt.components.badge import LLBadge
from ui.qt.components.button import (
    ButtonSize,
    ButtonVariant,
    LLButton,
    LLIconButton,
)
from ui.qt.components.card import LLCard, LLSection, LLSeparator
from ui.qt.components.focus import install_focus_visible
from ui.qt.components.status import LLStatus, Tone, tone_color, tone_glyph

__all__ = [
    "install_focus_visible",
    "LLBadge",
    "LLButton",
    "LLIconButton",
    "ButtonVariant",
    "ButtonSize",
    "LLCard",
    "LLSection",
    "LLSeparator",
    "LLStatus",
    "Tone",
    "tone_color",
    "tone_glyph",
]
