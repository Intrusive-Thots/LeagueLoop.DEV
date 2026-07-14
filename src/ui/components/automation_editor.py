"""
Automation Editor — Popup window for editing automation parameters.
Opens as a Toplevel dialog with dark theme styling, matching the app's aesthetic.
"""
import tkinter as tk
import customtkinter as ctk

from ui.components.factory import get_color, get_font, get_radius, make_input
from ui.components.champion_input import ChampionInput
from ui.ui_shared import CTkTooltip
from core.constants import SPACING_SM, SPACING_MD, CARD_PAD


class AutomationEditor(ctk.CTkToplevel):
    """Modal popup for editing automation-specific parameters."""

    def __init__(self, master, automation_key: str, config, assets=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.assets = assets
        self._automation_key = automation_key
        self._result = None  # Will be set on save

        # ── Window Setup ──
        self.title(f"Edit: {self._get_display_name()}")
        self.geometry("360x420")
        self.resizable(False, False)
        self.configure(fg_color=get_color("colors.background.app", "#0A1428"))
        
        # Center on parent
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.after(10, self._center_on_parent)

        self._build_ui()

    def _center_on_parent(self):
        """Center the popup over the main window."""
        try:
            parent = self.master.winfo_toplevel()
            px = parent.winfo_rootx() + parent.winfo_width() // 2 - 180
            py = parent.winfo_rooty() + parent.winfo_height() // 2 - 210
            self.geometry(f"360x420+{px}+{py}")
        except Exception:
            pass

    def _get_display_name(self):
        names = {
            "auto_accept": "Auto Accept",
            "priority_picker": "ARAM Picker",
            "auto_join": "Friend Auto-Join",
            "auto_honor": "Auto Honor",
            "skip_stats": "Skip Stats",
            "auto_runes": "Auto Runes",
            "auto_add_played": "Auto-Add Played",
            "auto_ban": "Auto-Ban",
        }
        return names.get(self._automation_key, self._automation_key)

    def _build_ui(self):
        # ── Header ──
        header = ctk.CTkFrame(self, fg_color=get_color("colors.background.card", "#1E2328"), height=50)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text=f"⚙  {self._get_display_name()}",
            font=get_font("title"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            anchor="w"
        ).pack(side="left", padx=SPACING_MD, pady=SPACING_SM)

        # Close button
        ctk.CTkButton(
            header, text="✕", width=28, height=28,
            corner_radius=14, font=get_font("body"),
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover"),
            command=self._on_cancel, cursor="hand2"
        ).pack(side="right", padx=SPACING_SM)

        # ── Body ──
        self.body = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=get_color("colors.text.disabled"),
            scrollbar_button_hover_color=get_color("colors.text.muted"),
        )
        self.body.pack(fill="both", expand=True, padx=SPACING_MD, pady=SPACING_MD)

        # Build form fields based on automation type
        builder = getattr(self, f"_build_{self._automation_key}", None)
        if builder:
            builder()
        else:
            ctk.CTkLabel(
                self.body, text="No additional parameters for this automation.",
                font=get_font("body"),
                text_color=get_color("colors.text.muted")
            ).pack(pady=SPACING_MD)

        # ── Footer ──
        footer = ctk.CTkFrame(self, fg_color="transparent", height=50)
        footer.pack(fill="x", padx=SPACING_MD, pady=(0, SPACING_MD))

        ctk.CTkButton(
            footer, text="Cancel", width=100, height=32,
            font=get_font("body", "bold"),
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            hover_color=get_color("colors.state.hover"),
            command=self._on_cancel
        ).pack(side="right", padx=(SPACING_SM, 0))

        ctk.CTkButton(
            footer, text="Save", width=100, height=32,
            font=get_font("body", "bold"),
            fg_color=get_color("colors.accent.primary"),
            text_color="#ffffff",
            hover_color=get_color("colors.state.hover"),
            command=self._on_save
        ).pack(side="right")

    # ── Per-Automation Form Builders ──

    def _build_auto_accept(self):
        self._add_section_label("Accept Delay")
        self._add_description("How long to wait before accepting a match pop.")

        delay_val = float(self.config.get("accept_delay", 2.0))
        self._delay_var = ctk.DoubleVar(value=delay_val)

        slider_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        slider_frame.pack(fill="x", pady=(SPACING_SM, 0))

        self._delay_display = ctk.CTkLabel(
            slider_frame, text=f"{delay_val:.1f}s",
            font=get_font("body", "bold"),
            text_color=get_color("colors.accent.gold"),
            width=40
        )
        self._delay_display.pack(side="right")

        slider = ctk.CTkSlider(
            slider_frame,
            from_=0, to=8, number_of_steps=16,
            variable=self._delay_var,
            fg_color=get_color("colors.background.card"),
            progress_color=get_color("colors.accent.primary"),
            button_color=get_color("colors.accent.gold"),
            button_hover_color=get_color("colors.text.primary"),
            command=lambda v: self._delay_display.configure(text=f"{v:.1f}s")
        )
        slider.pack(side="left", fill="x", expand=True, padx=(0, SPACING_SM))

    def _build_auto_honor(self):
        self._add_section_label("Honor Strategy")
        self._add_description("Choose how to pick which teammate to honor after each game.")

        strategies = [
            ("random", "Random — Honor a random teammate"),
            ("best_kda", "Best KDA — Honor the player with the best KDA"),
            ("mvp", "MVP — Honor the MVP of the match"),
        ]

        current = self.config.get("honor_strategy", "random")
        self._honor_var = ctk.StringVar(value=current)

        for val, label in strategies:
            radio = ctk.CTkRadioButton(
                self.body, text=label,
                variable=self._honor_var, value=val,
                font=get_font("body"),
                text_color=get_color("colors.text.primary"),
                fg_color=get_color("colors.accent.primary"),
                border_color=get_color("colors.text.muted"),
                hover_color=get_color("colors.state.hover"),
            )
            radio.pack(anchor="w", pady=(SPACING_SM, 0))

    def _build_auto_join(self):
        self._add_section_label("Auto-Join Settings")
        
        self._add_description("When enabled, automatically joins lobbies of online friends.")

        self._vip_only_var = ctk.BooleanVar(
            value=self.config.get("vip_invites_only", False)
        )
        ctk.CTkCheckBox(
            self.body, text="VIP-only mode (only join VIP friends)",
            variable=self._vip_only_var,
            font=get_font("body"),
            text_color=get_color("colors.text.primary"),
            fg_color=get_color("colors.accent.primary"),
            hover_color=get_color("colors.state.hover"),
            border_color=get_color("colors.text.muted"),
        ).pack(anchor="w", pady=(SPACING_MD, 0))

    def _build_auto_ban(self):
        self._add_section_label("Auto-Ban Champions")
        self._add_description(
            "Champions to automatically ban during champion select. "
            "Bans are attempted in priority order (1st → 2nd → 3rd)."
        )

        self._ban_entries = []
        for i in range(1, 4):
            row = ctk.CTkFrame(self.body, fg_color="transparent")
            row.pack(fill="x", pady=(SPACING_SM, 0))

            ctk.CTkLabel(
                row, text=f"Ban {i}:",
                font=get_font("body", "bold"),
                text_color=get_color("colors.text.muted"),
                width=50, anchor="w"
            ).pack(side="left")

            entry = ChampionInput(row, placeholder=f"Champion {i}...", height=28)
            entry.pack(side="left", fill="x", expand=True, padx=(SPACING_SM, 0))

            current_val = self.config.get(f"auto_ban_{i}", "")
            if current_val:
                entry.insert(0, current_val)

            self._ban_entries.append(entry)

    def _build_priority_picker(self):
        self._add_section_label("ARAM Priority Picker")
        self._add_description(
            "Configure your champion priority list in the Config tab's ARAM Priority Grid. "
            "This automation picks the highest win-rate available champion from your list."
        )

        ctk.CTkLabel(
            self.body, text="💡 Tip: Switch to the Config tab to manage your ARAM champion list.",
            font=get_font("caption"),
            text_color=get_color("colors.accent.gold"),
            wraplength=300, anchor="w", justify="left"
        ).pack(anchor="w", pady=(SPACING_MD, 0))

    # ── Helpers ──

    def _add_section_label(self, text):
        ctk.CTkLabel(
            self.body, text=text,
            font=get_font("body", "bold"),
            text_color=get_color("colors.text.primary"),
            anchor="w"
        ).pack(anchor="w", pady=(0, 2))

    def _add_description(self, text):
        ctk.CTkLabel(
            self.body, text=text,
            font=get_font("caption"),
            text_color=get_color("colors.text.muted"),
            wraplength=300, anchor="w", justify="left"
        ).pack(anchor="w", pady=(0, SPACING_SM))

    # ── Save / Cancel ──

    def _on_save(self):
        """Save parameters back to config."""
        key = self._automation_key

        if key == "auto_accept":
            self.config.set("accept_delay", round(self._delay_var.get(), 1))

        elif key == "auto_honor":
            self.config.set("honor_strategy", self._honor_var.get())

        elif key == "auto_join":
            self.config.set("vip_invites_only", self._vip_only_var.get())

        elif key == "auto_ban":
            for i, entry in enumerate(self._ban_entries, 1):
                val = entry.get().strip()
                if hasattr(entry, 'resolved_name') and entry.resolved_name:
                    val = entry.resolved_name
                self.config.set(f"auto_ban_{i}", val)

        # Show toast
        try:
            from ui.components.toast import ToastManager
            ToastManager.get_instance().show(
                f"{self._get_display_name()} settings saved",
                theme="success", icon="✓"
            )
        except Exception:
            pass

        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        """Close without saving."""
        self.grab_release()
        self.destroy()
