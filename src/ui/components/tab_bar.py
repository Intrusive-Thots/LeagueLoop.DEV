"""
Tab Navigation component.

Equal-width tabs that always fit the parent (no clipped trailing tab).
Optional short labels via `labels` map: internal name → display text.
"""
import customtkinter as ctk  # type: ignore
from .factory import get_color, get_font
from .hover import apply_click_animation
from utils.logger import Logger


class TabBar(ctk.CTkFrame):
    def __init__(self, master, tabs, default_tab=None, command=None, labels=None, **kwargs):
        super().__init__(master, fg_color="transparent", height=28, **kwargs)
        self.pack_propagate(False)
        self.command = command
        self.tabs = list(tabs)
        self.labels = labels or {}
        self.buttons = {}

        n = max(len(self.tabs), 1)
        # Tiny base width + expand/fill so each tab gets an equal slice of
        # the real parent width. A large fixed width (old 240//n with long
        # labels) overflowed and clipped the last tab (Settings).
        for tab_name in self.tabs:
            display = self.labels.get(tab_name, tab_name)
            btn = ctk.CTkButton(
                self,
                text=display,
                width=1,  # let pack expand assign equal share
                height=24,
                fg_color="transparent",
                text_color=get_color("colors.text.muted"),
                hover_color=get_color("colors.state.hover"),
                font=get_font("caption", "bold"),
                command=lambda t=tab_name: self.select_tab(t),
                corner_radius=4,
            )
            btn.pack(side="left", padx=1, expand=True, fill="both")
            apply_click_animation(btn, normal_color="transparent")
            self.buttons[tab_name] = btn
            # Full name on hover when using short labels
            if display != tab_name:
                try:
                    from ui.ui_shared import CTkTooltip
                    CTkTooltip(btn, tab_name)
                except Exception as exc:
                    Logger.debug("TabBar", "__init__ suppressed an error", exc=exc)

        self.current_tab = None
        if default_tab and default_tab in self.buttons:
            self.select_tab(default_tab)

    def select_tab(self, tab_name):
        if tab_name == self.current_tab:
            return

        self.current_tab = tab_name

        for name, btn in self.buttons.items():
            if name == tab_name:
                active_bg = get_color("colors.background.card")
                btn.configure(
                    fg_color=active_bg,
                    text_color=get_color("colors.text.primary"),
                )
                btn._orig_pulse_fg = active_bg
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=get_color("colors.text.muted"),
                )
                btn._orig_pulse_fg = "transparent"

        if self.command:
            self.command(tab_name)
