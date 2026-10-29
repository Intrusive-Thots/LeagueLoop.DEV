"""Champ-select phase clock, corrected for how the LCU actually reports it.

`timer.adjustedTimeLeftInPhase` is not a live countdown. It is the time left
*as of* `timer.internalNowInEpochMs`, and the client only refreshes the
session when something in the draft changes. Captured live from an ARAM:
Mayhem draft (tests/fixtures/lcu/champ_select_aram_mayhem_stale_*.json), two
reads nine seconds apart both said 19 793 ms left. Reading the field as-is
froze the countdown and made "act with <2 s left" logic believe it still had
plenty of time while the phase ran out.
"""
from __future__ import annotations

import time
from typing import Any, Mapping, Optional

#: Older than this and the stamp is not trustworthy (clock jump, bad data).
_MAX_PLAUSIBLE_AGE_MS = 600_000.0


def phase_time_left_ms(
    timer: Optional[Mapping[str, Any]],
    now_ms: Optional[float] = None,
    default: float = 0.0,
) -> float:
    """Milliseconds left in the current draft phase, aged to `now_ms`.

    Falls back to `default` when the timer has no usable value. The snapshot
    age is only subtracted when it is plausible (0..10 minutes; the stamp
    comes from the client on the same machine), so a skewed or missing
    `internalNowInEpochMs` degrades to the raw value instead of zeroing it.
    """
    if not isinstance(timer, Mapping):
        return float(default)
    if timer.get("isInfinite"):
        return float(default)
    left = timer.get("adjustedTimeLeftInPhase")
    if not isinstance(left, (int, float)) or isinstance(left, bool):
        left = timer.get("timeLeftInPhase")
    if not isinstance(left, (int, float)) or isinstance(left, bool):
        return float(default)
    left = float(left)

    stamp = timer.get("internalNowInEpochMs")
    if isinstance(stamp, (int, float)) and not isinstance(stamp, bool) and stamp > 0:
        if now_ms is None:
            now_ms = time.time() * 1000.0
        age = float(now_ms) - float(stamp)
        if 0.0 < age <= _MAX_PLAUSIBLE_AGE_MS:
            left -= age
    return max(0.0, left)
