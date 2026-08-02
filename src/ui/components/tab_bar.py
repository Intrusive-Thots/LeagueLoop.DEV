"""
Tab Navigation component.
"""
import customtkinter as ctk  # type: ignore
from .factory import get_color, get_font
from .hover import apply_click_animation

class TabBar(ctk.CTkFrame):
    def __init__(self, master, tabs, default_tab=None, command=None, **kwargs):
        super().__init__(master, fg_color="transparent", height=28, **kwargs)
        self.pack_propagate(False)
        self.command = command
        self.tabs = tabs
        self.buttons = {}
        
        # Calculate dynamic width to spread evenly
        btn_width = 240 // max(len(tabs), 1) if len(tabs) > 0 else 60

        for tab_name in tabs:
            btn = ctk.CTkButton(
                self, 
                text=tab_name, 
                width=btn_width, 
                height=24, 
                fg_color="transparent", 
                text_color=get_color("colors.text.muted"), 
                hover_color=get_color("colors.state.hover"), 
                font=get_font("caption", "bold"), 
                command=lambda t=tab_name: self.select_tab(t),
                corner_radius=4
            )
            btn.pack(side="left", padx=1, expand=True, fill="x")
            
            # Apply subtle pulse effect
            apply_click_animation(btn, normal_color="transparent")
            self.buttons[tab_name] = btn
            
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
                    text_color=get_color("colors.text.primary")
                )
                btn._orig_pulse_fg = active_bg
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=get_color("colors.text.muted")
                )
                btn._orig_pulse_fg = "transparent"
                
        if self.command:
            self.command(tab_name)
