"""
Track the League Client's top-level window so the companion can sit beside it.

This module was deleted along with the PySide6 shell on the grounds that its
only consumer was the Qt companion anchor. That was wrong: `LeagueLoopApp`'s
`docking_loop` imports it too, at the top of the thread body and outside any
`try`. So the docking thread died the instant it started, every launch, with

    ModuleNotFoundError: No module named 'services.client_window_tracker'

and the window simply stayed wherever it opened, at its startup 300x500. The
app looked broken in a way that had nothing to do with docking logic, because
the docking logic never ran a single line.

`tests/test_import_graph.py` now walks every `import` in `src/` and fails if a
first-party module named there does not exist, so removing a file out from
under a live consumer cannot pass the suite again.

The interface is only what `docking_loop` uses:

    tracker = ClientWindowTracker()
    window = tracker.tick()          # -> ClientWindow
    window.found / .visible / .minimized / .rect

Nothing here needs the LCU. It reads the window manager, so it works while the
client is still loading and before any port or auth token exists.
"""
from __future__ import annotations

import ctypes
import sys

if sys.platform == "win32":  # pragma: no cover - Windows-only
    # `import ctypes` does NOT bring in the `wintypes` submodule; it has to be
    # imported by name. Code elsewhere in the app gets away with
    # `ctypes.wintypes.RECT` only because some other library happens to have
    # imported it first, which is not something to depend on in the module
    # that keeps the companion attached to the client.
    import ctypes.wintypes  # noqa: F401
from dataclasses import dataclass, field
from typing import Optional, Tuple

from utils.logger import Logger

TAG = "ClientWindow"

#: Window titles the League Client presents. The client is a CEF host, so the
#: class name varies by patch far more than the title does.
LEAGUE_TITLES = ("league of legends",)
#: The Riot Client, used as a fallback so the companion still anchors during
#: the sign-in step, before League itself has a window.
RIOT_TITLES = ("riot client", "riot client main")

_IS_WINDOWS = sys.platform == "win32"


@dataclass
class ClientWindow:
    """One observation of the client's window. Never raises; always answers."""

    found: bool = False
    visible: bool = False
    minimized: bool = False
    #: (x, y, width, height) in physical pixels. Zeroes when not found.
    rect: Tuple[int, int, int, int] = field(default=(0, 0, 0, 0))
    hwnd: int = 0
    title: str = ""

    @property
    def usable(self) -> bool:
        """Found, on screen, not minimised, and with a real size."""
        return (
            self.found
            and self.visible
            and not self.minimized
            and self.rect[2] > 0
            and self.rect[3] > 0
        )


class ClientWindowTracker:
    """Finds the client window and reports where it is, once per `tick()`.

    The handle is cached between ticks and revalidated rather than re-searched,
    because enumerating every top-level window twenty times a second is the
    kind of cost that shows up as stutter in the game.
    """

    def __init__(self, poll_titles: Optional[Tuple[str, ...]] = None) -> None:
        self._hwnd: int = 0
        self._title: str = ""
        self._announced: bool = False
        self._last_rect: Optional[Tuple[int, int, int, int]] = None
        self._titles = poll_titles or (LEAGUE_TITLES + RIOT_TITLES)
        self._user32 = ctypes.windll.user32 if _IS_WINDOWS else None

    # ---------------------------------------------------------------- public
    def tick(self) -> ClientWindow:
        """Look at the client window now. Safe to call from a tight loop."""
        if not _IS_WINDOWS:
            return ClientWindow()

        try:
            if not self._still_valid(self._hwnd):
                if self._hwnd:
                    Logger.info(TAG, "Lost the client window; re-discovering.")
                    self._forget()
                self._hwnd, self._title = self._find()

            if not self._hwnd:
                if self._announced:
                    Logger.info(TAG, "League Client window closed.")
                    self._announced = False
                return ClientWindow()

            return self._observe()
        except Exception as exc:
            # A window can be destroyed between two calls here. That is normal
            # during a client restart and must not take the docking thread
            # down with it -- which is the whole failure this file exists to
            # stop happening twice.
            Logger.debug(TAG, "tick suppressed an error", exc=exc)
            self._forget()
            return ClientWindow()

    def forget(self) -> None:
        """Drop the cached handle; the next tick searches again."""
        self._forget()

    # --------------------------------------------------------------- private
    def _forget(self) -> None:
        self._hwnd = 0
        self._title = ""
        self._last_rect = None

    def _still_valid(self, hwnd: int) -> bool:
        if not hwnd:
            return False
        return bool(self._user32.IsWindow(hwnd))

    def _find(self) -> Tuple[int, str]:
        """Enumerate top-level windows for the first title we recognise.

        League wins over the Riot Client when both are open: once the game
        client exists it is the one worth docking to.
        """
        user32 = self._user32
        league: list = [0, ""]
        riot: list = [0, ""]

        def enum_callback(hwnd, _lparam):
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                raw = buf.value.strip()
                title = raw.lower()
                if title in LEAGUE_TITLES:
                    league[0], league[1] = hwnd, raw
                    return False  # stop: nothing beats the League window
                if title in RIOT_TITLES and not riot[0]:
                    riot[0], riot[1] = hwnd, raw
            except Exception as exc:
                # A window can vanish mid-enumeration. Never let one bad
                # handle abort the search for the rest.
                Logger.debug(TAG, "Skipped a window during discovery", exc=exc)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        hwnd, title = (league if league[0] else riot)
        if hwnd:
            rect = self._rect_of(hwnd)
            Logger.info(
                TAG,
                "Found the League Client window: {}x{} at ({}, {}) - {}".format(
                    rect[2], rect[3], rect[0], rect[1], title
                ),
                hwnd=hwnd,
            )
            self._announced = True
        return hwnd, title

    def _rect_of(self, hwnd: int) -> Tuple[int, int, int, int]:
        rect = ctypes.wintypes.RECT()
        self._user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (
            rect.left,
            rect.top,
            rect.right - rect.left,
            rect.bottom - rect.top,
        )

    def _observe(self) -> ClientWindow:
        user32 = self._user32
        hwnd = self._hwnd
        minimized = bool(user32.IsIconic(hwnd))
        visible = bool(user32.IsWindowVisible(hwnd))
        rect = self._rect_of(hwnd)

        # A minimised window reports a rect off the bottom of the screen.
        # Passing that on would fling the companion off with it, so report the
        # last good geometry and let the caller act on `minimized` instead.
        if minimized and self._last_rect:
            rect = self._last_rect
        elif not minimized:
            if rect != self._last_rect:
                Logger.debug(TAG, "Client window geometry: {}".format(rect))
            self._last_rect = rect

        return ClientWindow(
            found=True,
            visible=visible,
            minimized=minimized,
            rect=rect,
            hwnd=hwnd,
            title=self._title,
        )
