"""
Win32 Acrylic Blur Effect
─────────────────────────
Applies a frosted glass (acrylic) blur to a tkinter window on Windows 10/11.
Falls back gracefully on unsupported platforms.

Uses the undocumented SetWindowCompositionAttribute API with ACCENT_ENABLE_ACRYLICBLURBEHIND.
"""

import ctypes
import platform
from utils.logger import Logger


class _AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WindowCompositionAttribData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.POINTER(_AccentPolicy)),
        ("SizeOfData", ctypes.c_size_t),
    ]


# Accent states
_ACCENT_DISABLED = 0
_ACCENT_ENABLE_BLURBEHIND = 3          # Standard blur (Win10 1607+)
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4   # Acrylic blur  (Win10 1803+)

# WindowCompositionAttribute enum
_WCA_ACCENT_POLICY = 19


def _get_hwnd(tk_window) -> int:
    """Extract the Win32 HWND from a tkinter window."""
    return ctypes.windll.user32.GetParent(tk_window.winfo_id())


def apply_acrylic_blur(tk_window, tint_color: int = 0x30000000, fallback_blur: bool = True) -> bool:
    """
    Apply acrylic blur to a tkinter/CTk window.

    Parameters
    ----------
    tk_window : tkinter.Tk or customtkinter.CTk
        The window to apply the effect to.
    tint_color : int
        ARGB tint color overlaid on the blur. Format: 0xAARRGGBB.
        Default: 0x30000000 (very subtle dark tint, mostly transparent).
    fallback_blur : bool
        If acrylic fails (pre-1803), fall back to standard blur.

    Returns
    -------
    bool
        True if the effect was applied successfully.
    """
    if platform.system() != "Windows":
        Logger.debug("SYS", "Acrylic blur skipped — not Windows")
        return False

    try:
        hwnd = _get_hwnd(tk_window)

        # Try acrylic first (Win10 1803+)
        accent = _AccentPolicy()
        accent.AccentState = _ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.GradientColor = tint_color

        data = _WindowCompositionAttribData()
        data.Attribute = _WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        result = ctypes.windll.user32.SetWindowCompositionAttribute(
            hwnd, ctypes.byref(data)
        )

        if result:
            Logger.info("SYS", "Acrylic blur applied successfully")
            return True

        # Fallback to standard blur (Win10 1607+)
        if fallback_blur:
            accent.AccentState = _ACCENT_ENABLE_BLURBEHIND
            accent.GradientColor = tint_color
            result = ctypes.windll.user32.SetWindowCompositionAttribute(
                hwnd, ctypes.byref(data)
            )
            if result:
                Logger.info("SYS", "Standard blur fallback applied")
                return True

        Logger.warning("SYS", "Blur effect not supported on this Windows version")
        return False

    except Exception as e:
        Logger.warning("SYS", f"Could not apply acrylic blur: {e}")
        return False


def remove_blur(tk_window) -> bool:
    """Remove any blur effect from the window."""
    if platform.system() != "Windows":
        return False

    try:
        hwnd = _get_hwnd(tk_window)

        accent = _AccentPolicy()
        accent.AccentState = _ACCENT_DISABLED

        data = _WindowCompositionAttribData()
        data.Attribute = _WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        ctypes.windll.user32.SetWindowCompositionAttribute(
            hwnd, ctypes.byref(data)
        )
        return True
    except Exception:
        return False
