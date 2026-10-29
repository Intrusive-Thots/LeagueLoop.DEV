"""
Keep popup windows on-screen.

The sidebar docks beside the League client, so it often sits at a screen
edge. Popups that centre on the 300 px sidebar (About, Automation Editor) or
on the client (Ban / ARAM lists) would then open partly off-screen, hiding
their title and Save / Close buttons. `place_on_screen` clamps a requested
position into the work area of the monitor the anchor window is on (taskbar
excluded on Windows; negative coordinates of a left-hand monitor stay valid).
"""
import sys

from utils.logger import Logger

EDGE_MARGIN = 8


def clamp_rect(x, y, w, h, area, margin=EDGE_MARGIN):
    """Return (x, y) moved so a w×h window fits inside area=(left, top, right, bottom).

    When the window is larger than the area it is pinned to the top-left
    corner so its title bar (drag handle and close button) stays reachable.
    """
    left, top, right, bottom = area
    max_x = right - w - margin
    max_y = bottom - h - margin
    x = min(int(x), max_x)
    y = min(int(y), max_y)
    x = max(x, left + margin)
    y = max(y, top + margin)
    return x, y


def _win32_work_area(px, py):
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    user32 = ctypes.windll.user32
    MONITOR_DEFAULTTONEAREST = 2
    hmon = user32.MonitorFromPoint(wintypes.POINT(int(px), int(py)), MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not hmon or not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
        return None
    r = info.rcWork
    return (r.left, r.top, r.right, r.bottom)


def work_area_for(widget):
    """Work area (left, top, right, bottom) of the monitor showing *widget*."""
    try:
        cx = widget.winfo_rootx() + widget.winfo_width() // 2
        cy = widget.winfo_rooty() + widget.winfo_height() // 2
    except Exception:
        cx = cy = 0
    if sys.platform == "win32":
        try:
            area = _win32_work_area(cx, cy)
            if area:
                return area
        except Exception as exc:
            Logger.debug("WindowPlace", "monitor lookup failed", exc=exc)
    try:
        return (0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight())
    except Exception:
        return (0, 0, 1920, 1080)


def place_on_screen(win, x, y, w, h, anchor=None, set_size=True):
    """Apply geometry to *win* at (x, y), clamped to the anchor's monitor."""
    area = work_area_for(anchor if anchor is not None else win)
    x, y = clamp_rect(x, y, w, h, area)
    geo = f"{w}x{h}+{x}+{y}" if set_size else f"+{x}+{y}"
    win.geometry(geo)
    return x, y


def centre_on(win, anchor, w, h, set_size=True):
    """Centre a w×h *win* over *anchor*, kept fully on the anchor's monitor."""
    x = anchor.winfo_rootx() + (anchor.winfo_width() - w) // 2
    y = anchor.winfo_rooty() + (anchor.winfo_height() - h) // 2
    return place_on_screen(win, x, y, w, h, anchor=anchor, set_size=set_size)
