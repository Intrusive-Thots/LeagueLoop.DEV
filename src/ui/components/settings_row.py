import customtkinter as ctk  # type: ignore
from ui.components.factory import get_color, get_font
from ui.components.lol_toggle import LolToggle  # type: ignore
from ui.ui_shared import CTkTooltip  # type: ignore

class SettingsToggleRow(ctk.CTkFrame):
    """A reusable component for a simple setting toggle row."""
    def __init__(self, master, label_text, variable, command, tooltip_text="", height=28, **kwargs):
        super().__init__(master, fg_color="transparent", height=height, **kwargs)
        self.pack_propagate(False)
        
        self.text_label = ctk.CTkLabel(
            self, 
            text=label_text, 
            font=get_font("body"), 
            anchor="w", 
            text_color=get_color("colors.text.primary")
        )
        self.text_label.pack(side="left")
        
        if tooltip_text:
            CTkTooltip(self.text_label, tooltip_text)
            
        self.toggle = LolToggle(self, variable=variable, command=command)
        self.toggle.pack(side="right")
        
        if tooltip_text:
            CTkTooltip(self.toggle, tooltip_text)

class SettingsSliderRow(ctk.CTkFrame):
    """A reusable component for a slider row with label and value display."""
    def __init__(self, master, label_text, variable, command, from_=0, to=10, number_of_steps=10, format_str="{:.1f}s", tooltip_text="", height=28, **kwargs):
        super().__init__(master, fg_color="transparent", height=height, **kwargs)
        self.pack_propagate(False)
        self.format_str = format_str
        self.command = command
        
        self.text_label = ctk.CTkLabel(
            self, 
            text=label_text, 
            font=get_font("body"), 
            anchor="w", 
            text_color=get_color("colors.text.primary")
        )
        self.text_label.pack(side="left")
        
        if tooltip_text:
            CTkTooltip(self.text_label, tooltip_text)
            
        self.value_label = ctk.CTkLabel(
            self, 
            text=self.format_str.format(variable.get()), 
            font=get_font("body", "bold"), 
            text_color=get_color("colors.accent.gold", "#C8AA6E"), 
            width=40
        )
        self.value_label.pack(side="right")
        
        self.slider = ctk.CTkSlider(
            self, 
            from_=from_, 
            to=to, 
            number_of_steps=number_of_steps, 
            variable=variable, 
            width=80, 
            fg_color=get_color("colors.background.app"), 
            progress_color=get_color("colors.accent.gold", "#C8AA6E"), 
            button_color=get_color("colors.text.primary", "#F0E6D2"), 
            button_hover_color="#FFFFFF", 
            command=self._on_slide
        )
        self.slider.pack(side="right", padx=(4, 4))
        
        if tooltip_text:
            CTkTooltip(self.slider, tooltip_text)

    def _on_slide(self, value):
        self.value_label.configure(text=self.format_str.format(value))
        if self.command:
            self.command(value)

class SettingsInputRow(ctk.CTkFrame):
    """A reusable component for a text input row."""
    def __init__(self, master, label_text, variable, command=None, placeholder_text="", tooltip_text="", height=28, **kwargs):
        super().__init__(master, fg_color="transparent", height=height, **kwargs)
        # We don't pack_propagate(False) here because entry can expand vertically if needed, 
        # but we'll try to keep it constrained
        
        self.text_label = ctk.CTkLabel(
            self, 
            text=label_text, 
            font=get_font("caption"), 
            text_color=get_color("colors.text.muted")
        )
        self.text_label.pack(anchor="w", pady=(0, 2))
        
        if tooltip_text:
            CTkTooltip(self.text_label, tooltip_text)
            
        self.entry = ctk.CTkEntry(
            self, 
            textvariable=variable, 
            font=get_font("body"), 
            height=26, 
            fg_color=get_color("colors.background.input", "#0A1220"), 
            border_color=get_color("colors.border.subtle"),
            placeholder_text=placeholder_text
        )
        self.entry.pack(fill="x")
        
        if command:
            self.entry.bind("<KeyRelease>", lambda e: command(variable.get()))
        
        if tooltip_text:
            CTkTooltip(self.entry, tooltip_text)

class SettingsHotkeyRow(ctk.CTkFrame):
    """A reusable component for a hotkey recorder row."""
    def __init__(self, master, label_text, config_key, default_val, on_change_callback, tooltip_text="", height=28, **kwargs):
        super().__init__(master, fg_color="transparent", height=height, **kwargs)
        from ui.components.hotkey_recorder import HotkeyRecorder
        
        self.text_label = ctk.CTkLabel(
            self, 
            text=label_text, 
            font=get_font("body"), 
            text_color=get_color("colors.text.primary")
        )
        self.text_label.pack(side="top", anchor="w")
        
        if tooltip_text:
            CTkTooltip(self.text_label, tooltip_text)
            
        self.recorder = HotkeyRecorder(
            self, 
            initial_value=default_val, 
            width=150, 
            on_change=lambda val: on_change_callback(val, config_key)
        )
        self.recorder.pack(fill="x", pady=(2, 0))
        
        if tooltip_text:
            CTkTooltip(self.recorder, tooltip_text)
