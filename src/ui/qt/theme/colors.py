"""
Color Tokens for LeagueLoop UI (UI/UX Master Plan §61, §62).

Palette rules from the plan:
  §61 — one configurable accent (primary/hover/active/subtle/disabled), the
        surrounding palette stays neutral.
  §62 — semantic colors carry meaning (success/warning/danger/info/neutral),
        but color is NEVER the sole meaning carrier: components pair every
        semantic color with a glyph and a text label.
"""
from __future__ import annotations

# --- Surfaces (neutral, layered rather than boxed — §39) ---
SURFACE_APP_BACKGROUND = "#010A13"
SURFACE_PANEL = "#091428"
SURFACE_PANEL_ELEVATED = "#0A1428"
SURFACE_PANEL_HOVER = "#1E282D"
SURFACE_PANEL_ACTIVE = "#1E2328"
SURFACE_OVERLAY = "rgba(1, 10, 19, 0.85)"
SURFACE_SUNKEN = "#00060C"

# --- Accent: Hextech gold (§61) ---
GOLD_PRIMARY = "#C8AA6E"
GOLD_LIGHT = "#F0E6D2"
GOLD_DARK = "#785A28"
GOLD_BORDER = "#C8AA6E"
GOLD_SUBTLE = "rgba(200, 170, 110, 0.14)"
GOLD_DISABLED = "#5A4E37"

# --- Secondary accent: magic blue ---
BLUE_ACCENT = "#0AC8B9"
BLUE_DARK = "#005A82"
BLUE_HOVER = "#0397AB"

# --- Text ---
TEXT_PRIMARY = "#F0E6D2"
TEXT_SECONDARY = "#A09B8C"
TEXT_MUTED = "#5C5B57"
TEXT_DISABLED = "#3C3C41"
TEXT_ACCENT = "#0AC8B9"
TEXT_ON_ACCENT = "#010A13"

# --- Borders ---
BORDER_DEFAULT = "#1E282D"
BORDER_ACCENT = "#785A28"
BORDER_ACTIVE = "#C8AA6E"
BORDER_SUBTLE = "#101A22"

# --- Semantic / feedback (§62) ---
COLOR_SUCCESS = "#0AC8B9"
COLOR_DANGER = "#E84057"
COLOR_WARNING = "#E0A92E"
COLOR_INFO = "#3FA9F5"
COLOR_NEUTRAL = "#A09B8C"

# Low-emphasis semantic fills for status pills / badge backgrounds
COLOR_SUCCESS_SUBTLE = "rgba(10, 200, 185, 0.14)"
COLOR_DANGER_SUBTLE = "rgba(232, 64, 87, 0.14)"
COLOR_WARNING_SUBTLE = "rgba(224, 169, 46, 0.14)"
COLOR_INFO_SUBTLE = "rgba(63, 169, 245, 0.14)"
COLOR_NEUTRAL_SUBTLE = "rgba(160, 155, 140, 0.12)"

# --- Focus (§30, §63: focus must be clearly visible for keyboard nav) ---
FOCUS_RING = "#3FA9F5"
FOCUS_RING_WIDTH = 2

__all__ = [
    "SURFACE_APP_BACKGROUND", "SURFACE_PANEL", "SURFACE_PANEL_ELEVATED",
    "SURFACE_PANEL_HOVER", "SURFACE_PANEL_ACTIVE", "SURFACE_OVERLAY", "SURFACE_SUNKEN",
    "GOLD_PRIMARY", "GOLD_LIGHT", "GOLD_DARK", "GOLD_BORDER", "GOLD_SUBTLE", "GOLD_DISABLED",
    "BLUE_ACCENT", "BLUE_DARK", "BLUE_HOVER",
    "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED", "TEXT_DISABLED", "TEXT_ACCENT", "TEXT_ON_ACCENT",
    "BORDER_DEFAULT", "BORDER_ACCENT", "BORDER_ACTIVE", "BORDER_SUBTLE",
    "COLOR_SUCCESS", "COLOR_DANGER", "COLOR_WARNING", "COLOR_INFO", "COLOR_NEUTRAL",
    "COLOR_SUCCESS_SUBTLE", "COLOR_DANGER_SUBTLE", "COLOR_WARNING_SUBTLE",
    "COLOR_INFO_SUBTLE", "COLOR_NEUTRAL_SUBTLE",
    "FOCUS_RING", "FOCUS_RING_WIDTH",
]
