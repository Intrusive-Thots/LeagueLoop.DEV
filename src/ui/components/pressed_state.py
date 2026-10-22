"""Pressed/active states for CustomTkinter buttons (#34).

CTkButton only knows normal and hover, so a click gave no feedback until the
command ran. ``install_pressed_states`` tags each button's parts with one bind class: on mouse
down the button's inner fill darkens (its hover colour, 18% darker); on
release it returns to hover (pointer still inside) or normal.
"""
from __future__ import annotations

import customtkinter as ctk
from utils.logger import Logger
from ui.components.color_utils import darken_color

PRESSED_FALLBACK = "#1A2430"  # transparent/ghost buttons: a faint well
_pressed = {"btn": None}


def pressed_color(fg, hover):
    """Colour to paint while *fg*/*hover* button is held down."""
    base = hover if hover not in (None, "transparent") else fg
    if isinstance(base, (list, tuple)):
        base = base[-1]  # dark-mode value
    if not isinstance(base, str) or not base.startswith("#"):
        return PRESSED_FALLBACK
    r, g, b = (int(base[i:i + 2], 16) for i in (1, 3, 5))
    if (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.35:
        return darken_color(base, 18)  # light fills (gold primary): press darker
    # dark fills: darkening is invisible next to the card, so tint 22% toward gold
    gr, gg, gb = 0xC8, 0xAA, 0x6E
    return "#%02X%02X%02X" % tuple(int(c + (t - c) * 0.22) for c, t in ((r, gr), (g, gg), (b, gb)))


def _button_for(widget):
    w = widget
    for _ in range(3):
        if w is None:
            return None
        if isinstance(w, ctk.CTkButton):
            return w
        w = getattr(w, "master", None)
    return None


def _paint(btn, color):
    btn._canvas.itemconfig("inner_parts", outline=color, fill=color)
    for lbl in (getattr(btn, "_text_label", None), getattr(btn, "_image_label", None)):
        if lbl is not None:
            lbl.configure(bg=color)


def _on_press(event):
    try:
        btn = _button_for(event.widget)
        if btn is None or getattr(btn, "_state", "normal") != "normal":
            return
        col = pressed_color(btn.cget("fg_color"), btn.cget("hover_color"))
        _paint(btn, col)
        _pressed["btn"] = btn
        # Focus handling redraws the button (focus ring border) right after the
        # press, repainting fg; paint again once that has run.
        btn.after(15, lambda: _pressed["btn"] is btn and btn.winfo_exists() and _paint(btn, col))
    except Exception as exc:
        Logger.debug("PressedState", "press paint failed", exc=exc)


def _on_release(event):
    btn, _pressed["btn"] = _pressed["btn"], None
    if btn is None:
        return
    try:
        if not btn.winfo_exists():
            return
        if getattr(btn, "_mouse_inside", False):
            btn._on_enter()
        else:
            btn._on_leave()
    except Exception as exc:
        Logger.debug("PressedState", "release restore failed", exc=exc)


_TAG = "LLPressed"


def _tag_buttons(widget) -> int:
    """Put the LLPressed tag first on every CTkButton part under *widget*."""
    n = 0
    stack = [widget]
    while stack:
        w = stack.pop()
        try:
            stack.extend(w.winfo_children())
        except Exception as exc:
            Logger.debug("PressedState", "children lookup failed", exc=exc)
            continue
        if not isinstance(w, ctk.CTkButton):
            continue
        for part in (getattr(w, "_canvas", None), getattr(w, "_text_label", None),
                     getattr(w, "_image_label", None)):
            if part is None:
                continue
            tags = part.bindtags()
            if _TAG not in tags:
                # First, so a widget binding returning "break" can't swallow it.
                part.bindtags((_TAG,) + tuple(tags))
                n += 1
    return n


def install_pressed_states(root, scope=None) -> int:
    """Give every CTkButton under *scope* (default *root*) a pressed state.

    Safe to call repeatedly (tabs build lazily); returns parts newly tagged.
    """
    if not getattr(root, "_ll_pressed_states", False):
        root.bind_class(_TAG, "<ButtonPress-1>", _on_press, add="+")
        root.bind_class(_TAG, "<ButtonRelease-1>", _on_release, add="+")
        root._ll_pressed_states = True
    return _tag_buttons(scope or root)
