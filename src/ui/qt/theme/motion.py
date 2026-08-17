"""
Animation / Motion Tokens for LeagueLoop UI (UI/UX Master Plan §29).

Targets from the plan:
    hover            100-150 ms
    panel transition 150-220 ms
    modal            180-250 ms

Motion must reinforce state and preserve spatial relationships, and must
never delay interaction. `DURATION_INSTANT` exists so that reduced-motion
mode (§30) can be honoured by swapping durations rather than branching
every call site.
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve

# --- Durations (milliseconds) ---
DURATION_INSTANT = 0
DURATION_HOVER = 120
DURATION_PANEL = 180
DURATION_MODAL = 220
DURATION_TOAST_IN = 160
DURATION_TOAST_OUT = 140

# --- Easing ---
EASE_STANDARD = QEasingCurve.Type.OutCubic
EASE_DECELERATE = QEasingCurve.Type.OutQuint
EASE_ACCELERATE = QEasingCurve.Type.InCubic

# --- Toast timing (§19: 2-4 seconds) ---
TOAST_DURATION_SHORT_MS = 2000
TOAST_DURATION_DEFAULT_MS = 3000
TOAST_DURATION_LONG_MS = 4000

# Reduced-motion switch (§30). Flip via `set_reduced_motion(True)` and read
# through `duration()` so a single setting disables motion app-wide.
_reduced_motion = False


def set_reduced_motion(enabled: bool) -> None:
    """Enable/disable reduced motion globally (accessibility, §30)."""
    global _reduced_motion
    _reduced_motion = bool(enabled)


def reduced_motion() -> bool:
    return _reduced_motion


def duration(ms: int) -> int:
    """Return the effective duration, honouring reduced-motion preference."""
    return DURATION_INSTANT if _reduced_motion else ms


__all__ = [
    "DURATION_INSTANT",
    "DURATION_HOVER",
    "DURATION_PANEL",
    "DURATION_MODAL",
    "DURATION_TOAST_IN",
    "DURATION_TOAST_OUT",
    "EASE_STANDARD",
    "EASE_DECELERATE",
    "EASE_ACCELERATE",
    "TOAST_DURATION_SHORT_MS",
    "TOAST_DURATION_DEFAULT_MS",
    "TOAST_DURATION_LONG_MS",
    "set_reduced_motion",
    "reduced_motion",
    "duration",
]
