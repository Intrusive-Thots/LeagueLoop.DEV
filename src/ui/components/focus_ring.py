"""Keyboard focus rings for CustomTkinter controls (#14).

CustomTkinter draws its widgets on canvases that Tk does not put in the Tab
order, and nothing showed which control had focus. ``install_focus_rings``

* makes CTk buttons, switches, checkboxes and RiotButtons Tab-focusable,
* binds Space/Return to activate the focused control, and
* draws a 2px gold ring on the focused control — only after keyboard use
  ("focus-visible"), so mouse clicks don't leave rings behind.
"""
from __future__ import annotations

import time

import customtkinter as ctk
from utils.logger import Logger

RING = "#C8AA6E"
_FOCUSABLE = (ctk.CTkButton, ctk.CTkSwitch, ctk.CTkCheckBox, ctk.CTkSegmentedButton)


def _owner(widget):
    """Map an inner Tk canvas/label back to the CTk control that owns it."""
    w = widget
    for _ in range(3):
        if w is None:
            return None
        if isinstance(w, _FOCUSABLE) or getattr(w, "_ll_focus_ring", False):
            return w
        if w is widget and type(w).__name__ == "LolToggle":
            return w
        w = getattr(w, "master", None)
    return None


def _activate(ctl):
    try:
        if isinstance(ctl, (ctk.CTkSwitch, ctk.CTkCheckBox)):
            ctl.toggle()
        elif hasattr(ctl, "invoke"):
            ctl.invoke()
        elif hasattr(ctl, "_on_click"):
            ctl._on_click()
    except Exception as exc:
        Logger.debug("FocusRing", "_activate suppressed an error", exc=exc)


class _Rings:
    def __init__(self, root):
        self.root = root
        self.keyboard = False
        self.last_press = 0.0
        self.current = None
        self.saved = {}
        root.bind_all("<KeyPress-Tab>", self._kbd, add="+")
        root.bind_all("<Shift-KeyPress-Tab>", self._kbd, add="+")
        root.bind_all("<ISO_Left_Tab>", self._kbd, add="+")
        root.bind_all("<ButtonPress>", self._mouse, add="+")
        root.bind_all("<FocusIn>", self._focus_in, add="+")
        root.bind_all("<FocusOut>", self._focus_out, add="+")

    def _kbd(self, _e=None):
        self.keyboard = True

    def _mouse(self, _e=None):
        self.keyboard = False
        self.last_press = time.monotonic()
        self._clear()

    def _focus_in(self, e):
        ctl = _owner(e.widget)
        # Widget Tab bindings can swallow the KeyPress before the "all" tag,
        # so also treat any focus change not caused by a recent click as
        # keyboard-driven (focus-visible heuristic).
        by_click = time.monotonic() - self.last_press < 0.4
        if ctl is None or (by_click and not self.keyboard):
            return
        self._clear()
        self.current = ctl
        try:
            if type(ctl).__name__ == "LolToggle":  # plain tk.Canvas: use Tk's highlight ring
                self.saved[ctl] = ("hl", ctl.cget("highlightthickness"), ctl.cget("highlightbackground"))
                ctl.configure(highlightthickness=2, highlightcolor=RING, highlightbackground=RING)
            elif getattr(ctl, "_ll_focus_ring", False):  # RiotButton: outer frame is the border
                self.saved[ctl] = ("fg_color", ctl.cget("fg_color"))
                ctk.CTkFrame.configure(ctl, fg_color=RING)
            else:
                self.saved[ctl] = ("border", ctl.cget("border_color"), ctl.cget("border_width"))
                ctl.configure(border_color=RING, border_width=2)
        except Exception:
            self.saved.pop(ctl, None)

    def _focus_out(self, e):
        if _owner(e.widget) is self.current:
            self._clear()

    def _clear(self):
        ctl, self.current = self.current, None
        if ctl is None or ctl not in self.saved:
            return
        state = self.saved.pop(ctl)
        try:
            if state[0] == "hl":
                ctl.configure(highlightthickness=state[1], highlightbackground=state[2])
            elif state[0] == "fg_color":
                ctk.CTkFrame.configure(ctl, fg_color=state[1])
            else:
                ctl.configure(border_color=state[1], border_width=state[2])
        except Exception as exc:
            Logger.debug("FocusRing", "_clear suppressed an error", exc=exc)


def make_focusable(widget) -> int:
    """Walk *widget*'s tree and put every CTk control in the Tab order."""
    count = 0
    stack = [widget]
    while stack:
        w = stack.pop()
        try:
            stack.extend(w.winfo_children())
        except Exception:
            continue
        if isinstance(w, _FOCUSABLE):  # RiotButton binds its own keys
            canvas = getattr(w, "_canvas", None)
            if canvas is None or getattr(canvas, "_ll_bound", False):
                continue
            try:
                canvas.configure(takefocus=1)
                for seq in ("<KeyPress-space>", "<KeyPress-Return>"):
                    canvas.bind(seq, lambda _e, c=w: _activate(c), add="+")
                canvas._ll_bound = True
                count += 1
            except Exception as exc:
                Logger.debug("FocusRing", "make_focusable suppressed an error", exc=exc)
    return count


def install_focus_rings(root, scope=None):
    """Install focus-visible rings on *root* (once) and make *scope* focusable."""
    if not getattr(root, "_ll_rings", None):
        root._ll_rings = _Rings(root)
    return make_focusable(scope or root)
