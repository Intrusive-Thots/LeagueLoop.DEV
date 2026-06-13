import tkinter as tk
import customtkinter as ctk  # type: ignore

from ui.components.factory import get_color, get_font, get_radius, make_button, make_divider  # type: ignore
from ui.ui_shared import CTkTooltip  # type: ignore

CARD_PAD = 10

class SessionHeader(ctk.CTkFrame):
    """Component for displaying the current session status, queue mode, and queue timers."""
    
    def __init__(self, master, config, on_mode_change, on_power_click, initial_mode="ARAM", **kwargs):
        super().__init__(
            master,
            height=64,
            fg_color=get_color("colors.background.card", "#0F1923"),
            corner_radius=get_radius("md"),
            border_width=1,
            border_color="#1A2332",
            **kwargs
        )
        self.pack_propagate(False)
        self.config = config
        self.on_mode_change = on_mode_change
        self.on_power_click = on_power_click
        
        self._setup_ui(initial_mode)
        
    def _setup_ui(self, initial_mode):
        self.inner_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.inner_frame.pack(fill="both", expand=True)
        
        self.inner_frame.grid_columnconfigure(0, weight=3)
        self.inner_frame.grid_columnconfigure(1, weight=1)

        # Queue Mode Label
        self.queue_label = ctk.CTkLabel(
            self.inner_frame,
            text=initial_mode,
            font=get_font("body", "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            anchor="w",
            cursor="hand2"
        )
        self.queue_label.grid(row=0, column=0, padx=(CARD_PAD, 2), pady=(CARD_PAD, 2), sticky="w")
        self.queue_label.bind("<Button-1>", self._show_mode_menu)

        # Power Status Button
        # Initial state is Active
        self.btn_power_status = make_button(
            self.inner_frame, 
            text="▶ Active", 
            style="ghost",
            font=get_font("body", "bold"),
            text_color=get_color("colors.accent.primary"),
            width=80,
            height=24,
            command=self.on_power_click
        )
        self.btn_power_status.grid(row=0, column=1, padx=(2, CARD_PAD), pady=(CARD_PAD, 2), sticky="e")
        
        hk_auto = self.config.get("hotkey_toggle_automation", "ctrl+shift+a").upper()
        CTkTooltip(self.btn_power_status, f"Toggle Automation ({hk_auto})")

        # Time Label
        self.time_label = ctk.CTkLabel(
            self.inner_frame,
            text="Queue: Idle",
            font=get_font("caption"),
            text_color=get_color("colors.text.primary"),
            anchor="w"
        )
        self.time_label.grid(row=1, column=0, padx=(CARD_PAD, 2), pady=(0, CARD_PAD), sticky="w")

        # Estimate / Status Label
        self.estimate_label = ctk.CTkLabel(
            self.inner_frame,
            text="● Connected",
            font=get_font("caption"),
            text_color=get_color("colors.state.success", "#00C853"),
            anchor="e"
        )
        self.estimate_label.grid(row=1, column=1, padx=(2, CARD_PAD), pady=(0, CARD_PAD), sticky="e")

        # Bottom Progress Bar
        make_divider(self, side="top")

        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=3,
            corner_radius=0,
            progress_color=get_color("colors.accent.gold", "#C8AA6E")
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", side="bottom")

    def _show_mode_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg="#1A2332", fg="#F0E6D2",
                       activebackground="#C8AA6E", activeforeground="#0A1428",
                       font=("Segoe UI", 9))
        modes = [
            "Quickplay", "Draft Pick", "Ranked Solo/Duo", "Ranked Flex",
            "ARAM", "ARAM Mayhem", "Arena", "Arena 3v6", "Brawl", "URF", "ARURF",
            "Nexus Blitz", "One For All", "Ultimate Spellbook",
            "TFT Normal", "TFT Ranked"
        ]
        for mode in modes:
            menu.add_command(label=mode, command=lambda m=mode: self.on_mode_change(m))
        menu.tk_popup(event.x_root, event.y_root)

    def update_power_state(self, is_active: bool):
        text = "▶ Active" if is_active else "⏸ Paused"
        color = get_color("colors.accent.primary") if is_active else get_color("colors.text.muted")
        self.btn_power_status.configure(text=text, text_color=color)

    def set_queue_mode(self, text: str):
        self.queue_label.configure(text=text)

    def set_time_text(self, text: str):
        self.time_label.configure(text=text)

    def set_estimate_text(self, text: str, color: str = None):
        self.estimate_label.configure(text=text)
        if color:
            self.estimate_label.configure(text_color=color)

    def set_progress(self, value: float):
        self.progress_bar.set(value)
