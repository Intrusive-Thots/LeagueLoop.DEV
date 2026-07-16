"""
Settings Page Component
Manages advanced configuration panels, hotkeys, status updates, and links.
"""
import customtkinter as ctk
from ui.components.factory import get_color, get_font, get_radius, make_button, make_card
from ui.components.settings_row import (
    SettingsToggleRow, SettingsSliderRow, SettingsInputRow, SettingsHotkeyRow
)
from ui.ui_shared import CTkTooltip
from core.constants import SECTION_GAP, INNER_GAP, CARD_PAD
from core.version import __version__
from utils.smooth_scroll import apply_smooth_scroll

class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, coordinator, **kwargs):
        super().__init__(
            master, 
            fg_color="transparent",
            **kwargs
        )
        self.coordinator = coordinator
        self.config = coordinator.config
        
        try:
            self._scrollbar.configure(width=6)
        except Exception:
            pass

        # LOBBY & QUEUE
        card_lobby = make_card(self, title="LOBBY & QUEUE", padx=0, pady=(0, SECTION_GAP))
        
        delay_val = float(self.config.get("accept_delay", 2.0))
        self.delay_var = ctk.DoubleVar(value=delay_val)
        
        def _on_delay_slide(value):
            self.config.set("accept_delay", round(value, 1))
            
        self.row_delay = SettingsSliderRow(
            card_lobby,
            label_text="Accept Delay",
            variable=self.delay_var,
            command=_on_delay_slide,
            from_=0,
            to=8,
            number_of_steps=16,
            format_str="{:.1f}s",
            tooltip_text="Delay before auto-accepting a match"
        )
        self.row_delay.pack(fill="x", pady=(0, INNER_GAP))

        # AUTOMATION & BEHAVIOR
        card_auto = make_card(self, title="AUTOMATION & BEHAVIOR", padx=0, pady=(0, SECTION_GAP))
        
        self.tray_var = ctk.BooleanVar(value=bool(self.config.get("run_in_tray", True)))
        
        def _on_tray_toggle():
            self.config.set("run_in_tray", self.tray_var.get())
            
        self.row_tray = SettingsToggleRow(
            card_auto,
            label_text="Run in Tray",
            variable=self.tray_var,
            command=_on_tray_toggle
        )
        self.row_tray.pack(fill="x", pady=(INNER_GAP, 0))

        # SOCIAL & IDENTITY
        card_social = make_card(self, title="SOCIAL & IDENTITY", padx=0, pady=(0, SECTION_GAP))
        
        self.discord_var = ctk.BooleanVar(value=bool(self.config.get("discord_rpc_enabled", True)))
        self.row_discord = SettingsToggleRow(
            card_social,
            label_text="Discord RPC",
            variable=self.discord_var,
            command=lambda: self.config.set("discord_rpc_enabled", self.discord_var.get())
        )
        self.row_discord.pack(fill="x", pady=(0, INNER_GAP))
        
        self.join_vip_var = ctk.BooleanVar(value=bool(self.config.get("auto_join_vip_only", False)))
        self.row_join_vip = SettingsToggleRow(
            card_social,
            label_text="VIP Invites Only",
            variable=self.join_vip_var,
            command=lambda: self.config.set("auto_join_vip_only", self.join_vip_var.get())
        )
        self.row_join_vip.pack(fill="x", pady=(0, INNER_GAP))
        
        self.vip_var = ctk.StringVar(value=self.config.get("vip_invite_list", ""))
        self.row_vip_list = SettingsInputRow(
            card_social,
            label_text="VIP Invite List",
            variable=self.vip_var,
            command=lambda val: self.config.set("vip_invite_list", val.strip()),
            placeholder_text="Enter summoner names, comma separated..."
        )
        self.row_vip_list.pack(fill="x", pady=(0, 0))
        
        # HOTKEYS
        card_hotkeys = make_card(self, title="HOTKEYS", padx=0, pady=(0, SECTION_GAP))
        hotkeys = [
            ("Client Launch", "hotkey_launch_client", "ctrl+shift+l"),
            ("Toggle Auto", "hotkey_toggle_automation", "ctrl+shift+a"),
            ("Find Match", "hotkey_find_match", "ctrl+shift+f"),
        ]
        self.recorders = {}
        for i, (label_text, config_key, default_val) in enumerate(hotkeys):
            pad_bottom = INNER_GAP if i < len(hotkeys) - 1 else 0
            
            def _save_hk(val, key=config_key):
                self.config.set(key, val)
                if hasattr(self.coordinator.master, "on_settings_saved"):
                    self.coordinator.master.on_settings_saved()
                    
            row = SettingsHotkeyRow(
                card_hotkeys,
                label_text=label_text,
                config_key=config_key,
                default_val=self.config.get(config_key, default_val),
                on_change_callback=_save_hk
            )
            row.pack(fill="x", pady=(0, pad_bottom))
            self.recorders[config_key] = row.recorder

        # ABOUT
        card_about = make_card(self, title="ABOUT", padx=0, pady=(0, SECTION_GAP))
        ctk.CTkLabel(card_about, text="League Loop", font=get_font("title", "bold"), text_color=get_color("colors.text.primary")).pack(anchor="w")
        ctk.CTkLabel(card_about, text=f"Version {__version__}", font=get_font("caption"), text_color=get_color("colors.text.muted")).pack(anchor="w", pady=(0, INNER_GAP))
        
        def _open_about():
            from ui.components.about_page import AboutPage
            AboutPage(self.coordinator.master)
        
        btn_about = make_button(card_about, text="Info & Legal", style="ghost", font=get_font("caption", "bold"), width=100, height=24, command=_open_about)
        btn_about.pack(anchor="w")

        def _open_mobile_qr():
            if hasattr(self.coordinator.master, "_show_mobile_qr"):
                self.coordinator.master._show_mobile_qr()
        
        btn_mobile = make_button(card_about, text="Link Mobile Device", style="primary", font=get_font("caption", "bold"), width=150, height=24, command=_open_mobile_qr)
        btn_mobile.pack(anchor="w", pady=(INNER_GAP, 0))

        # PROFILE
        self.profile_frame = make_card(
            self,
            title="PROFILE",
            fg_color=get_color("colors.background.panel"),
            padx=0,
            pady=(0, SECTION_GAP),
            collapsible=True,
            start_collapsed=True
        )

        lbl_status = ctk.CTkLabel(self.profile_frame, text="Custom Status", font=get_font("caption"), text_color=get_color("colors.text.muted"), anchor="w")
        lbl_status.pack(fill="x", padx=CARD_PAD, pady=(0, 2))

        self.entry_status = ctk.CTkEntry(
            self.profile_frame,
            placeholder_text="Set your status...",
            font=get_font("body"),
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            border_color=get_color("colors.border.subtle"),
            height=30,
        )
        self.entry_status.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))
        self.entry_status.bind("<Return>", self._on_status_submit)
        CTkTooltip(self.entry_status, "Press Enter to update your League Client status")

        # Quick Status Presets
        self.preset_frame = ctk.CTkFrame(self.profile_frame, fg_color="transparent")
        self.preset_frame.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))

        presets = [
            ("🚀", "Grinding Ranked"),
            ("🎮", "LeagueLoop ⚙️ https://github.com/Intrusive-Thots/LeagueLoop-Installer"),
            ("🌮", "Eating / Brb"),
            ("💤", "AFK"),
        ]

        for emoji, text in presets:
            btn = ctk.CTkButton(
                self.preset_frame, text=emoji, width=32, height=32,
                corner_radius=get_radius("sm"),
                font=get_font("title"),
                fg_color=get_color("colors.background.panel"),
                hover_color=get_color("colors.state.hover"),
                command=lambda e=emoji, t=text: self._on_quick_status(e, t),
                cursor="hand2"
            )
            btn.pack(side="left", padx=(0, 4))
            CTkTooltip(btn, f"Set status to: {text}")

        apply_smooth_scroll(self)

    def _on_status_submit(self, event=None):
        status_text = self.entry_status.get().strip()
        if status_text:
            self.coordinator._on_quick_status("", status_text)

    def _on_quick_status(self, emoji, text):
        status_str = f"{emoji} {text}".strip() if emoji else text
        self.entry_status.delete(0, "end")
        self.entry_status.insert(0, status_str)
        self.coordinator._on_quick_status(emoji, text)
