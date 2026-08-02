import customtkinter as ctk
from ui.theme.token_loader import TOKENS
from ui.components.factory import get_color, get_font

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, width=200, **kwargs):
        bg_color = get_color("colors.background.panel", default="#091428")

        super().__init__(
            master,
            width=width,
            fg_color=bg_color,
            corner_radius=0,
            **kwargs
        )
        self.pack_propagate(False)

class SidebarItem(ctk.CTkButton):
    def __init__(self, master, text, icon=None, command=None, is_active=False, **kwargs):
        bg_color = "transparent"
        text_color = get_color("colors.text.secondary", default="#A09B8C")
        hover_color = get_color("colors.state.hover", default="#1E282D")
        font = get_font("body", "bold")

        if is_active:
            bg_color = get_color("colors.accent.primary", default="#0AC8B9")
            text_color = get_color("colors.text.primary", default="#F0E6D2")

        super().__init__(
            master,
            text=text,
            image=icon,
            command=command,
            fg_color=bg_color,
            text_color=text_color,
            hover_color=hover_color,
            font=font,
            corner_radius=TOKENS.get("radius.sm", 4),
            height=40,
            anchor="w",
            cursor="hand2",
            **kwargs
        )

        if not is_active:
            text_primary = get_color("colors.text.primary")
            self.bind("<Enter>", lambda e: self.configure(text_color=text_primary))
            self.bind("<Leave>", lambda e: self.configure(text_color=text_color))
