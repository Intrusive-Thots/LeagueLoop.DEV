import customtkinter as ctk
from ui.theme.token_loader import TOKENS
from ui.components.factory import get_color, get_font, parse_border
from ui.components.hover import apply_card_hover

class Card(ctk.CTkFrame):
    def __init__(self, master, corner_radius=None, fg_color=None, **kwargs):
        def_bg = get_color("colors.background.card", default="#1E2328")
        def_radius = TOKENS.get("radius.md", default=8)
        def_border_w, def_border_c = parse_border("subtle")

        bg_color = fg_color or def_bg
        radius = corner_radius or def_radius
        border_width = kwargs.pop("border_width", def_border_w)
        border_color = kwargs.pop("border_color", def_border_c)

        super().__init__(
            master,
            fg_color=bg_color,
            corner_radius=radius,
            border_width=border_width,
            border_color=border_color,
            **kwargs
        )
        apply_card_hover(self)

class CardHeader(ctk.CTkFrame):
    def __init__(self, master, title, action_widget=None, collapsible=False, start_collapsed=False, content_widget=None, card_widget=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.collapsible = collapsible
        self.is_expanded = not start_collapsed
        self.content_widget = content_widget
        self.card_widget = card_widget

        self.label = ctk.CTkLabel(
            self,
            text=title,
            font=get_font("title"),
            text_color=get_color("colors.text.primary", default="#F0E6D2")
        )
        self.label.pack(side="left", padx=TOKENS.get("spacing.md", 16), pady=TOKENS.get("spacing.sm", 8))

        if action_widget:
            action_widget.pack(side="right", padx=TOKENS.get("spacing.md", 16), pady=TOKENS.get("spacing.sm", 8))

        if self.collapsible:
            from ui.components.buttons import IconButton
            self.btn_toggle = IconButton(
                self,
                text="▼" if self.is_expanded else "▶",
                command=self.toggle,
                size=24,
                font=get_font("body")
            )
            self.btn_toggle.pack(side="right", padx=TOKENS.get("spacing.md", 16), pady=TOKENS.get("spacing.sm", 8))

            # 🎨 Palette: Add UX affordances for the collapsible label
            self.label.configure(cursor="hand2")
            self.label.bind("<Button-1>", lambda e: self.toggle())
            self.label.bind("<Enter>", lambda e: self.label.configure(text_color=get_color("colors.text.secondary", default="#A09B8C")))
            self.label.bind("<Leave>", lambda e: self.label.configure(text_color=get_color("colors.text.primary", default="#F0E6D2")))

        self.underline = ctk.CTkFrame(
            self,
            height=1,
            fg_color=get_color("colors.accent.gold", default="#C8AA6E")
        )
        if self.is_expanded or not self.collapsible:
            self.underline.pack(side="bottom", fill="x", padx=TOKENS.get("spacing.md", 16))

    def toggle(self):
        if not self.collapsible or not self.content_widget:
            return

        if self.is_expanded:
            self.content_widget.pack_forget()
            self.underline.pack_forget()
            self.btn_toggle.configure(text="▶")
            if self.card_widget:
                self.card_widget.configure(height=40)
            self.is_expanded = False
        else:
            self.underline.pack(side="bottom", fill="x", padx=TOKENS.get("spacing.md", 16))
            self.content_widget.pack(fill="both", expand=True)
            self.btn_toggle.configure(text="▼")
            self.is_expanded = True

class CardContent(ctk.CTkFrame):
    def __init__(self, master, padding=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        pad = padding if padding is not None else TOKENS.get("spacing.md", 16)

class CardFooter(ctk.CTkFrame):
    def __init__(self, master, padding=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.pad = padding if padding is not None else TOKENS.get("spacing.md", 16)

        self.underline = ctk.CTkFrame(
            self,
            height=1,
            fg_color=parse_border("subtle")[1]
        )
        self.underline.pack(side="top", fill="x", padx=self.pad)

        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=self.pad, pady=self.pad)
