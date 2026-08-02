import customtkinter as ctk
from ui.theme.token_loader import TOKENS
from ui.components.factory import get_color, get_font

class PageContainer(ctk.CTkFrame):
    def __init__(self, master, title=None, fg_color=None, padding=None, **kwargs):
        bg_color = fg_color or get_color("colors.background.app", default="#010A13")
        pad = padding if padding is not None else TOKENS.get("spacing.lg", 24)

        super().__init__(
            master,
            fg_color=bg_color,
            corner_radius=0,
            **kwargs
        )

        self.pack_propagate(False)

        if title:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.pack(fill="x", padx=pad, pady=(pad, TOKENS.get("spacing.sm", 8)))

            ctk.CTkLabel(
                header,
                text=title.upper(),
                font=get_font("title"),
                text_color=get_color("colors.accent.gold", default="#C8AA6E")
            ).pack(side="left")

            ctk.CTkFrame(
                self,
                height=1,
                fg_color=get_color("colors.accent.gold", default="#C8AA6E")
            ).pack(fill="x", padx=pad, pady=(0, pad))

        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=pad, pady=(0, pad))
