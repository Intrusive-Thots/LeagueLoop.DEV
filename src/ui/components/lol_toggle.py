import customtkinter as ctk
from ui.components.factory import get_color

class LolToggle(ctk.CTkSwitch):
    """Custom Riot-style sliding toggle switch leveraging CTkSwitch for stability."""
    def __init__(self, master, variable=None, command=None, bg_color=None, **kwargs):
        # Clean canvas specific kwargs
        kwargs.pop("width", None)
        kwargs.pop("height", None)
        kwargs.pop("highlightthickness", None)
        kwargs.pop("bg", None)
        kwargs.pop("takefocus", None)
        
        # Style CTkSwitch to match the Riot design system
        inactive_color = get_color("colors.background.card", "#1E2328")
        active_color = "#A88A4E"
        knob_color = get_color("colors.text.primary", "#F0E6D2")
        
        super().__init__(
            master,
            text="",  # No text label on the toggle itself
            variable=variable,
            command=command,
            fg_color=inactive_color,
            progress_color=active_color,
            button_color=knob_color,
            button_hover_color=knob_color,
            width=36,
            height=18,
            **kwargs
        )


