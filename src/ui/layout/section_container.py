import customtkinter as ctk
from ui.theme.token_loader import TOKENS

class SectionContainer(ctk.CTkFrame):
    def __init__(self, master, padding=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        pad = padding if padding is not None else TOKENS.get("spacing.md", 16)
        self.grid_columnconfigure(0, weight=1)
