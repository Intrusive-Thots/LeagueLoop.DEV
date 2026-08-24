"""
One icon, everywhere, including the taskbar.

The taskbar button was showing Windows' generic white page rather than the
app's icon, and the reason is not the icon file — `assets/leagueloop.ico`
carries all seven sizes (16/24/32/48/64/128/256). It is that the Qt shell
never claimed an application identity.

Windows groups taskbar buttons by **AppUserModelID**. A Python process that
does not set one inherits the interpreter's, so the button belongs to
`python.exe`, and the icon shown is the one Explorer has for that — not the
one the window carries. The legacy CustomTkinter shell called
`SetCurrentProcessExplicitAppUserModelID` in `core/main.py`; the Qt entry
point never did, which is exactly the set of runs where the icon was wrong.

The call must happen **before the first window exists**, so `install()` is
called while the QApplication is being built.

Everything else here is about using one resolved path in all four places the
icon appears — application, window, tray, and the shortcut that launches it —
so they cannot drift apart again.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from utils.logger import Logger

TAG = "AppIcon"

#: Must match the AppUserModelID baked into the desktop shortcut, or Windows
#: treats the pinned shortcut and the running window as two different apps and
#: shows two taskbar buttons.
APP_USER_MODEL_ID = "LeagueLoop.Companion.1"

#: In preference order. `leagueloop.ico` is the multi-size file `make_icon.py`
#: writes; the rest are fallbacks for a partially-built checkout.
ICON_CANDIDATES = (
    "assets/leagueloop.ico",
    "assets/app.ico",
    "assets/icon.png",
    "assets/app.png",
)

_cached_path: Optional[str] = None
_identity_installed = False


def icon_path() -> Optional[str]:
    """The best available icon file, or None if the assets are missing."""
    global _cached_path
    if _cached_path is not None:
        return _cached_path or None
    try:
        from utils.path_utils import get_asset_path
    except Exception as exc:
        Logger.debug(TAG, "Could not import the asset path helper", exc=exc)
        return None

    for candidate in ICON_CANDIDATES:
        try:
            path = get_asset_path(candidate)
        except Exception:
            continue
        if path and os.path.exists(path):
            _cached_path = path
            return path
    Logger.warning(
        TAG,
        "No application icon was found, so the window and taskbar will show "
        "the platform default. Run `python tools/make_icon.py` to build it.",
    )
    _cached_path = ""
    return None


def app_icon():
    """A `QIcon` carrying every size in the .ico, or an empty one."""
    from PySide6.QtGui import QIcon

    path = icon_path()
    return QIcon(path) if path else QIcon()


def install_identity() -> bool:
    """Claim a taskbar identity. Returns True when Windows accepted it.

    Idempotent, and a no-op off Windows.
    """
    global _identity_installed
    if _identity_installed or sys.platform != "win32":
        return _identity_installed
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
        _identity_installed = True
        Logger.debug(TAG, f"Taskbar identity set to {APP_USER_MODEL_ID}.")
    except Exception as exc:
        # Not fatal: the app runs, the taskbar grouping is just wrong.
        Logger.warning(
            TAG,
            "Could not set the taskbar identity, so Windows may show the "
            "generic icon for this window.",
            exc=exc,
        )
    return _identity_installed


def apply_to(target) -> bool:
    """Give a QApplication, window or tray icon the app icon.

    Returns False when there was no icon to apply, so callers can tell "we
    set it" from "there was nothing to set" rather than guessing.
    """
    if target is None or not icon_path():
        return False
    setter = getattr(target, "setWindowIcon", None) or getattr(target, "setIcon", None)
    if setter is None:
        return False
    try:
        setter(app_icon())
        return True
    except Exception as exc:
        Logger.debug(TAG, "Could not apply the app icon", exc=exc)
        return False


__all__ = [
    "APP_USER_MODEL_ID", "ICON_CANDIDATES",
    "app_icon", "apply_to", "icon_path", "install_identity",
]
