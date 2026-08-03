import customtkinter as ctk  # type: ignore
from PIL import ImageOps  # type: ignore
from ui.components.factory import get_color, get_font
from ui.components.lol_toggle import LolToggle  # type: ignore
from ui.ui_shared import CTkTooltip  # type: ignore

class ToggleRow(ctk.CTkFrame):
    """A reusable component for a toggle row with icon, label, toggle, and optional edit button."""
    def __init__(self, master, label_text, variable, command, tooltip_text="",
                 icon_item_id=None, icon_type="item", icon_champion_id=None,
                 assets=None, height=28, on_edit=None, **kwargs):
        super().__init__(master, fg_color="transparent", height=height, **kwargs)
        self.pack_propagate(False)
        
        self._variable = variable
        self._on_edit = on_edit
        self._pulse_job = None
        self._pulse_state = True  # True = full brightness
        self._color_image = None
        self._gray_image = None
        self._icon_size = (24, 24)
        
        self.icon_label = ctk.CTkLabel(self, text="", width=24)
        self.icon_label.pack(side="left")
            
        self.text_label = ctk.CTkLabel(
            self, 
            text=label_text, 
            font=get_font("body"), 
            width=90, 
            anchor="w", 
            text_color=get_color("colors.text.primary", "#F0E6D2")
        )
        self.text_label.pack(side="left", padx=(6, 0))
        
        if tooltip_text:
            CTkTooltip(self.text_label, tooltip_text)
        
        # Borderless gear icon — no square box, transparent background
        self.btn_edit = ctk.CTkButton(
            self, text="⚙", width=22, height=22,
            corner_radius=6, font=("Segoe UI Symbol", 15),
            fg_color="transparent",
            border_width=0,
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            hover_color="#1A2332",
            command=self._handle_edit, cursor="hand2"
        )
        if self._on_edit:
            self.btn_edit.pack(side="left", padx=(6, 0))
            self.text_label.bind("<Button-1>", lambda e: self._handle_edit())
            self.text_label.configure(cursor="hand2")
        
        self.toggle = LolToggle(self, variable=variable, command=self._on_toggle)
        self.toggle.pack(side="right")
        
        self._user_command = command
        
        if tooltip_text:
            CTkTooltip(self.toggle, tooltip_text)
        
        # Determine icon source and load AFTER all widgets are created
        # (get_icon_async can fire callback synchronously if cached)
        actual_icon_type = icon_type
        actual_icon_id = icon_item_id
        if icon_champion_id:
            actual_icon_type = "champion"
            actual_icon_id = str(icon_champion_id)
        
        if assets and actual_icon_id:
            assets.get_icon_async(
                actual_icon_type, 
                actual_icon_id, 
                lambda img, l=self.icon_label: self._on_icon_loaded(img), 
                size=self._icon_size, 
                widget=self.icon_label
            )
        
        # Initialize icon state based on current variable value
        if self._variable:
            try:
                self._variable.trace_add("write", lambda *args: self.after(10, self._update_icon_state))
            except Exception:
                pass
            self.after(100, self._update_icon_state)
    
    def _on_icon_loaded(self, ctk_img):
        """Called when the async icon load completes. Store color + generate grayscale."""
        self._color_image = ctk_img
        
        # Generate grayscale version from the light image
        try:
            pil_light = ctk_img._light_image if hasattr(ctk_img, '_light_image') else None
            if pil_light:
                gray_pil = ImageOps.grayscale(pil_light).convert("RGBA")
                # Darken it further for the "off" look
                from PIL import ImageEnhance
                gray_pil = ImageEnhance.Brightness(gray_pil).enhance(0.4)
                self._gray_image = ctk.CTkImage(gray_pil, size=self._icon_size)
        except Exception:
            self._gray_image = None
        
        self._update_icon_state()
    
    def _update_icon_state(self):
        """Switch between color (animated) and grayscale icon based on toggle state.
        Also updates the gear button color to match the ON/OFF state."""
        if not self.winfo_exists():
            return
        
        is_on = self._variable.get() if self._variable else False
        gold = get_color("colors.accent.gold", "#C8AA6E")
        muted = get_color("colors.text.muted", "#5B5A56")
        
        if is_on:
            # Show color icon and start pulse
            if self._color_image:
                self.icon_label.configure(image=self._color_image)
            self.text_label.configure(text_color=get_color("colors.text.primary", "#F0E6D2"))
            # Gear icon gets gold color when ON
            if self._on_edit and self.btn_edit.winfo_exists():
                self.btn_edit.configure(text_color=gold)
            self._start_pulse()
        else:
            # Show grayscale icon and stop pulse
            self._stop_pulse()
            if self._gray_image:
                self.icon_label.configure(image=self._gray_image)
            elif self._color_image:
                self.icon_label.configure(image=self._color_image)
            self.text_label.configure(text_color=muted)
            # Gear icon grays out when OFF
            if self._on_edit and self.btn_edit.winfo_exists():
                self.btn_edit.configure(text_color=muted)
    
    def _start_pulse(self):
        """Subtle pulse animation on the icon when automation is ON."""
        self._stop_pulse()  # Clear any existing
        
        def _tick():
            if not self.winfo_exists():
                return
            if not (self._variable and self._variable.get()):
                return
            # Toggle opacity between slightly dim and full
            self._pulse_state = not self._pulse_state
            alpha = 1.0 if self._pulse_state else 0.7
            try:
                self.icon_label.configure(
                    text_color=get_color("colors.accent.gold") if not self._pulse_state else ""
                )
            except Exception:
                pass
            self._pulse_job = self.after(1500, _tick)
        
        self._pulse_job = self.after(1500, _tick)
    
    def _stop_pulse(self):
        """Stop the pulse animation."""
        if self._pulse_job:
            try:
                self.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
        self._pulse_state = True
    
    def _on_toggle(self):
        """Internal toggle handler that updates icon state then calls user command."""
        self._update_icon_state()
        if self._user_command:
            self._user_command()
    
    def _handle_edit(self):
        """Handle edit button click."""
        if self._on_edit:
            self._on_edit()
    
    def set_enabled(self, enabled: bool):
        """Enable or disable this row (used by master switch)."""
        state = "normal" if enabled else "disabled"
        try:
            self.text_label.configure(text_color=
                get_color("colors.text.primary") if enabled 
                else get_color("colors.text.disabled", "#3C3C41")
            )
            if hasattr(self.toggle, 'configure'):
                pass  # LolToggle is a Canvas, doesn't support state
        except Exception:
            pass
    
    def destroy(self):
        """Clean up pulse animation on destroy."""
        self._stop_pulse()
        super().destroy()

