"""
Settings Panel Component
Provides the settings scrollable frame interface displaying configuration inputs for LeagueLoop.
"""

import customtkinter as ctk  # type: ignore
from ui.components.factory import make_card, make_button, get_color, get_font, get_radius
from ui.components.lol_toggle import LolToggle  # type: ignore
from ui.components.hotkey_recorder import HotkeyRecorder  # type: ignore
from ui.theme.token_loader import TOKENS

SECTION_GAP = TOKENS.get("spacing", "lg", 16)
INNER_GAP = TOKENS.get("spacing", "md", 8)
CARD_PAD = TOKENS.get("spacing", "md", 8)
CARD_RADIUS = TOKENS.get("radius", "md", 10)

class SettingsPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, config, on_settings_saved=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.config = config
        self.on_settings_saved = on_settings_saved
        
        self._build_lobby_queue()
        self._build_automation()
        self._build_social()
        self._build_hotkeys()
        self._build_profile()
        self._build_about()
        
    def _build_lobby_queue(self):
        card_lobby = make_card(self, title="LOBBY & QUEUE", padx=0, pady=(0, SECTION_GAP), collapsible=True)
        
        row_delay = ctk.CTkFrame(card_lobby, fg_color="transparent")
        row_delay.pack(fill="x", pady=(0, INNER_GAP))
        ctk.CTkLabel(row_delay, text="Accept Delay", font=get_font("body"), text_color=get_color("colors.text.primary")).pack(side="left")
        
        delay_val = float(self.config.get("accept_delay", 2.0))
        self.delay_var = ctk.DoubleVar(value=delay_val)
        self.lbl_delay_val = ctk.CTkLabel(row_delay, text=f"{delay_val:.1f}s", font=get_font("body", "bold"), text_color=get_color("colors.accent.gold", "#C8AA6E"), width=40)
        self.lbl_delay_val.pack(side="right")
        
        def _on_delay_slide(value):
            self.lbl_delay_val.configure(text=f"{value:.1f}s")
            self.config.set("accept_delay", round(value, 1))
            
        self.slider_delay = ctk.CTkSlider(row_delay, from_=0, to=8, number_of_steps=16, variable=self.delay_var, width=80, fg_color=get_color("colors.background.app"), progress_color=get_color("colors.accent.gold", "#C8AA6E"), button_color=get_color("colors.text.primary", "#F0E6D2"), button_hover_color="#FFFFFF", command=_on_delay_slide)
        self.slider_delay.pack(side="right", padx=(4, 4))
        
    def _build_automation(self):
        card_auto = make_card(self, title="AUTOMATION & BEHAVIOR", padx=0, pady=(0, SECTION_GAP), collapsible=True)
        
        row_tray = ctk.CTkFrame(card_auto, fg_color="transparent")
        row_tray.pack(fill="x", pady=(0, 0))
        ctk.CTkLabel(row_tray, text="Run in Tray", font=get_font("body"), text_color=get_color("colors.text.primary")).pack(side="left")
        
        self.tray_var = ctk.BooleanVar(value=bool(self.config.get("run_in_tray", True)))
        def _on_tray_toggle():
            self.config.set("run_in_tray", self.tray_var.get())
        self.tray_switch = LolToggle(row_tray, variable=self.tray_var, command=_on_tray_toggle)
        self.tray_switch.pack(side="right")

        # ── Stealth Mode ──
        row_stealth = ctk.CTkFrame(card_auto, fg_color="transparent")
        row_stealth.pack(fill="x", pady=(INNER_GAP, 0))
        ctk.CTkLabel(row_stealth, text="Stealth Mode", font=get_font("body"), text_color=get_color("colors.text.primary")).pack(side="left")
        ctk.CTkLabel(row_stealth, text="Restore silently after game", font=get_font("caption"), text_color=get_color("colors.text.disabled")).pack(side="left", padx=(6, 0))

        self.stealth_var = ctk.BooleanVar(value=bool(self.config.get("stealth_mode", False)))
        def _on_stealth_toggle():
            self.config.set("stealth_mode", self.stealth_var.get())
        self.stealth_switch = LolToggle(row_stealth, variable=self.stealth_var, command=_on_stealth_toggle)
        self.stealth_switch.pack(side="right")
        
    def _build_social(self):
        card_social = make_card(self, title="SOCIAL & IDENTITY", padx=0, pady=(0, SECTION_GAP), collapsible=True, start_collapsed=True)
        
        row_discord = ctk.CTkFrame(card_social, fg_color="transparent")
        row_discord.pack(fill="x", pady=(0, INNER_GAP))
        ctk.CTkLabel(row_discord, text="Discord RPC", font=get_font("body"), text_color=get_color("colors.text.primary")).pack(side="left")
        self.discord_var = ctk.BooleanVar(value=bool(self.config.get("discord_rpc_enabled", True)))
        self.discord_switch = LolToggle(row_discord, variable=self.discord_var, command=lambda: self.config.set("discord_rpc_enabled", self.discord_var.get()))
        self.discord_switch.pack(side="right")
        
        row_join_vip = ctk.CTkFrame(card_social, fg_color="transparent")
        row_join_vip.pack(fill="x", pady=(0, INNER_GAP))
        ctk.CTkLabel(row_join_vip, text="VIP Invites Only", font=get_font("body"), text_color=get_color("colors.text.primary")).pack(side="left")
        self.join_vip_var = ctk.BooleanVar(value=bool(self.config.get("auto_join_vip_only", False)))
        self.join_vip_switch = LolToggle(row_join_vip, variable=self.join_vip_var, command=lambda: self.config.set("auto_join_vip_only", self.join_vip_var.get()))
        self.join_vip_switch.pack(side="right")
        
        ctk.CTkLabel(card_social, text="VIP Invite List", font=get_font("caption"), text_color=get_color("colors.text.muted")).pack(anchor="w", pady=(0, 2))
        self.vip_var = ctk.StringVar(value=self.config.get("vip_invite_list", ""))
        self.entry_vip = ctk.CTkEntry(card_social, textvariable=self.vip_var, font=get_font("body"), height=26, fg_color=get_color("colors.background.input", "#0A1220"), border_color=get_color("colors.border.subtle"))
        self.entry_vip.pack(fill="x", pady=(0, 0))
        def _save_vip(*args): self.config.set("vip_invite_list", self.vip_var.get().strip())
        self.entry_vip.bind("<KeyRelease>", _save_vip)
        
    def _build_hotkeys(self):
        card_hotkeys = make_card(self, title="HOTKEYS", padx=0, pady=(0, SECTION_GAP), collapsible=True, start_collapsed=True)
        hotkeys = [
            ("Client Launch", "hotkey_launch_client", "ctrl+shift+l"),
            ("Toggle Auto", "hotkey_toggle_automation", "ctrl+shift+a"),
            ("Find Match", "hotkey_find_match", "ctrl+shift+f"),
        ]
        self.recorders = {}
        for i, (label_text, config_key, default_val) in enumerate(hotkeys):
            row = ctk.CTkFrame(card_hotkeys, fg_color="transparent")
            pad_bottom = INNER_GAP if i < len(hotkeys) - 1 else 0
            row.pack(fill="x", pady=(0, pad_bottom))
            ctk.CTkLabel(row, text=label_text, font=get_font("body"), text_color=get_color("colors.text.primary")).pack(side="top", anchor="w")
            
            def _save_hk(val, key=config_key):
                self.config.set(key, val)
                if self.on_settings_saved:
                    self.on_settings_saved()
                    
            recorder = HotkeyRecorder(row, initial_value=self.config.get(config_key, default_val), width=150, on_change=_save_hk)
            recorder.pack(fill="x", pady=(2,0))
            self.recorders[config_key] = recorder
            
    def _build_profile(self):
        self.profile_frame = make_card(self, title="PROFILE", padx=0, pady=(0, SECTION_GAP), collapsible=True, start_collapsed=True)

        lbl_status = ctk.CTkLabel(self.profile_frame, text="Custom Status", font=get_font("caption"), text_color=get_color("colors.text.muted"), anchor="w")
        lbl_status.pack(fill="x", pady=(0, 2))

        self.entry_status = ctk.CTkEntry(
            self.profile_frame,
            placeholder_text="Set your status...",
            font=get_font("body"),
            fg_color=get_color("colors.background.card"),
            text_color=get_color("colors.text.primary"),
            border_color=get_color("colors.border.subtle"),
            height=30,
        )
        self.entry_status.pack(fill="x", pady=(0, INNER_GAP))
        self.entry_status.bind("<Return>", self._on_status_submit)

        # ── Quick Status Presets ──
        self.preset_frame = ctk.CTkFrame(self.profile_frame, fg_color="transparent")
        self.preset_frame.pack(fill="x", pady=(0, 0))

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
            
    def _build_about(self):
        card_about = make_card(self, title="ABOUT", padx=0, pady=(0, SECTION_GAP), collapsible=True, start_collapsed=True)
        from core.version import __version__
        ctk.CTkLabel(card_about, text="League Loop", font=get_font("title", "bold"), text_color=get_color("colors.text.primary")).pack(anchor="w")
        ctk.CTkLabel(card_about, text=f"Version {__version__}", font=get_font("caption"), text_color=get_color("colors.text.muted")).pack(anchor="w", pady=(0, INNER_GAP))
        
        def _open_about():
            from ui.components.about_page import AboutPage
            AboutPage(self.winfo_toplevel())
        
        btn_about = make_button(card_about, text="Info & Legal", style="ghost", font=get_font("caption", "bold"), width=100, height=24, command=_open_about)
        btn_about.pack(anchor="w")

    def _on_status_submit(self, event=None):
        text = self.entry_status.get().strip()
        engine = getattr(self.winfo_toplevel(), "automation", None)
        if engine and text:
            import threading
            threading.Thread(target=lambda: engine.set_custom_status(text), daemon=True).start()

    def _on_quick_status(self, emoji, text):
        status_text = f"{emoji} {text}"
        self.entry_status.delete(0, "end")
        self.entry_status.insert(0, status_text)
        self._on_status_submit()
        try:
            from ui.components.toast import ToastManager
            ToastManager.get_instance(self.winfo_toplevel()).show(
                message=f"Status set: {text}",
                icon=emoji,
                theme="success",
                duration=2000
            )
        except Exception as e:
            pass

