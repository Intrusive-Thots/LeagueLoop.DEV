import customtkinter as ctk
from ui.components.factory import get_color, get_font
from ui.components.hover import apply_hover_brightness, apply_press_effect
from ui.components.tooltip import CTkTooltip

class IconButton(ctk.CTkButton):
    def __init__(self, master, icon=None, text="", command=None, size=32, style="ghost", tooltip=None, **kwargs):
        bg_color = "transparent"
        hover_color = kwargs.pop('hover_color', get_color("colors.state.hover", default="#1E282D"))
        text_color = kwargs.pop('text_color', get_color("colors.text.secondary", default="#A09B8C"))
        font = kwargs.pop('font', get_font("title"))
        corner_radius = kwargs.pop('corner_radius', size // 2)
        cursor = kwargs.pop('cursor', 'hand2')
        kwargs.pop('fg_color', None)  # Pop to allow override below

        if style == "primary":
            bg_color = get_color("colors.accent.primary", default="#0AC8B9")
            text_color = get_color("colors.text.primary", default="#F0E6D2")

        super().__init__(
            master,
            image=icon,
            text=text,
            command=command,
            width=size,
            height=size,
            fg_color=bg_color,
            hover_color=hover_color,
            text_color=text_color,
            font=font,
            corner_radius=corner_radius,
            cursor=cursor,
            **kwargs
        )

        if bg_color != "transparent":
            apply_hover_brightness(self, bg_color)
            apply_press_effect(self, bg_color)

        if tooltip:
            self.tooltip = CTkTooltip(self, tooltip)
