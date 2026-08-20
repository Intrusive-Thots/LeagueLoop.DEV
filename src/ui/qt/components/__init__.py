"""
LeagueLoop Qt component library (UI/UX Master Plan §33).

The shared visual vocabulary every screen reuses. Components consume design
tokens from `ui.qt.theme` and own their own hover / pressed / disabled /
focus states, so screens never hand-roll QSS.

Implemented so far:
    LLStatus, Tone   §20  universal status readout
    LLChampionTile   §9    champion tile, full state set
    LLButton         §2.2 ranked-emphasis button
    LLIconButton     §33  icon-only control
    LLCard           §38  meaningful group surface
    LLSection        §39  light titled group
    LLSeparator      §39  subtle rule
    LLBadge          §62  compact state pill
    LLTimer          §13  semantic countdown
    LLDraftTimeline  §12  draft phase strip
    LLToggle         §33  on/off switch
    LLSettingRow     §7   name + state + explanation + control
    LLActivityFeed   §18  human-readable activity
    LLTextField      §33  labelled input with inline validation
    LLModal          §40  dialog surface with verb-labelled actions

Still to build (see the migration audit): LLTabs, LLSearch,
LLPriorityList, LLToast, LLTooltip, LLAvatar.
"""
from ui.qt.components.activity import (
    ActivityEntry,
    ActivityKind,
    LLActivityFeed,
    LLActivityRow,
)
from ui.qt.components.badge import LLBadge
from ui.qt.components.button import (
    ButtonSize,
    ButtonVariant,
    LLButton,
    LLIconButton,
)
from ui.qt.components.card import LLCard, LLSection, LLSeparator
from ui.qt.components.field import LLTextField
from ui.qt.components.modal import LLConfirmModal, LLModal
from ui.qt.components.champion_tile import (
    ChampionTileModel,
    LLChampionTile,
    TileSize,
)
from ui.qt.components.draft_timeline import LLDraftTimeline, StepState
from ui.qt.components.focus import install_focus_visible
from ui.qt.components.timer import LLTimer, TimerState
from ui.qt.components.setting_row import LLSettingRow
from ui.qt.components.status import LLStatus, Tone, tone_color, tone_glyph
from ui.qt.components.toast import LLToast, QtToastManager
from ui.qt.components.toggle import LLToggle

__all__ = [
    "install_focus_visible",
    "LLActivityFeed",
    "LLActivityRow",
    "ActivityEntry",
    "ActivityKind",
    "LLBadge",
    "LLButton",
    "LLIconButton",
    "ButtonVariant",
    "ButtonSize",
    "LLChampionTile",
    "ChampionTileModel",
    "TileSize",
    "LLTimer",
    "TimerState",
    "LLDraftTimeline",
    "StepState",
    "LLToggle",
    "LLSettingRow",
    "LLCard",
    "LLTextField",
    "LLModal",
    "LLConfirmModal",
    "LLSection",
    "LLSeparator",
    "LLStatus",
    "LLToast",
    "QtToastManager",
    "Tone",
    "tone_color",
    "tone_glyph",
]
