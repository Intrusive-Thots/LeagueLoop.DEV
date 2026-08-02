import customtkinter as ctk
from ui.components.factory import get_color, get_font
from ui.components.cards import Card, CardHeader, CardContent

class ActivityLogPanel(Card):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.header = CardHeader(self, title="Activity Log")
        self.header.pack(fill="x")

        self.content = CardContent(self)
        self.content.pack(fill="both", expand=True)

        self.scroll = ctk.CTkScrollableFrame(
            self.content, fg_color="transparent",
            scrollbar_button_color=get_color("colors.background.card", "#1E2328"),
            scrollbar_button_hover_color=get_color("colors.text.disabled", "#3A4654")
        )
        self.scroll.pack(fill="both", expand=True)

    def add_log(self, text, level="info"):
        color_map = {
            "info": get_color("colors.text.secondary", default="#A09B8C"),
            "success": get_color("colors.state.success", default="#0397AB"),
            "warning": get_color("colors.state.warning", default="#eab308"),
            "error": get_color("colors.state.danger", default="#C64650")
        }
        color = color_map.get(level, color_map["info"])

        lbl = ctk.CTkLabel(
            self.scroll,
            text=f"• {text}",
            text_color=color,
            font=get_font("caption"),
            anchor="w",
            justify="left"
        )
        lbl.pack(fill="x", pady=2)

        # Auto-scroll to bottom logic would go here
