"""
One rule for how big a popup is allowed to be.

Every dialog in the app had picked its own answer, and each answer was wrong
in a different direction:

* `ban_list_dialog`  - `resize(780, 520)` regardless of what was in it, so an
                       empty ban list opened as a large window of nothing
* `hotkey_dialog`    - `setFixedSize(360, 200)`, which clips the moment the
                       text is longer or Windows scaling is above 100%
* `blacklist_dialog` - no size at all, so it opened at whatever Qt guessed
* `LLModal`          - a 420px minimum and no maximum, so one long sentence
                       could stretch it past the edge of the screen

The rule here is the obvious one nobody had written down: **size to content,
inside a minimum and a maximum, and never larger than the screen you are
opening on.** Content that still does not fit belongs in a scroll area — the
popup does not grow to swallow the desktop.

    from ui.qt.services.popup_size import size_to_content
    size_to_content(dialog, min_size=(420, 220), max_size=(900, 700))
"""
from __future__ import annotations

from typing import Optional, Tuple

Size = Tuple[int, int]

#: Never take more of the screen than this in either axis. A dialog covering
#: the whole display reads as the application breaking, not as a dialog.
SCREEN_FRACTION = 0.85


def _screen_size_for(widget) -> Optional[Size]:
    """The available size of the screen this popup will open on.

    Follows the parent window rather than the primary screen: on a two-monitor
    setup the dialog appears over its parent, so the primary screen's size is
    the wrong bound — and on a 4K secondary it is the wrong bound by a lot.
    """
    try:
        from PySide6.QtGui import QGuiApplication

        handle = None
        parent = widget.parentWidget() if hasattr(widget, "parentWidget") else None
        source = parent or widget
        if hasattr(source, "screen"):
            handle = source.screen()
        if handle is None:
            handle = QGuiApplication.primaryScreen()
        if handle is None:
            return None
        available = handle.availableGeometry()
        return (available.width(), available.height())
    except Exception:
        return None


def size_to_content(
    widget,
    min_size: Size = (420, 200),
    max_size: Optional[Size] = None,
    screen_fraction: float = SCREEN_FRACTION,
) -> Size:
    """Resize `widget` to what its layout actually needs, within bounds.

    Returns the size applied, so callers and tests can assert on it.
    """
    min_w, min_h = min_size
    widget.setMinimumSize(min_w, min_h)

    screen = _screen_size_for(widget)
    cap_w, cap_h = max_size if max_size else (1 << 20, 1 << 20)
    if screen:
        cap_w = min(cap_w, int(screen[0] * screen_fraction))
        cap_h = min(cap_h, int(screen[1] * screen_fraction))
    # A maximum below the minimum is not a maximum, it is a clip. On a small
    # screen the minimum wins and the popup is allowed to be scrolled.
    cap_w = max(cap_w, min_w)
    cap_h = max(cap_h, min_h)
    widget.setMaximumSize(cap_w, cap_h)

    hint = widget.sizeHint()
    width = min(max(hint.width(), min_w), cap_w)
    # Ask the layout how tall it needs to be *at that width*, not at whatever
    # width it happened to guess. Wrapping labels answer differently.
    height = hint.height()
    layout = widget.layout()
    if layout is not None and layout.hasHeightForWidth():
        height = max(height, layout.heightForWidth(width))
    height = min(max(height, min_h), cap_h)

    widget.resize(width, height)
    return (width, height)


__all__ = ["size_to_content", "SCREEN_FRACTION"]
