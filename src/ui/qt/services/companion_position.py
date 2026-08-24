"""
Where the companion panel goes, given where the League Client is.

Pure geometry. No Qt widgets, no Win32, no global state — it takes rectangles
and returns a point, which is what makes it testable without a desktop and
means the same rules apply on every monitor.

The rule
--------
Sit beside the client, on the preferred side, separated by a gap::

    ┌──────────────────────────┐ gap ┌────────┐
    │                          │ <-> │ League │
    │      League Client       │     │  Loop  │
    │                          │     │        │
    └──────────────────────────┘     └────────┘

If the preferred side has no room, use the other side. If neither does — the
client is maximised, or the screen is small — overlap the client's edge
rather than going off-screen, because a panel you cannot see is worse than
one that covers 300px of the client.

Screen boundaries and multiple monitors
---------------------------------------
Placement is always resolved against the screen that actually contains the
client, not the primary one, and the result is clamped into that screen's
*available* geometry so it never lands under the taskbar. `screen_for_rect`
picks the screen by largest intersection, which is the behaviour you want
while a window is being dragged between monitors.

Nothing here is expressed in absolute screen coordinates. `move(1200, 50)`
was exactly the bug this replaces.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

Rect = Tuple[int, int, int, int]  # x, y, width, height

#: Which side of the client the panel prefers.
SIDE_RIGHT = "right"
SIDE_LEFT = "left"

#: Space between the client's edge and the panel.
DEFAULT_GAP = 8


@dataclass(frozen=True)
class Placement:
    """Where to put the panel, and why."""

    x: int
    y: int
    side: str
    #: True when the panel had to overlap the client to stay on screen.
    overlapping: bool = False
    #: Short explanation, for the log and for tests to assert against.
    reason: str = ""


def _right(rect: Rect) -> int:
    return rect[0] + rect[2]


def _bottom(rect: Rect) -> int:
    return rect[1] + rect[3]


def _intersection_area(a: Rect, b: Rect) -> int:
    overlap_w = min(_right(a), _right(b)) - max(a[0], b[0])
    overlap_h = min(_bottom(a), _bottom(b)) - max(a[1], b[1])
    if overlap_w <= 0 or overlap_h <= 0:
        return 0
    return overlap_w * overlap_h


def screen_for_rect(rect: Rect, screens: Sequence[Rect]) -> Optional[Rect]:
    """The screen a window is on: the one it overlaps most.

    Largest-intersection rather than "contains the top-left corner", because
    a window being dragged between monitors is briefly on both, and the
    corner rule makes the panel jump to the new screen well before the client
    has actually moved there.
    """
    if not screens:
        return None
    best, best_area = None, 0
    for screen in screens:
        area = _intersection_area(rect, screen)
        if area > best_area:
            best, best_area = screen, area
    # No overlap at all (the client is off-screen): fall back to the first
    # screen rather than returning nothing and leaving the caller stuck.
    return best if best is not None else screens[0]


def clamp_to_screen(x: int, y: int, size: Tuple[int, int], screen: Rect) -> Tuple[int, int]:
    """Keep a panel of `size` fully inside `screen` where possible.

    When the panel is taller than the screen, the top edge wins — a control
    you can reach beats a bottom edge you cannot.
    """
    width, height = size
    max_x = _right(screen) - width
    max_y = _bottom(screen) - height
    x = min(max(x, screen[0]), max(max_x, screen[0]))
    y = min(max(y, screen[1]), max(max_y, screen[1]))
    return int(x), int(y)


def place_companion(
    client_rect: Rect,
    panel_size: Tuple[int, int],
    screens: Sequence[Rect],
    gap: int = DEFAULT_GAP,
    preferred_side: str = SIDE_RIGHT,
) -> Placement:
    """Work out where the companion panel should sit.

    `screens` are *available* geometries (taskbar already excluded), in the
    same coordinate space as `client_rect`.
    """
    panel_w, panel_h = panel_size
    screen = screen_for_rect(client_rect, screens) or (
        client_rect[0], client_rect[1], client_rect[2], client_rect[3]
    )

    right_x = _right(client_rect) + gap
    left_x = client_rect[0] - gap - panel_w

    fits_right = right_x + panel_w <= _right(screen)
    fits_left = left_x >= screen[0]

    order = (
        [(SIDE_RIGHT, right_x, fits_right), (SIDE_LEFT, left_x, fits_left)]
        if preferred_side == SIDE_RIGHT
        else [(SIDE_LEFT, left_x, fits_left), (SIDE_RIGHT, right_x, fits_right)]
    )

    # Top-aligned with the client: the panel's own content starts at the top,
    # so aligning tops keeps the two reading as one unit.
    y = client_rect[1]

    for side, x, fits in order:
        if fits:
            cx, cy = clamp_to_screen(x, y, panel_size, screen)
            return Placement(
                x=cx, y=cy, side=side,
                reason=f"beside the client on the {side}",
            )

    # Neither side fits — maximised client, or a panel wider than the margin.
    # Sit against the inside of the preferred edge, overlapping the client.
    if preferred_side == SIDE_RIGHT:
        x = _right(screen) - panel_w
        side = SIDE_RIGHT
    else:
        x = screen[0]
        side = SIDE_LEFT
    cx, cy = clamp_to_screen(x, y, panel_size, screen)
    return Placement(
        x=cx, y=cy, side=side, overlapping=True,
        reason="no room beside the client, so overlapping its edge",
    )


def qt_available_screens(app=None) -> List[Rect]:
    """Every screen's available geometry, from Qt.

    Kept here so callers do not import QtGui just to ask. Returns [] when Qt
    is not up, which the caller must treat as "unknown", not "no screens".
    """
    try:
        from PySide6.QtWidgets import QApplication

        instance = app or QApplication.instance()
        if instance is None:
            return []
        rects = []
        for screen in instance.screens():
            geometry = screen.availableGeometry()
            rects.append((
                geometry.x(), geometry.y(), geometry.width(), geometry.height(),
            ))
        return rects
    except Exception:
        return []
