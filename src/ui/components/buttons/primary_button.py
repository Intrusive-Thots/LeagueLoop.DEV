import customtkinter as ctk
from ui.theme.token_loader import TOKENS
from ui.components.factory import get_color, get_font
from ui.components.hover import apply_hover_brightness, apply_press_effect
from ui.components.tooltip import CTkTooltip

class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, text="", command=None, width=120, height=32, tooltip=None, **kwargs):
        # Pop all non-CTkButton custom kwargs
        kwargs.pop('style', None)
        icon = kwargs.pop('icon', None)
        if icon:
            kwargs['image'] = icon

        # Resolve defaults, allowing kwargs overrides
        bg_color = kwargs.pop('fg_color', get_color("colors.accent.primary", default="#0AC8B9"))
        text_color = kwargs.pop('text_color', get_color("colors.text.primary", default="#F0E6D2"))
        font = kwargs.pop('font', get_font("body", "bold"))
        corner_radius = kwargs.pop('corner_radius', TOKENS.get("radius.sm", default=4))
        cursor = kwargs.pop('cursor', 'hand2')

        super().__init__(
            master,
            text=text,
            command=command,
            width=width,
            height=height,
            fg_color=bg_color,
            text_color=text_color,
            font=font,
            corner_radius=corner_radius,
            cursor=cursor,
            **kwargs
        )
        apply_hover_brightness(self, bg_color)
        apply_press_effect(self, bg_color)

        if tooltip:
            self.tooltip = CTkTooltip(self, tooltip)
