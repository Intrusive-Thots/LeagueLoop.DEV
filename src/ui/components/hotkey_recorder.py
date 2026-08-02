import tkinter as tk
import customtkinter as ctk  # type: ignore
import keyboard  # type: ignore

from ui.ui_shared import CTkTooltip  # type: ignore
from ui.components.factory import get_color, get_font  # type: ignore
from ui.components.hover import apply_click_animation  # type: ignore

class HotkeyRecorder(ctk.CTkButton):
    """A button that records keyboard shortcuts when clicked.

    Click to start recording → press your key combo → it captures and displays it.
    """
    _active_recorder = None

    _MODIFIERS_MAP = {
        "left ctrl": "ctrl", "right ctrl": "ctrl",
        "left shift": "shift", "right shift": "shift",
        "left alt": "alt", "right alt": "alt",
        "left windows": "win", "right windows": "win",
        "control_l": "ctrl", "control_r": "ctrl",
        "shift_l": "shift", "shift_r": "shift",
        "alt_l": "alt", "alt_r": "alt",
    }
    _MODIFIER_NAMES = {"ctrl", "shift", "alt", "win"}
    _MODIFIER_ORDER = ["ctrl", "shift", "alt", "win"]

    def __init__(self, master, initial_value="", on_change=None, **kwargs):
        self._hotkey_value = initial_value
        self._recording = False
        self._pressed_keys = set()
        self._hook = None
        self._pulse_job = None
        self._pulse_state = False
        self.on_change = on_change

        super().__init__(
            master,  # type: ignore
            text=initial_value or "Click to set",  # type: ignore
            width=kwargs.pop("width", 140),  # type: ignore
            height=kwargs.pop("height", 28),  # type: ignore
            corner_radius=6,  # type: ignore
            font=get_font("body", "bold"),  # type: ignore
            fg_color=get_color("colors.background.card"),  # type: ignore
            text_color=get_color("colors.text.primary"),  # type: ignore
            border_width=1,  # type: ignore
            border_color=get_color("colors.border.subtle"),  # type: ignore
            hover_color=get_color("colors.state.hover"),  # type: ignore
            command=self._toggle_recording,  # type: ignore
            cursor="hand2",  # type: ignore
            # type: ignore
            **kwargs,
        )
        self._tooltip = CTkTooltip(self, "Click to record a new hotkey")

        # 🎨 Palette: Keyboard Accessibility Focus States
        self._focus_border = get_color("colors.accent.primary", "#0AC8B9")
        self._unfocus_border = get_color("colors.border.subtle")

        apply_click_animation(self, get_color("colors.background.card"), pulse_color=get_color("colors.accent.primary"))

        if hasattr(self, "_canvas"):
            self._canvas.configure(takefocus=1)
            self._canvas.bind("<FocusIn>", self._on_focus, add="+")
            self._canvas.bind("<FocusOut>", self._on_unfocus, add="+")
            self._canvas.bind("<KeyPress-space>", lambda e: self._toggle_recording(), add="+")
            self._canvas.bind("<KeyPress-Return>", lambda e: self._toggle_recording(), add="+")

    def _on_focus(self, event=None):
        if not self._recording:
            self.configure(border_color=self._focus_border, border_width=2)

    def _on_unfocus(self, event=None):
        if not self._recording:
            self.configure(border_color=self._unfocus_border, border_width=1)

    def _toggle_recording(self):
        if self._recording:
            self._stop_recording(cancel=True)
        else:
            self._start_recording()

    def _start_recording(self):
        if HotkeyRecorder._active_recorder and HotkeyRecorder._active_recorder is not self:
            HotkeyRecorder._active_recorder._stop_recording()
        HotkeyRecorder._active_recorder = self

        self._recording = True
        self._pressed_keys = set()
        self.configure(
            text="⏺ Listening...",
            fg_color=get_color("colors.accent.primary"),
            text_color="#ffffff",
            border_color=get_color("colors.accent.primary"),
        )
        if hasattr(self, "_tooltip"):
            self._tooltip.configure(text="Press your desired key combination")
        self._hook = keyboard.on_press(self._on_key_press)
        self._animate_pulse()

    def _animate_pulse(self):
        """Malcolm's Infusion: Pulse animation while recording to indicate active listening."""
        if not self._recording or not self.winfo_exists():
            return

        self._pulse_state = not self._pulse_state
        if self._pulse_state:
            # Dimmed state
            self.configure(fg_color="#A88A4E", border_color="#A88A4E")
        else:
            # Bright state
            self.configure(fg_color=get_color("colors.accent.primary"), border_color=get_color("colors.accent.primary"))

        self._pulse_job = self.after(600, self._animate_pulse)

    def _on_key_press(self, event):
        """Capture key presses and build the hotkey combo string."""
        ev_name = getattr(event, "name", None)
        name = ev_name.lower() if isinstance(ev_name, str) else ""

        # ⚡ Bolt: Use pre-allocated static maps to avoid dictionary allocation overhead on every keystroke
        name = self._MODIFIERS_MAP.get(name, name)
        self._pressed_keys.add(name)

        non_modifiers = self._pressed_keys - self._MODIFIER_NAMES
        if non_modifiers:
            parts = []
            for mod in self._MODIFIER_ORDER:
                if mod in self._pressed_keys:
                    parts.append(mod)
            parts.extend(sorted(non_modifiers))
            combo = "+".join(parts)
            self._hotkey_value = combo
            self.after(50, lambda: self._stop_recording(success=True))

    def _stop_recording(self, success=False, cancel=False):
        if HotkeyRecorder._active_recorder is self:
            HotkeyRecorder._active_recorder = None


        self._recording = False
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        if self._pulse_job is not None:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None

        if cancel:
            # Check if they only pressed modifiers
            non_modifiers = self._pressed_keys - self._MODIFIER_NAMES
            if self._pressed_keys and not non_modifiers:
                # Invalid hotkey (only modifiers)
                self.configure(
                    text="! Needs a key",
                    fg_color=get_color("colors.state.warning", "#E67E22"),
                    text_color="#ffffff",
                    border_color=get_color("colors.state.warning", "#E67E22"),
                )
                if hasattr(self, "_tooltip"):
                    self._tooltip.configure(text="A non-modifier key is required")
                self.after(1200, self._revert_visuals)
                return
            else:
                self._revert_visuals()
                return

        if success:
            # Malcolm's Infusion: Satisfying success flash
            self.configure(
                text=f"✓ {self._hotkey_value}",
                fg_color=get_color("colors.state.success", "#27AE60"),
                text_color="#ffffff",
                border_color=get_color("colors.state.success", "#27AE60"),
            )
            self.after(800, self._revert_visuals)
            if self.on_change:
                self.on_change(self._hotkey_value)
        else:
            self._revert_visuals()

    def _revert_visuals(self):
        if not self.winfo_exists():
            return
        self.configure(
            text=self._hotkey_value or "Click to set",
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            border_color=get_color("colors.border.subtle"),
        )
        if hasattr(self, "_tooltip") and self._tooltip:
            self._tooltip.configure(text="Click to record a new hotkey")

    def get(self):
        return self._hotkey_value

    def destroy(self):
        """Custom destroy with safety guards for CustomTkinter's '_font' bug."""
        if self._hook is not None:
            try:
                keyboard.unhook(self._hook)
                self._hook = None
            except Exception:
                pass

        if not hasattr(self, "_font") or not self.winfo_exists():
            return

        try:
            super().destroy()
        except Exception:
            try:
                tk.Button.destroy(self)
            except Exception:
                pass
