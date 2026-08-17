"""
Spacing, Layout and Control-Size Tokens for LeagueLoop UI
(UI/UX Master Plan §34).

Spacing primitives follow the plan exactly: 4, 8, 12, 16, 24, 32.
Control heights and icon sizes live here too so components never invent
their own dimensions (§36: icons live in fixed-size containers).
"""
from __future__ import annotations

# --- Spacing primitives (§34) ---
SPACE_XXS = 2
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_XXL = 32

# --- Fixed layout regions (§3) ---
# Header is the single persistent context band: brand + state + window controls.
HEADER_HEIGHT = 52
TITLEBAR_HEIGHT = 32          # retained for the standalone Orb / overlay chrome
SIDEBAR_WIDTH = 200
SIDEBAR_WIDTH_COMPACT = 64
FOOTER_HEIGHT = 30
CONTENT_MARGIN = SPACE_XL

# --- Control heights (§34) ---
CONTROL_HEIGHT_SM = 26
CONTROL_HEIGHT_MD = 32
CONTROL_HEIGHT_LG = 40
ROW_HEIGHT = 40
NAV_ITEM_HEIGHT = 40

# --- Icon sizes (§36) ---
ICON_XS = 12
ICON_SM = 14
ICON_MD = 18
ICON_LG = 24
ICON_XL = 32

# --- Champion tile standard sizes (§65) ---
CHAMPION_TILE_SM = (64, 84)
CHAMPION_TILE_MD = (80, 104)
CHAMPION_TILE_LG = (112, 144)
CHAMPION_TILE_SIZE = 64       # legacy alias

# --- Responsive width breakpoints (§32) ---
BREAKPOINT_COMPACT = 320
BREAKPOINT_STANDARD = 420
BREAKPOINT_WIDE = 600

__all__ = [
    "SPACE_XXS", "SPACE_XS", "SPACE_SM", "SPACE_MD", "SPACE_LG", "SPACE_XL", "SPACE_XXL",
    "HEADER_HEIGHT", "TITLEBAR_HEIGHT", "SIDEBAR_WIDTH", "SIDEBAR_WIDTH_COMPACT",
    "FOOTER_HEIGHT", "CONTENT_MARGIN",
    "CONTROL_HEIGHT_SM", "CONTROL_HEIGHT_MD", "CONTROL_HEIGHT_LG", "ROW_HEIGHT", "NAV_ITEM_HEIGHT",
    "ICON_XS", "ICON_SM", "ICON_MD", "ICON_LG", "ICON_XL",
    "CHAMPION_TILE_SM", "CHAMPION_TILE_MD", "CHAMPION_TILE_LG", "CHAMPION_TILE_SIZE",
    "BREAKPOINT_COMPACT", "BREAKPOINT_STANDARD", "BREAKPOINT_WIDE",
]
