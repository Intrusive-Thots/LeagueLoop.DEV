import customtkinter as ctk
from ui.theme.token_loader import TOKENS
from ui.components.factory import get_color, get_font

class StatusBadge(ctk.CTkFrame):
    def __init__(self, master, status="default", text="", **kwargs):
        # Map statuses to colors
        status_map = {
            "success": get_color("colors.state.success", default="#0397AB"),
            "danger": get_color("colors.state.danger", default="#C64650"),
            "warning": get_color("colors.state.warning", default="#eab308"),
            "info": get_color("colors.accent.blue", default="#005A82"),
            "default": get_color("colors.background.card", default="#1E2328"),
        }

        bg_color = status_map.get(status, status_map["default"])
        text_color = get_color("colors.text.primary", default="#F0E6D2")
        font = get_font("caption", "bold")
        corner_radius = TOKENS.get("radius.sm", 4)

        super().__init__(
            master,
            fg_color=bg_color,
            corner_radius=corner_radius,
            **kwargs
        )

        # Inner padding frame (since CTkFrame doesn't have internal padding directly)
        pad_x = TOKENS.get("spacing.sm", 8)
        pad_y = TOKENS.get("spacing.xs", 4)

        self.label = ctk.CTkLabel(
            self,
            text=text,
            font=font,
            text_color=text_color,
        )
        self.label.pack(padx=pad_x, pady=pad_y)

    def set_status(self, status, text=None):
        status_map = {
            "success": get_color("colors.state.success", default="#0397AB"),
            "danger": get_color("colors.state.danger", default="#C64650"),
            "warning": get_color("colors.state.warning", default="#eab308"),
            "info": get_color("colors.accent.blue", default="#005A82"),
            "default": get_color("colors.background.card", default="#1E2328"),
        }
        self.configure(fg_color=status_map.get(status, status_map["default"]))
        if text:
            self.label.configure(text=text)
