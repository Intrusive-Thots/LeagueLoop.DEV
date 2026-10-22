import customtkinter as ctk  # type: ignore
from ui.components.factory import get_color, get_font
from ui.components.lol_toggle import LolToggle  # type: ignore
from ui.ui_shared import CTkTooltip  # type: ignore
from utils.logger import Logger

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
        # Inline: label left, recorder right — one row per hotkey instead of
        # two, so the whole Hotkeys card reads as a compact key map.
        self.text_label.pack(side="left", anchor="w")

        if tooltip_text:
            CTkTooltip(self.text_label, tooltip_text)

        self.recorder = HotkeyRecorder(
            self,
            initial_value=default_val,
            width=130,
            on_change=lambda val: on_change_callback(val, config_key)
        )
        self.recorder.pack(side="right")
        
        if tooltip_text:
            CTkTooltip(self.recorder, tooltip_text)


class SettingsActionRow(ctk.CTkFrame):
    """A reusable component for a setting row with a label/description, live feedback, and an action button."""
    def __init__(self, master, label_text, button_text, command, description="", tooltip_text="", button_width=110, style="primary", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.original_button_text = button_text
        self.command = command
        self.button_width = button_width

        # Top row: title/description on the left, button on the right
        self.top_row = ctk.CTkFrame(self, fg_color="transparent")
        self.top_row.pack(fill="x", expand=True)

        from ui.components.factory import make_button
        # Reserve sufficient width for the action button and pack it first to guarantee space
        self.button = make_button(
            self.top_row,
            text=button_text,
            style=style,
            font=get_font("caption", "bold"),
            width=button_width,
            height=28,
            command=command
        )
        self.button.pack(side="right", padx=(8, 0), anchor="center")

        # Responsive left-hand text container
        self.left_frame = ctk.CTkFrame(self.top_row, fg_color="transparent")
        self.left_frame.pack(side="left", fill="both", expand=True)

        # Initial wrap estimate based on narrow panel width
        init_text_w = max(60, 270 - button_width - 16)

        self.text_label = ctk.CTkLabel(
            self.left_frame,
            text=label_text,
            font=get_font("body", "bold"),
            anchor="w",
            justify="left",
            wraplength=init_text_w,
            text_color=get_color("colors.text.primary")
        )
        self.text_label.pack(side="top", fill="x", anchor="w")

        if description:
            self.desc_label = ctk.CTkLabel(
                self.left_frame,
                text=description,
                font=get_font("small"),
                anchor="w",
                justify="left",
                wraplength=init_text_w,
                text_color=get_color("colors.text.muted")
            )
            self.desc_label.pack(side="top", fill="x", anchor="w", pady=(1, 0))
        else:
            self.desc_label = None

        # Bottom live status feedback label below title/button row
        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=get_font("small"),
            anchor="w",
            justify="left",
            wraplength=250,
            text_color=get_color("colors.accent.gold", "#C8AA6E")
        )

        if tooltip_text:
            CTkTooltip(self.text_label, tooltip_text)
            CTkTooltip(self.button, tooltip_text)

        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event=None):
        """Recalculate label wraplengths dynamically when row width changes."""
        try:
            total_w = self.winfo_width()
            if total_w <= 1:
                return
            btn_w = self.button.winfo_reqwidth() if hasattr(self, "button") else self.button_width
            avail_text_w = max(60, total_w - btn_w - 14)
            if hasattr(self, "text_label") and self.text_label.winfo_exists():
                self.text_label.configure(wraplength=avail_text_w)
            if hasattr(self, "desc_label") and self.desc_label and self.desc_label.winfo_exists():
                self.desc_label.configure(wraplength=avail_text_w)
            if hasattr(self, "status_label") and self.status_label.winfo_exists():
                self.status_label.configure(wraplength=max(60, total_w - 8))
        except Exception as exc:
            Logger.debug("SettingsActionRow", f"Error in _on_configure: {exc}", exc=exc)

    def set_loading(self, is_loading: bool, loading_text: str = "Working..."):
        """Toggles loading text while keeping button visible and clickable."""
        try:
            if is_loading:
                self.button.configure(text=loading_text)
            else:
                self.button.configure(text=self.original_button_text)
        except Exception as exc:
            Logger.debug("SettingsActionRow", f"Failed to update loading state: {exc}", exc=exc)

    def clear_status(self):
        """Cleans up the inline status display."""
        self.set_status("")

    def set_status(self, message: str, is_error: bool = False, icon: str = None):
        """Sets inline real-time status display with automatic wrapping and visibility.

        *icon* is an optional glyph name ("check", "close", "refresh"...) drawn
        left of the text in the status colour instead of a text symbol.
        """
        try:
            color = get_color("colors.state.danger", "#E74C3C") if is_error else get_color("colors.accent.gold", "#C8AA6E")
            total_w = self.winfo_width()
            status_w = max(60, total_w - 8) if total_w > 1 else 250
            img = None
            if icon and message:
                from ui.components.glyphs import ctk_glyph
                img = ctk_glyph(icon, color, 12)
            self.status_label.configure(text=(" " + message) if img else message, text_color=color,
                                        wraplength=status_w, justify="left",
                                        image=img, compound="left")
            if message and not self.status_label.winfo_ismapped():
                self.status_label.pack(side="top", fill="x", anchor="w", pady=(4, 0))
            elif not message and self.status_label.winfo_ismapped():
                self.status_label.pack_forget()
        except Exception as exc:
            Logger.debug("SettingsActionRow", f"Failed to update status label: {exc}", exc=exc)

