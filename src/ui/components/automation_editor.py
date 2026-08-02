"""
Automation Editor — Popup window for editing automation parameters.
Opens as a Toplevel dialog with dark theme styling, matching the app's aesthetic.
"""
import customtkinter as ctk  # type: ignore

from ui.components.factory import get_color, get_font, make_card  # type: ignore
from core.constants import SPACING_SM, SPACING_MD, INNER_GAP  # type: ignore


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
        try:
            self.overrideredirect(True)
        except Exception:
            pass
        self.geometry("380x480")
        self.resizable(False, False)
        self.configure(fg_color=get_color("colors.accent.gold", "#C8AA6E"))
        
        # Center on parent
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.after(10, self._center_on_parent)

        self._build_ui()

    def _center_on_parent(self):
        """Center the popup over the main window."""
        try:
            parent = self.master.winfo_toplevel()
            px = parent.winfo_rootx() + parent.winfo_width() // 2 - 190
            py = parent.winfo_rooty() + parent.winfo_height() // 2 - 240
            self.geometry(f"380x480+{px}+{py}")
        except Exception:
            pass

    def _setup_drag(self, widget):
        """Allow window dragging via the header bar."""
        self._drag_x = 0
        self._drag_y = 0

        def _on_start(e):
            self._drag_x = e.x
            self._drag_y = e.y

        def _on_motion(e):
            dx = e.x - self._drag_x
            dy = e.y - self._drag_y
            new_x = self.winfo_x() + dx
            new_y = self.winfo_y() + dy
            self.geometry(f"+{new_x}+{new_y}")

        widget.bind("<ButtonPress-1>", _on_start)
        widget.bind("<B1-Motion>", _on_motion)

    def _get_display_name(self):
        names = {
            "auto_accept": "Auto Accept",
            "priority_picker": "ARAM Picker",
            "auto_join": "Friend Auto-Join",
            "auto_honor": "Auto Honor",
            "skip_stats": "Skip Stats",
            "auto_runes": "Auto Runes",
            "auto_skin": "Auto Select Skin",
            "auto_add_played": "Auto-Add Played",
            "auto_ban": "Auto-Ban",
        }
        return names.get(self._automation_key, self._automation_key)

    def _build_ui(self):
        # Outer Gold Border Frame
        self.outer_frame = ctk.CTkFrame(
            self,
            fg_color=get_color("colors.background.app", "#0A1428"),
            border_width=1,
            border_color=get_color("colors.accent.gold", "#C8AA6E"),
            corner_radius=0
        )
        self.outer_frame.pack(fill="both", expand=True)

        # ── Header ──
        header = ctk.CTkFrame(self.outer_frame, fg_color=get_color("colors.background.card", "#1E2328"), height=46, corner_radius=0)
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

        self._setup_drag(header)

        # ── Body ──
        self.body = ctk.CTkScrollableFrame(
            self.outer_frame, fg_color="transparent",
            scrollbar_button_color=get_color("colors.text.disabled"),
            scrollbar_button_hover_color=get_color("colors.text.muted"),
        )
        self.body.pack(fill="both", expand=True, padx=SPACING_MD, pady=SPACING_MD)

        # Common setting card for quick icon visibility on main page
        self._build_common_show_icon()

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
        footer = ctk.CTkFrame(self.outer_frame, fg_color="transparent", height=50)
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

    # ── Builders for Automation Settings ──

    def _build_auto_accept(self):
        """Auto Accept settings form."""
        ctk.CTkLabel(
            self.body, text="Accept Delay (Seconds)",
            font=get_font("body", "bold"), text_color=get_color("colors.text.primary")
        ).pack(anchor="w", pady=(0, 4))

        val = float(self.config.get("accept_delay", 2.0))
        self._delay_var = ctk.DoubleVar(value=val)
        
        self.lbl_delay = ctk.CTkLabel(
            self.body, text=f"{val:.1f}s",
            font=get_font("title", "bold"), text_color=get_color("colors.accent.gold", "#C8AA6E")
        )
        self.lbl_delay.pack(anchor="w", pady=(0, 8))

        def _update_delay_label(v):
            self.lbl_delay.configure(text=f"{round(v, 1):.1f}s")

        slider = ctk.CTkSlider(
            self.body, from_=0.0, to=8.0, number_of_steps=16,
            variable=self._delay_var, command=_update_delay_label,
            button_color=get_color("colors.accent.gold", "#C8AA6E")
        )
        slider.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            self.body,
            text="Adds a natural human-like delay before accepting the match pop.",
            font=get_font("caption"), text_color=get_color("colors.text.muted"),
            wraplength=320, justify="left"
        ).pack(anchor="w")

    def _build_auto_join(self):
        """Friend Auto-Join settings form."""
        self._vip_only_var = ctk.BooleanVar(value=bool(self.config.get("vip_invites_only", False)))
        
        sw = ctk.CTkSwitch(
            self.body, text="VIP Invites Only",
            font=get_font("body", "bold"),
            variable=self._vip_only_var,
            progress_color=get_color("colors.accent.gold", "#C8AA6E")
        )
        sw.pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(
            self.body, text="VIP Invite List (Comma Separated)",
            font=get_font("body", "bold"), text_color=get_color("colors.text.primary")
        ).pack(anchor="w", pady=(0, 4))

        self._vip_list_var = ctk.StringVar(value=self.config.get("vip_invite_list", ""))
        entry = ctk.CTkEntry(
            self.body,
            textvariable=self._vip_list_var,
            placeholder_text="e.g. Faker, Doublelift...",
            font=get_font("body"),
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            border_color=get_color("colors.border.subtle")
        )
        entry.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            self.body,
            text="If VIP Invites Only is enabled, Auto-Join will only auto-accept lobby invites from summoners in your VIP list.",
            font=get_font("caption"), text_color=get_color("colors.text.muted"),
            wraplength=320, justify="left"
        ).pack(anchor="w")

    def _build_auto_honor(self):
        """Auto Honor settings form."""
        ctk.CTkLabel(
            self.body, text="Honor Priority Strategy",
            font=get_font("body", "bold"), text_color=get_color("colors.text.primary")
        ).pack(anchor="w", pady=(0, 8))

        self._honor_var = ctk.StringVar(value=self.config.get("honor_strategy", "friends"))

        options = [
            ("friends", "Honor Friends First", "Prioritize party members & friends in your lobby"),
            ("kda", "Best KDA Teammate", "Honor the teammate with highest KDA performance"),
            ("random", "Random Teammate", "Randomly honor a non-premade teammate")
        ]

        for val, label, desc in options:
            rb = ctk.CTkRadioButton(
                self.body, text=label, value=val,
                variable=self._honor_var,
                font=get_font("body", "bold"),
                fg_color=get_color("colors.accent.gold", "#C8AA6E")
            )
            rb.pack(anchor="w", pady=(4, 0))
            ctk.CTkLabel(
                self.body, text=desc,
                font=get_font("caption"), text_color=get_color("colors.text.muted")
            ).pack(anchor="w", padx=(24, 0), pady=(0, 8))

    def _build_skip_stats(self):
        """Skip Stats settings form."""
        ctk.CTkLabel(
            self.body, text="Post-Match Screen Behavior",
            font=get_font("body", "bold"), text_color=get_color("colors.text.primary")
        ).pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(
            self.body,
            text="Automatically skips the end-of-game victory/defeat stats screen and returns immediately to lobby or play again.",
            font=get_font("caption"), text_color=get_color("colors.text.muted"),
            wraplength=320, justify="left"
        ).pack(anchor="w")

    def _build_auto_runes(self):
        """Auto Runes settings form."""
        ctk.CTkLabel(
            self.body, text="Rune Automation Mode",
            font=get_font("body", "bold"), text_color=get_color("colors.text.primary")
        ).pack(anchor="w", pady=(0, 8))

        self._runes_mode_var = ctk.StringVar(value=self.config.get("runes_mode", "highest_winrate"))

        modes = [
            ("highest_winrate", "Highest Winrate Runes", "Automatically applies top winrate runes from OP.GG/Meraki"),
            ("highest_pickrate", "Most Popular Runes", "Applies the most frequently picked rune page")
        ]

        for val, label, desc in modes:
            rb = ctk.CTkRadioButton(
                self.body, text=label, value=val,
                variable=self._runes_mode_var,
                font=get_font("body", "bold"),
                fg_color=get_color("colors.accent.gold", "#C8AA6E")
            )
            rb.pack(anchor="w", pady=(4, 0))
            ctk.CTkLabel(
                self.body, text=desc,
                font=get_font("caption"), text_color=get_color("colors.text.muted")
            ).pack(anchor="w", padx=(24, 0), pady=(0, 8))

    def _build_auto_add_played(self):
        """Auto-Add Played Champions settings form."""
        ctk.CTkLabel(
            self.body, text="ARAM List Auto-Add Position",
            font=get_font("body", "bold"), text_color=get_color("colors.text.primary")
        ).pack(anchor="w", pady=(0, 8))

        self._add_pos_var = ctk.StringVar(value=self.config.get("auto_add_position", "bottom"))

        positions = [
            ("bottom", "Add to Bottom (Low Priority)", "New played champions appended to end of ARAM List"),
            ("top", "Add to Top (High Priority)", "New played champions inserted at start of ARAM List")
        ]

        for val, label, desc in positions:
            rb = ctk.CTkRadioButton(
                self.body, text=label, value=val,
                variable=self._add_pos_var,
                font=get_font("body", "bold"),
                fg_color=get_color("colors.accent.gold", "#C8AA6E")
            )
            rb.pack(anchor="w", pady=(4, 0))
            ctk.CTkLabel(
                self.body, text=desc,
                font=get_font("caption"), text_color=get_color("colors.text.muted")
            ).pack(anchor="w", padx=(24, 0), pady=(0, 8))

    def _build_auto_ban(self):
        """Auto-Ban settings form."""
        ctk.CTkLabel(
            self.body, text="Priority Champion Bans",
            font=get_font("body", "bold"), text_color=get_color("colors.text.primary")
        ).pack(anchor="w", pady=(0, 8))

        self._ban_entries = []
        for i in range(1, 4):
            val = self.config.get(f"auto_ban_{i}", "")
            ctk.CTkLabel(
                self.body, text=f"Ban Preference #{i}",
                font=get_font("caption", "bold"), text_color=get_color("colors.text.muted")
            ).pack(anchor="w", pady=(4, 2))

            entry = ctk.CTkEntry(
                self.body,
                placeholder_text=f"e.g. Yuumi, Shaco, Master Yi",
                font=get_font("body"),
                fg_color=get_color("colors.background.card"),
                text_color=get_color("colors.text.primary"),
                border_color=get_color("colors.border.subtle")
            )
            entry.insert(0, val)
            entry.pack(fill="x", pady=(0, 8))
            self._ban_entries.append(entry)

        self._respect_hovers_var = ctk.BooleanVar(value=bool(self.config.get("auto_ban_respect_hovers", True)))
        sw = ctk.CTkSwitch(
            self.body, text="Respect Teammate Hovers",
            font=get_font("body", "bold"),
            variable=self._respect_hovers_var,
            progress_color=get_color("colors.accent.gold", "#C8AA6E")
        )
        sw.pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(
            self.body,
            text="Will not ban a champion if a teammate in your lobby has selected/hovered it.",
            font=get_font("caption"), text_color=get_color("colors.text.muted"),
            wraplength=320, justify="left"
        ).pack(anchor="w", pady=(2, 0))

    def _build_common_show_icon(self):
        """Standard setting for enabling/disabling the mainpage quick access icon."""
        card = ctk.CTkFrame(
            self.body,
            fg_color=get_color("colors.background.card", "#192230"),
            corner_radius=8,
            border_width=1,
            border_color="#1E2838"
        )
        card.pack(fill="x", pady=(0, SPACING_MD))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=8)

        config_key = f"show_icon_{self._automation_key}"
        val = bool(self.config.get(config_key, True))
        self._show_icon_var = ctk.BooleanVar(value=val)

        lbl = ctk.CTkLabel(
            inner, text="Show Icon on Main Page",
            font=get_font("body", "bold"),
            text_color=get_color("colors.text.primary")
        )
        lbl.pack(side="left")

        sw = ctk.CTkSwitch(
            inner, text="",
            variable=self._show_icon_var,
            progress_color=get_color("colors.accent.gold", "#C8AA6E"),
            width=40
        )
        sw.pack(side="right")

        sub = ctk.CTkLabel(
            card, text="Displays quick action toggle icon below 'Find Match' button on main page",
            font=get_font("caption"),
            text_color=get_color("colors.text.muted")
        )
        sub.pack(anchor="w", padx=12, pady=(0, 8))

    # ── Save / Cancel ──

    def _on_save(self):
        """Save parameters back to config."""
        key = self._automation_key

        if hasattr(self, "_show_icon_var"):
            self.config.set(f"show_icon_{key}", self._show_icon_var.get())

        if key == "auto_accept":
            if hasattr(self, "_delay_var"):
                self.config.set("accept_delay", round(self._delay_var.get(), 1))

        elif key == "auto_honor":
            if hasattr(self, "_honor_var"):
                self.config.set("honor_strategy", self._honor_var.get())

        elif key == "auto_join":
            if hasattr(self, "_vip_only_var"):
                self.config.set("vip_invites_only", self._vip_only_var.get())
            if hasattr(self, "_vip_list_var"):
                self.config.set("vip_invite_list", self._vip_list_var.get().strip())

        elif key == "auto_runes":
            if hasattr(self, "_runes_mode_var"):
                self.config.set("runes_mode", self._runes_mode_var.get())

        elif key == "auto_add_played":
            if hasattr(self, "_add_pos_var"):
                self.config.set("auto_add_position", self._add_pos_var.get())

        elif key == "auto_ban":
            if hasattr(self, "_ban_entries"):
                for i, entry in enumerate(self._ban_entries, 1):
                    val = entry.get().strip()
                    self.config.set(f"auto_ban_{i}", val)
            if hasattr(self, "_respect_hovers_var"):
                self.config.set("auto_ban_respect_hovers", self._respect_hovers_var.get())

        # Notify parent sidebar if active
        if self.master and hasattr(self.master, "_update_all_quick_icons"):
            try:
                self.master._update_all_quick_icons()
            except Exception:
                pass

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
