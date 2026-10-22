"""
Tab Navigation component.

Equal-width tabs that always fit the parent (no clipped trailing tab).
Optional short labels via `labels` map: internal name → display text, and
optional `icons` map: internal name → glyph name (see ui.components.glyphs).

The selected tab is marked three ways so it never relies on colour alone:
brighter text, a gold icon, and a 2 px gold underline.
"""
import customtkinter as ctk  # type: ignore
from .factory import get_color, get_font
from .hover import apply_click_animation
from utils.logger import Logger

TAB_ACTIVE_TEXT = "#F0E6D2"
TAB_IDLE_TEXT = "#8A93A0"   # ≥4.5:1 on the app background
TAB_GOLD = "#C8AA6E"


class TabBar(ctk.CTkFrame):
    def __init__(self, master, tabs, default_tab=None, command=None, labels=None, icons=None, **kwargs):
        has_icons = bool(icons)
        super().__init__(master, fg_color="transparent", height=42 if has_icons else 28, **kwargs)
        self.command = command
        self.tabs = list(tabs)
        self.labels = labels or {}
        self.icons = icons or {}
        self.buttons = {}
        self.indicators = {}
        self._images = {}

        # Grid with a shared "uniform" group gives every tab exactly the same
        # width regardless of label length, and never pushes tabs off-screen.
        if hasattr(self, "grid_propagate"):
            self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        for col, tab_name in enumerate(self.tabs):
            display = self.labels.get(tab_name, tab_name)
            self.grid_columnconfigure(col, weight=1, uniform="tabs")
            cell = self

            img_kw = {}
            glyph = self.icons.get(tab_name)
            if glyph:
                try:
                    from .glyphs import ctk_glyph
                    self._images[tab_name] = (ctk_glyph(glyph, TAB_IDLE_TEXT, 16),
                                              ctk_glyph(glyph, TAB_GOLD, 16))
                    img_kw = {"image": self._images[tab_name][0], "compound": "top"}
                except Exception as exc:
                    Logger.debug("TabBar", "glyph load failed", exc=exc)

            btn = ctk.CTkButton(
                cell,
                text=display,
                width=1,  # let pack expand assign equal share
                height=36 if img_kw else 24,
                fg_color="transparent",
                text_color=TAB_IDLE_TEXT,
                hover_color=get_color("colors.state.hover"),
                font=get_font("caption", "bold"),
                command=lambda t=tab_name: self.select_tab(t),
                corner_radius=4,
                **img_kw,
            )
            btn.grid(row=0, column=col, sticky="nsew", padx=1)
            apply_click_animation(btn, normal_color="transparent")
            ind = ctk.CTkFrame(cell, height=2, corner_radius=0, fg_color="transparent")
            ind.grid(row=1, column=col, sticky="ew", padx=8)
            self.buttons[tab_name] = btn
            self.indicators[tab_name] = ind
            if display != tab_name:
                try:
                    from ui.ui_shared import CTkTooltip
                    CTkTooltip(btn, tab_name)
                except Exception as exc:
                    Logger.debug("TabBar", "__init__ suppressed an error", exc=exc)

        self.current_tab = None
        if default_tab and default_tab in self.buttons:
            self.select_tab(default_tab)

    def set_active(self, tab_name):
        """Style *tab_name* as selected without invoking the command."""
        self.current_tab = tab_name
        for name, btn in self.buttons.items():
            active = name == tab_name
            kw = {"fg_color": "transparent",
                  "text_color": TAB_ACTIVE_TEXT if active else TAB_IDLE_TEXT}
            if name in self._images:
                kw["image"] = self._images[name][1 if active else 0]
            btn.configure(**kw)
            btn._orig_pulse_fg = "transparent"
            self.indicators[name].configure(fg_color=TAB_GOLD if active else "transparent")

    def select_tab(self, tab_name):
        if tab_name == self.current_tab:
            return
        self.set_active(tab_name)
        if self.command:
            self.command(tab_name)
