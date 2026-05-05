"""
Sidebar navigation and main layout component.
"""
import tkinter as tk
import customtkinter as ctk  # type: ignore
import os
import threading
import time
from PIL import Image  # type: ignore

from utils.logger import Logger  # type: ignore
from utils.path_utils import get_asset_path  # type: ignore
from ui.components.factory import get_color, get_font, get_radius, TOKENS, make_button, make_card  # type: ignore
from ui.ui_shared import CTkTooltip  # type: ignore
from ui.components.priority_grid import PriorityIconGrid  # type: ignore
from ui.components.game_tools.arena_tool import ArenaTool  # type: ignore
from ui.components.game_tools.accounts_tool import AccountsTool  # type: ignore
from ui.components.game_tools.draft_tool import DraftTool  # type: ignore
from ui.components.tab_bar import TabBar  # type: ignore

from ui.components.lol_toggle import LolToggle  # type: ignore
from ui.components.friend_list import FriendPriorityList  # type: ignore
from core.events import EventBus  # type: ignore
from core.constants import (  # type: ignore
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL,
    SECTION_GAP, CARD_PAD, INNER_GAP, CARD_RADIUS, ROW_HEIGHT,
    BTN_HEIGHT, HEADER_HEIGHT, FOOTER_HEIGHT
)

class SidebarWidget(ctk.CTkFrame):
    """The main layout component containing the sidebar navigation, header, and primary content area."""
    def __init__(self, master, toggle_callback, config, lcu=None, assets=None, scraper=None):
        """Initializes the SidebarWidget."""
        self._account_manager = None  # Set externally by main.py
        super().__init__(  # type: ignore
            master, 
            corner_radius=0,  # type: ignore
            fg_color=get_color("colors.background.app"),  # type: ignore
            border_width=1,  # type: ignore
            border_color=get_color("colors.border.subtle")  # type: ignore
        )
        self.toggle_callback = toggle_callback
        self.config = config
        self.lcu = lcu
        self.assets = assets
        self.scraper = scraper
        self.power_state = False

        self.img_on = None
        self.img_off = None
        self._queue_timer_job = None
        self._last_ui_phase = None
        self._current_game_phase = "None"
        self._game_tool_visible = False
        self._accounts_tool_visible = False
        self._stats_visible = False
        self.auto_expanded = True
        self.profile_expanded = False
        self._current_queue_time = 0
        self._estimated_queue_time = 120
        self._body_expanded = True
        
        EventBus.on("lobby_event", self._on_lobby_event)

        self._setup_ui()
        self.after(100, self._load_icons_async)

    def _setup_ui(self):
        # ── Header / Drag Area ──
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=32)
        self.header.pack(fill="x", pady=(SPACING_XS, SPACING_XS), padx=CARD_PAD)
        self.header.pack_propagate(False)
        
        self.lbl_title = ctk.CTkLabel(
            self.header, text="League Loop", 
            font=get_font("title", "bold"), 
            text_color=get_color("colors.text.primary")
        )
        self.lbl_title.pack(side="left", fill="x", expand=True, padx=SPACING_XS)

        # ✕ Close
        self.btn_close = ctk.CTkButton(
            self.header, text="✕", width=20, height=20,
            corner_radius=10, font=get_font("caption"),
            fg_color="transparent", hover_color=get_color("colors.state.danger", "#e81123"),
            command=self.master._on_close, cursor="hand2",
            )
        self.btn_close.pack(side="right", padx=(4, 2))
        CTkTooltip(self.btn_close, "Close Application")
        self.drag_widgets = [self.header, self.lbl_title]

        # Gold accent divider below header (pre-blended: #C8AA6E at ~12% on #091428)
        ctk.CTkFrame(self, height=1, fg_color="#1E1E2D").pack(fill="x", padx=CARD_PAD)

        # ── Collapsible Body ──
        # NOTE: main_body is created here but packed AFTER the footer
        # to ensure proper tkinter pack geometry (footer reserves bottom space first)
        self.main_body = ctk.CTkFrame(self, fg_color="transparent")

        self.power_state = True
        self.var_power = ctk.BooleanVar(value=True)

        # ── 5.1 Tab Navigation ──
        self.tab_frame = ctk.CTkFrame(self.main_body, fg_color="transparent")
        self.tab_frame.pack(fill="x", pady=(0, INNER_GAP))
        
        self._current_tab = "Play"
        
        def _switch_tab(tab_name):
            self._current_tab = tab_name
            
            # Hide everything
            self.session_frame.pack_forget()
            self.action_container.pack_forget()
            self.game_tool_container.pack_forget()
            if getattr(self, "accounts_tool", None): self.accounts_tool.pack_forget()
            
            if getattr(self, "automation_frame", None): self.automation_frame._card.pack_forget()
            if getattr(self, "friend_list", None): self.friend_list.pack_forget()
            
            self.advanced_scroll.pack_forget()
            if hasattr(self, "stats_card"):
                self.stats_card.pack_forget()
            self.spacer.pack_forget()
            
            # Pack based on tab
            if tab_name == "Play":
                self.session_frame.pack(fill="x", pady=(0, SECTION_GAP))
                self.action_container.pack(fill="x", pady=(0, SECTION_GAP))
                
                # Show tools in Play mode
                if getattr(self, "friend_list", None):
                    self.friend_list.pack(fill="x", pady=(0, SECTION_GAP))
                if getattr(self, "_accounts_tool_visible", False) and getattr(self, "accounts_tool", None):
                    self.accounts_tool.pack(fill="x", pady=(0, SECTION_GAP))
                self.spacer.pack(fill="both", expand=True)
                
            elif tab_name == "Actions":
                if getattr(self, "automation_frame", None): self.automation_frame._card.pack(fill="x", pady=(0, SECTION_GAP))
                self.spacer.pack(fill="both", expand=True)
                
            elif tab_name == "Config":
                # Config tab shows game tools
                self.game_tool_container.pack(fill="x", pady=(0, SECTION_GAP))
                self.spacer.pack(fill="both", expand=True)
                
            elif tab_name == "Settings":
                self.advanced_scroll.pack(fill="both", expand=True, pady=(0, SPACING_XS))
                if getattr(self, "_stats_visible", False):
                    if hasattr(self, "stats_card"):
                        self.stats_card.pack(fill="x", pady=(0, SECTION_GAP))
                    
        self.switch_tab = _switch_tab
        
        self.tab_bar = TabBar(
            self.tab_frame,
            tabs=["Play", "Actions", "Config", "Settings"],
            default_tab=None,
            command=self.switch_tab
        )
        self.tab_bar.pack(fill="x")

        from ui.components.session_header import SessionHeader  # type: ignore

        # ── Session Info Block (always visible) ──
        self.session_header = SessionHeader(
            self.main_body,
            config=self.config,
            on_mode_change=self._on_mode_change,
            on_power_click=self._on_power_click,
            initial_mode=self.config.get("aram_mode", "ARAM")
        )
        self.session_header.pack(fill="x", pady=(0, SECTION_GAP))
        
        # Backward compatibility for other methods
        self.queue_label = self.session_header.queue_label
        self.time_label = self.session_header.time_label
        self.estimate_label = self.session_header.estimate_label
        self.progress_bar = self.session_header.progress_bar
        self.btn_power_status = self.session_header.btn_power_status
        self.session_frame = self.session_header

        # ── Action Buttons ──
        self.action_container = ctk.CTkFrame(
            self.main_body,
            fg_color=get_color("colors.background.card", "#0F1923"),
            corner_radius=CARD_RADIUS,
            border_width=1,
            border_color="#1A2332"
        )
        self.action_container.pack(fill="x", pady=(0, SECTION_GAP))

        self.btn_frame = ctk.CTkFrame(self.action_container, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=CARD_PAD, pady=CARD_PAD)

        # Session Block relocated above self.action_container

        # ── Find Match / Quick Actions Container ──
        self.queue_actions_container = ctk.CTkFrame(self.btn_frame, fg_color="transparent")
        self.queue_actions_container.pack(fill="x", pady=0)

        # ── Find Match (primary action) ──
        self.btn_find_match = make_button(
            self.queue_actions_container, 
            text="▶  Find Match",
            style="primary",
            font=get_font("body", "bold"), 
            height=BTN_HEIGHT,
            border_width=1,
            border_color=get_color("colors.accent.primary", "#F0E6D2"),
            command=self._find_match
        )
        self.btn_find_match.pack(fill="x", pady=0)
        hk_find = self.config.get("hotkey_find_match", "ctrl+shift+f").upper()
        CTkTooltip(self.btn_find_match, f"Start or Cancel Matchmaking ({hk_find})")

        # ── Quick Actions Row (2-column grid, fixed height) ──
        self.quick_actions_frame = ctk.CTkFrame(
            self.queue_actions_container,
            height=BTN_HEIGHT,
            fg_color="transparent"
        )
        # Starts hidden — revealed dynamically during Matchmaking/ChampSelect
        self.quick_actions_frame.pack_propagate(False)
        self.quick_actions_frame.grid_columnconfigure((0, 1), weight=1)

        self.requeue_button = make_button(
            self.quick_actions_frame,
            text="Requeue",
            style="primary",
            font=get_font("body", "bold"),
            height=BTN_HEIGHT,
            border_width=1,
            border_color=get_color("colors.accent.primary", "#F0E6D2"),
            command=self._force_requeue,
        )
        CTkTooltip(self.requeue_button, "Cancel and re-enter matchmaking queue")

        self.dodge_button = make_button(
            self.quick_actions_frame,
            text="Dodge",
            style="secondary",
            font=get_font("body", "bold"),
            height=32,
            border_width=1,
            border_color=get_color("colors.accent.primary", "#F0E6D2"),
            command=self._force_dodge,
        )
        CTkTooltip(self.dodge_button, "Force quit the client to dodge the lobby")

        self.play_again_button = make_button(
            self.queue_actions_container,
            text="🔄 Play Again",
            style="primary",
            font=get_font("body", "bold"),
            height=BTN_HEIGHT,
            border_width=1,
            border_color=get_color("colors.accent.primary", "#F0E6D2"),
            command=self._play_again
        )
        CTkTooltip(self.play_again_button, "Return to lobby and play again")

        # ── Launch Client ──
        self.btn_launch_client = make_button(
            self.btn_frame,
            text="🚀 Launch Client",
            style="secondary",
            font=get_font("body", "bold"),
            height=BTN_HEIGHT,
            command=lambda: self.master._hotkey_launch_client() if hasattr(self.master, "_hotkey_launch_client") else None
        )
        self.btn_launch_client.pack(fill="x", pady=(INNER_GAP, 0))
        hk_launch = self.config.get("hotkey_launch_client", "ctrl+shift+l").upper()
        CTkTooltip(self.btn_launch_client, f"Open the Riot Client and start League ({hk_launch})")

        # (Divider removed — card containers provide visual separation)

        # ── Toggles Section (Automation) ──
        self.automation_frame = make_card(
            self.main_body,
            title="AUTOMATION",
            padx=0,
            pady=(0, SECTION_GAP),
            collapsible=True,
            start_collapsed=False
        )
        
        # Inject custom icon header frame into the card's header
        self.icon_header_frame = ctk.CTkFrame(self.automation_frame._header, fg_color="transparent")
        self.icon_header_frame.pack(side="right", padx=(0, INNER_GAP))
        
        # Bind the click events to the card's toggle controller so clicking icons collapses the card
        def _bind_toggle(widget):
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", self.automation_frame._toggle_controller.toggle)
            
        _bind_toggle(self.icon_header_frame)
        
        self.hdr_icon_honor = ctk.CTkLabel(self.icon_header_frame, text="", width=16)
        self.hdr_icon_auto_join = ctk.CTkLabel(self.icon_header_frame, text="", width=16)
        self.hdr_icon_priority = ctk.CTkLabel(self.icon_header_frame, text="", width=16)
        self.hdr_icon_accept = ctk.CTkLabel(self.icon_header_frame, text="", width=16)
        self.hdr_icon_skip_stats = ctk.CTkLabel(self.icon_header_frame, text="", width=16)
        self.hdr_icon_auto_runes = ctk.CTkLabel(self.icon_header_frame, text="", width=16)
        
        for w in (self.hdr_icon_honor, self.hdr_icon_auto_join, self.hdr_icon_priority, self.hdr_icon_accept, self.hdr_icon_skip_stats, self.hdr_icon_auto_runes):
            _bind_toggle(w)

        if getattr(self, "assets", None):
            self.assets.get_icon_async("item", "3105", lambda img, l=self.hdr_icon_honor: l.configure(image=img) if l.winfo_exists() else None, size=(16, 16), widget=self.hdr_icon_honor)
            self.assets.get_icon_async("item", "3109", lambda img, l=self.hdr_icon_auto_join: l.configure(image=img) if l.winfo_exists() else None, size=(16, 16), widget=self.hdr_icon_auto_join)
            self.assets.get_icon_async("item", "2052", lambda img, l=self.hdr_icon_priority: l.configure(image=img) if l.winfo_exists() else None, size=(16, 16), widget=self.hdr_icon_priority)
            self.assets.get_icon_async("item", "2420", lambda img, l=self.hdr_icon_accept: l.configure(image=img) if l.winfo_exists() else None, size=(16, 16), widget=self.hdr_icon_accept)
            self.assets.get_icon_async("item", "3111", lambda img, l=self.hdr_icon_skip_stats: l.configure(image=img) if l.winfo_exists() else None, size=(16, 16), widget=self.hdr_icon_skip_stats)
            self.assets.get_icon_async("item", "3340", lambda img, l=self.hdr_icon_auto_runes: l.configure(image=img) if l.winfo_exists() else None, size=(16, 16), widget=self.hdr_icon_auto_runes)
        
        TOGGLE_ROW_HEIGHT = 28

        from ui.components.toggle_row import ToggleRow  # type: ignore

        # Auto Accept
        self.var_accept = ctk.BooleanVar(value=self.config.get("auto_accept", True))
        self.row_accept = ToggleRow(
            self.automation_frame, label_text="Auto Accept", variable=self.var_accept,
            command=self._on_toggle_accept, tooltip_text="Automatically accepts match queue pops",
            icon_item_id="2420", assets=self.assets, height=TOGGLE_ROW_HEIGHT
        )
        self.row_accept.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))

        # ARAM Picker
        self.var_priority = ctk.BooleanVar(value=self.config.get("priority_picker", {}).get("enabled", False))
        self.row_priority = ToggleRow(
            self.automation_frame, label_text="ARAM Picker", variable=self.var_priority,
            command=self._on_toggle_priority, tooltip_text="Attempts to pick highest available champion from ARAM List",
            icon_item_id="2052", assets=self.assets, height=TOGGLE_ROW_HEIGHT
        )
        self.row_priority.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))
        
        # Friend Auto-Join
        self.var_auto_join = ctk.BooleanVar(value=self.config.get("auto_join_enabled", True))
        self.row_auto_join = ToggleRow(
            self.automation_frame, label_text="Friend Auto-Join", variable=self.var_auto_join,
            command=self._on_toggle_auto_join, tooltip_text="Automatically joins available friend lobbies",
            icon_item_id="3109", assets=self.assets, height=TOGGLE_ROW_HEIGHT
        )
        self.row_auto_join.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))

        # Auto Honor
        self.var_auto_honor = ctk.BooleanVar(value=self.config.get("auto_honor_enabled", False))
        self.row_auto_honor = ToggleRow(
            self.automation_frame, label_text="Auto Honor", variable=self.var_auto_honor,
            command=self._on_toggle_auto_honor, tooltip_text="Automatically honors a teammate after each game",
            icon_item_id="3105", assets=self.assets, height=TOGGLE_ROW_HEIGHT
        )
        self.row_auto_honor.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))

        # Skip Stats
        self.var_skip_stats = ctk.BooleanVar(value=self.config.get("skip_stats_enabled", True))
        self.row_skip_stats = ToggleRow(
            self.automation_frame, label_text="Skip Stats", variable=self.var_skip_stats,
            command=self._on_toggle_skip_stats, tooltip_text="Automatically skips the post-match stats screen",
            icon_item_id="3111", assets=self.assets, height=TOGGLE_ROW_HEIGHT
        )
        self.row_skip_stats.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))

        # Auto Runes
        self.var_auto_runes = ctk.BooleanVar(value=self.config.get("auto_runes_enabled", False))
        self.row_auto_runes = ToggleRow(
            self.automation_frame, label_text="Auto Runes", variable=self.var_auto_runes,
            command=self._on_toggle_auto_runes, tooltip_text="Automatically equips recommended runes for your champion",
            icon_item_id="3340", assets=self.assets, height=TOGGLE_ROW_HEIGHT
        )
        self.row_auto_runes.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        # Honor Strategy
        row_honor = ctk.CTkFrame(self.automation_frame, fg_color="transparent")
        row_honor.pack(fill="x", padx=CARD_PAD, pady=(INNER_GAP, 0))
        ctk.CTkLabel(row_honor, text="Honor Strategy", font=get_font("body"), text_color=get_color("colors.text.primary")).pack(side="top", anchor="w")
        
        self.honor_var = ctk.StringVar(value=self.config.get("honor_strategy", "random"))
        def _on_honor_change(val):
            self.config.set("honor_strategy", val)
        self.honor_select = ctk.CTkOptionMenu(row_honor, values=["random", "best_kda", "mvp"], variable=self.honor_var, font=get_font("body", "bold"), fg_color=get_color("colors.background.app"), button_color="#1A2733", button_hover_color=get_color("colors.state.hover"), dropdown_fg_color=get_color("colors.background.app"), dropdown_hover_color=get_color("colors.state.hover"), dropdown_font=get_font("caption"), command=_on_honor_change, height=24)
        self.honor_select.pack(fill="x", pady=(4,0))

        self._update_auto_header()
        
        # (Divider removed — card containers provide visual separation)

        # ── Game Tool Module Container ──
        # This container holds the active game-mode-specific tool.
        # Currently only the ARAM Priority Grid is implemented;
        # future modules (Draft helper, Arena planner, etc.) will slot in here.
        self.game_tool_container = ctk.CTkFrame(self.main_body, fg_color="transparent")
        # Starts HIDDEN — shown conditionally by _update_game_tool_visibility()

        # ── Game Tool Modules ──
        self.priority_grid = PriorityIconGrid(self.game_tool_container, self.config, self.assets)
        self.arena_tool = ArenaTool(self.game_tool_container, self.config, self.assets)
        self.draft_tool = DraftTool(self.game_tool_container, self.config, self.assets)
        
        self._update_game_tool_visibility(self.config.get("aram_mode", "ARAM"))
        
        # ── Friend Auto-Join List ──
        self.friend_list = FriendPriorityList(self.main_body, config=self.config, lcu=self.lcu)

        # ── Accounts Tool ──
        # Placeholder — instantiated properly once account_manager is injected from main.py
        self.accounts_tool = None

        # UI status and dummy stats stripped for cleaner layout

        from ui.components.settings_row import SettingsToggleRow, SettingsSliderRow  # type: ignore

        # ── Advanced Settings Tab Content ──
        self.advanced_scroll = ctk.CTkScrollableFrame(self.main_body, fg_color="transparent")
        
        # LOBBY & QUEUE
        card_lobby = make_card(self.advanced_scroll, title="LOBBY & QUEUE", padx=0, pady=(0, SECTION_GAP))
        
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
        card_auto = make_card(self.advanced_scroll, title="AUTOMATION & BEHAVIOR", padx=0, pady=(0, SECTION_GAP))
        
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
        card_social = make_card(self.advanced_scroll, title="SOCIAL & IDENTITY", padx=0, pady=(0, SECTION_GAP))
        
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
        
        from ui.components.settings_row import SettingsInputRow, SettingsHotkeyRow  # type: ignore

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
        card_hotkeys = make_card(self.advanced_scroll, title="HOTKEYS", padx=0, pady=(0, SECTION_GAP))
        hotkeys = [
            ("Client Launch", "hotkey_launch_client", "ctrl+shift+l"),
            ("Toggle Auto", "hotkey_toggle_automation", "ctrl+shift+a"),
            ("Find Match", "hotkey_find_match", "ctrl+shift+f"),
            ("Omnibar", "hotkey_omnibar", "ctrl+k"),
        ]
        self.recorders = {}
        for i, (label_text, config_key, default_val) in enumerate(hotkeys):
            pad_bottom = INNER_GAP if i < len(hotkeys) - 1 else 0
            
            def _save_hk(val, key):
                self.config.set(key, val)
                if hasattr(self.master, "on_settings_saved"):
                    self.master.on_settings_saved()
                    
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
        card_about = make_card(self.advanced_scroll, title="ABOUT", padx=0, pady=(0, SECTION_GAP))
        from core.version import __version__
        ctk.CTkLabel(card_about, text="League Loop", font=get_font("title", "bold"), text_color=get_color("colors.text.primary")).pack(anchor="w")
        ctk.CTkLabel(card_about, text=f"Version {__version__}", font=get_font("caption"), text_color=get_color("colors.text.muted")).pack(anchor="w", pady=(0, INNER_GAP))
        
        def _open_about():
            from ui.components.about_page import AboutPage
            AboutPage(self.master)
        
        btn_about = make_button(card_about, text="Info & Legal", style="ghost", font=get_font("caption", "bold"), width=100, height=24, command=_open_about)
        btn_about.pack(anchor="w")

        # ── Profile Section (Moved into Advanced Scroll) ──
        self.profile_frame = make_card(
            self.advanced_scroll,
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

        # ── Quick Status Presets ──
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

        # ── Action Log (Bottom) ──
        self.spacer = ctk.CTkFrame(self.main_body, fg_color="transparent")
        self.spacer.pack(fill="both", expand=True)

        # ── Lobby Stats (Hidden initially, packed before spacer when shown) ──
        self.stats_content = make_card(
            self.main_body, 
            title="LIVE LOBBY STATS",
            collapsible=True,
            start_collapsed=False,
            padx=0,
            pady=0
        )
        self.stats_card = self.stats_content._card
        self.stats_card.pack_forget()

        # ── Fixed Footer (pinned to bottom of sidebar, never clips) ──
        # IMPORTANT: Footer must be packed BEFORE main_body to reserve bottom space
        self.footer = ctk.CTkFrame(self, fg_color="transparent", height=FOOTER_HEIGHT)
        self.footer.pack(fill="x", side="bottom", padx=CARD_PAD, pady=(0, INNER_GAP))
        self.footer.pack_propagate(False)

        ctk.CTkFrame(self.footer, height=1, fg_color=get_color("colors.border.subtle")).pack(fill="x", side="top")

        action_row = ctk.CTkFrame(self.footer, fg_color="transparent")
        action_row.pack(fill="x", padx=SPACING_SM, pady=(SPACING_SM, 0))

        self.lbl_action = ctk.CTkLabel(
            action_row, text="Waiting for client...",
            font=get_font("caption"),
            text_color=get_color("colors.text.muted"),
            wraplength=170, anchor="w"
        )
        self.lbl_action.pack(side="left", fill="x", expand=True)

        self.btn_clear_log = ctk.CTkButton(
            action_row, text="✕", width=18, height=18,
            corner_radius=9, font=get_font("caption"),
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover", "#e81123"),
            command=self._clear_action_log, cursor="hand2",
            )
        self.btn_clear_log.pack(side="right", padx=(4, 0))
        CTkTooltip(self.btn_clear_log, "Clear Log")

        # NOW pack main_body to fill remaining space between header and footer
        self.main_body.pack(fill="both", expand=True, padx=CARD_PAD, pady=(0, SPACING_XS))

        # Initialize tab state — hide Configure and Advanced widgets
        self.switch_tab("Play")

    # ── Account Manager Injection ──
    def set_account_manager(self, account_manager):
        """Called from main.py after sidebar is built to inject the AccountManager."""
        self._account_manager = account_manager
        if self.accounts_tool is not None:
            self.accounts_tool.destroy()
        self.accounts_tool = AccountsTool(
            self.main_body, account_manager, lcu=self.lcu
        )
        # Start hidden — visibility controlled by update_accounts_tool_visibility()
        self._accounts_tool_visible = False

    def update_accounts_tool_visibility(self, lcu_connected: bool = False):
        """Show accounts tool only when Riot Client is running but user is NOT logged in.
        
        Visible when: Riot Client running AND LCU disconnected (login screen).
        Hidden when:  LCU connected (logged in) OR Riot Client not running.
        """
        if self.accounts_tool is None or not self.winfo_exists():
            return

        # Check if Riot Client is actually running
        riot_running = False
        if getattr(self, "_account_manager", None):
            riot_running = self._account_manager.riot_client.is_riot_client_running()

        should_show = riot_running and not lcu_connected

        self._accounts_tool_visible = should_show
        
        # Toggle Launch Client Button
        if hasattr(self, "btn_launch_client"):
            if not lcu_connected and not riot_running:
                if not bool(self.btn_launch_client.winfo_manager()):
                    # SPACING_SM from tokens or INNER_GAP
                    from .theme.token_loader import TOKENS
                    self.btn_launch_client.pack(fill="x", pady=(TOKENS.get("spacing", "sm", 4), 0))
            else:
                if bool(self.btn_launch_client.winfo_manager()):
                    self.btn_launch_client.pack_forget()

        if hasattr(self, "switch_tab"):
            self.switch_tab(self._current_tab)

    # ── Callbacks ──
    def _load_icons_async(self):
        if not self.winfo_exists(): return  # type: ignore
        try:
            idle_path = get_asset_path("assets/icon_idle.png")
            active_path = get_asset_path("assets/icon_active.png")
            if os.path.exists(idle_path):
                self.img_off = ctk.CTkImage(Image.open(idle_path), size=(56, 56))
            if os.path.exists(active_path):
                self.img_on = ctk.CTkImage(Image.open(active_path), size=(56, 56))
        except Exception as e:
            print(f"Icon load error: {e}")

    def _toggle_body_collapse(self):
        self._body_expanded = not self._body_expanded
        h = self.master.winfo_height()
        if self._body_expanded:
            self.header.pack_configure(fill="x", pady=(SPACING_SM, SPACING_MD), padx=SPACING_MD)
            self.lbl_title.pack(side="left")
            self.btn_close.pack(side="right", padx=(4, 2))

            self.btn_minimize.pack(side="right", padx=(4, 1))
            self.btn_collapse.pack(side="right", padx=(4, 1))
            self.main_body.pack(fill="both", expand=True)
            self.btn_collapse.configure(text="◀")
            self.master.geometry(f"200x{h}")
            if hasattr(self, 'tooltip_collapse'):
                self.tooltip_collapse.configure(text="Collapse Sidebar")
        else:
            self.main_body.pack_forget()
            self.btn_close.pack_forget()

            self.btn_minimize.pack_forget()
            self.lbl_title.pack_forget()
            
            self.header.pack_configure(fill="both", expand=True, padx=0, pady=0)
            self.btn_collapse.pack_configure(side="top", pady=SPACING_MD, padx=0)
            
            self.btn_collapse.configure(text="▶")
            self.master.geometry("44x44")
            if hasattr(self, 'tooltip_collapse'):
                self.tooltip_collapse.configure(text="Expand Sidebar")
            
    def _minimize_window(self):
        """Minimize via Win32 API — tkinter's iconify() is blocked by overrideredirect(True)."""
        import ctypes
        SW_MINIMIZE = 6
        hwnd = ctypes.windll.user32.GetParent(self.master.winfo_id())
        if hwnd == 0:
            hwnd = self.master.winfo_id()
        ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)




    def _update_game_tool_visibility(self, mode):
        if hasattr(self, "priority_grid"):
            self.priority_grid.pack_forget()
        if hasattr(self, "arena_tool"):
            self.arena_tool.pack_forget()
        if hasattr(self, "draft_tool"):
            self.draft_tool.pack_forget()

        if mode in ["ARAM", "ARAM Mayhem"]:
            if hasattr(self, "priority_grid"):
                self.priority_grid.pack(fill="x", pady=(0, SPACING_MD), padx=0)
        elif mode == "Arena":
            if hasattr(self, "arena_tool"):
                self.arena_tool.pack(fill="x", pady=(0, SPACING_MD), padx=0)
        elif mode in ["Draft Pick", "Ranked Solo/Duo", "Ranked Flex", "Quickplay"]:
            if hasattr(self, "draft_tool"):
                self.draft_tool.pack(fill="x", pady=(0, SPACING_MD), padx=0)

    def _on_mode_change(self, new_mode):
        self.config.set("aram_mode", new_mode)
        if self.scraper:
            self.scraper.set_mode(new_mode)
        if hasattr(self, "queue_label"):
            self.queue_label.configure(text=new_mode)
        self._update_game_tool_visibility(new_mode)

    def _on_lobby_event(self, lobby_data):
        if not self.winfo_exists() or not lobby_data:
            return
            
        queue_id = lobby_data.get("gameConfig", {}).get("queueId")
        if not queue_id:
            return
            
        try:
            queue_id = int(queue_id)
        except ValueError:
            return
            
        mode_map = {
            400: "Draft Pick",
            490: "Quickplay",
            420: "Ranked Solo/Duo",
            440: "Ranked Flex",
            450: "ARAM",
            2400: "ARAM Mayhem",
            1700: "Arena",
            2300: "Brawl",
            900: "URF",
            1010: "ARURF",
            1300: "Nexus Blitz",
            1020: "One For All",
            1400: "Ultimate Spellbook",
            1090: "TFT Normal",
            1100: "TFT Ranked",
        }
        
        detected_mode = mode_map.get(queue_id)
        if detected_mode:
            current_mode = self.config.get("aram_mode", "ARAM")
            if detected_mode != current_mode:
                self.after(0, lambda: self._on_mode_change(detected_mode))

    # ── Handlers ──
    def on_lcu_connection_changed(self, connected: bool):
        """Handles LCU connection state changes."""
        if not self.winfo_exists(): return
        if connected:
            pass # Launch client visibility handled by update_accounts_tool_visibility
        else:
            self._hide_quick_actions()
            self._stop_local_queue_timer()
            
            self.time_label.configure(text="Disconnected", text_color=get_color("colors.state.danger", "#ff4444"))
            self.estimate_label.configure(text="● Offline", text_color=get_color("colors.state.danger", "#ff4444"))

        # Show/hide accounts tool and launch button based on login state
        self.update_accounts_tool_visibility(lcu_connected=connected)

    def set_power_state(self, state: bool):
        """Pure visual/logical toggle without user-cancel side effects."""
        if getattr(self, "power_state", None) == state: return
        self.power_state = state
        try:
            self.var_power.set(state)
        except Exception as e:
            from utils.logger import Logger  # type: ignore
            Logger.debug("UI", f"State sync error: {e}")

        if hasattr(self, "btn_power_status") and self.btn_power_status.winfo_exists():
            if state:
                self.btn_power_status.configure(text="▶ Active", text_color=get_color("colors.accent.primary"))
            else:
                self.btn_power_status.configure(text="⏸ Paused", text_color=get_color("colors.text.muted"))

        if self.toggle_callback:
            self.toggle_callback(self.power_state)

    def _on_power_click(self):
        """User clicks power button (may cancel search if active)."""
        if hasattr(self, "var_power"):
            new_state = self.var_power.get()
        else:
            new_state = not getattr(self, "power_state", False)
            
        self.set_power_state(new_state)

        if self.toggle_callback:
            def _check_and_cancel():
                state_req = self.lcu.request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state")
                state_data = state_req.json() if state_req and state_req.status_code == 200 else {}
                
                if state_data.get("searchState") == "Searching":
                    self.lcu.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")
                    self.after(0, lambda: self.update_action_log("Matchmaking Cancelled."))
                    if getattr(self, "power_state", False):
                        self.after(0, lambda: self.set_power_state(False))
            threading.Thread(target=_check_and_cancel, daemon=True).start()

    def _get_queue_id_for_mode(self, mode: str):
        """Dynamically resolve the queue ID from the client."""
        mode_map = {
            "Quickplay": 490,
            "Draft Pick": 400,
            "Ranked Solo/Duo": 420,
            "Ranked Flex": 440,
            "ARAM": 450,
            "ARAM Mayhem": 2400,
            "Arena": 1700,
            "Brawl": 2300,
            "URF": 900,
            "ARURF": 1010,
            "Nexus Blitz": 1300,
            "One For All": 1020,
            "Ultimate Spellbook": 1400,
            "TFT Normal": 1090,
            "TFT Ranked": 1100,
        }
        if mode in mode_map:
            return mode_map[mode]

        try:
            queues_req = self.lcu.request("GET", "/lol-game-queues/v1/queues")
            if queues_req and queues_req.status_code == 200:
                queues = queues_req.json()
                
                if mode == "ARAM Mayhem":
                    for q in queues:
                        if q.get("isCustom"): continue
                        name = q.get("name", "").lower()
                        desc = q.get("description", "").lower()
                        if "mayhem" in name or "mayhem" in desc:
                            return int(q.get("id"))

                if mode == "Brawl":
                    for q in queues:
                        if q.get("isCustom"): continue
                        name = q.get("name", "").lower()
                        desc = q.get("description", "").lower()
                        if "brawl" in name or "brawl" in desc:
                            return int(q.get("id"))

                # ⚡ Bolt: Hoist the target string's normalization outside the loop
                # to prevent redundant string allocations on every iteration.
                if isinstance(mode, str):
                    mode_lower = mode.lower()
                    for q in queues:
                        if q.get("isCustom"): continue
                        q_name = q.get("name")
                        if isinstance(q_name, str):
                            if mode_lower in q_name.lower():
                                return int(q.get("id"))
        except Exception:
            pass
        return 450 # Default to ARAM

    def _find_match(self):
        """Aggressive matchmaking: Stay in the lobby tab, just change the queue."""
        if not self.lcu: return

        mode = self.config.get("aram_mode", "ARAM")
        self.update_action_log(f"Initiating {mode}...")

        def _execute_sync():
            import time
            # 1. Check if already searching
            state_req = self.lcu.request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state")
            state_data = state_req.json() if state_req and state_req.status_code == 200 else {}
            
            if state_data.get("searchState") == "Searching":
                self.lcu.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")
                self.after(0, lambda: self.update_action_log("Matchmaking Cancelled."))
                if getattr(self, "power_state", False):
                    self.after(0, self._on_power_click)
                return

            # 2. Resolve Queue ID
            target_q_id = self._get_queue_id_for_mode(mode)

            # 3. Check current lobby
            lobby_req = self.lcu.request("GET", "/lol-lobby/v2/lobby")
            in_lobby = lobby_req and lobby_req.status_code == 200

            should_create = True

            if in_lobby:
                try:
                    data = lobby_req.json()
                    current_q = data.get("gameConfig", {}).get("queueId")

                    if current_q == target_q_id:
                        should_create = False
                    else:
                        self.lcu.request(
                            "DELETE", "/lol-lobby/v2/lobby/matchmaking/search"
                        )
                        time.sleep(0.5)
                        self.lcu.request("DELETE", "/lol-lobby/v2/lobby")
                        time.sleep(0.5)
                except Exception:
                    should_create = True

            if should_create:
                self.lcu.request(
                    "POST", "/lol-lobby/v2/lobby", {"queueId": target_q_id}
                )
                time.sleep(1)

            # 4. Start Search
            res = self.lcu.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
            
            def _update_ui():
                if res and res.status_code in [200, 204]:
                    self.update_action_log(f"Searching ({mode})...")
                    self.set_power_state(True)
                else:
                    self.update_action_log("Matchmaking failed — check client.")

            self.after(0, _update_ui)

        threading.Thread(target=_execute_sync, daemon=True).start()

    def _on_toggle_accept(self):
        self.config.set("auto_accept", self.var_accept.get())
        self._update_auto_header()

    def _on_toggle_priority(self):
        cfg = self.config.get("priority_picker", {})
        cfg["enabled"] = self.var_priority.get()
        self.config.set("priority_picker", cfg)
        self._update_auto_header()

    def _on_toggle_auto_join(self):
        self.config.set("auto_join_enabled", self.var_auto_join.get())
        self._update_auto_header()

    def _on_toggle_auto_honor(self):
        self.config.set("auto_honor_enabled", self.var_auto_honor.get())
        self._update_auto_header()

    def _on_toggle_skip_stats(self):
        self.config.set("skip_stats_enabled", self.var_skip_stats.get())
        self._update_auto_header()
        
    def _on_toggle_auto_runes(self):
        self.config.set("auto_runes_enabled", self.var_auto_runes.get())
        self._update_auto_header()

    def _on_mass_invite(self):
        engine = getattr(self.master, "automation", None)
        if engine:
            def _invite():
                engine.mass_invite_friends()
            threading.Thread(target=_invite, daemon=True).start()
        else:
            self.update_action_log("Automation engine not available.")



    def _on_status_submit(self, event=None):
        text = self.entry_status.get().strip()
        engine = getattr(self.master, "automation", None)
        if engine and text:
            threading.Thread(target=lambda: engine.set_custom_status(text), daemon=True).start()

    def _on_quick_status(self, emoji, text):
        """Handler for quick status presets."""
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

    def _update_auto_header(self):
        if getattr(self, "var_accept", None) and getattr(self, "hdr_icon_accept", None):
            if self.var_accept.get(): self.hdr_icon_accept.pack(side="left", padx=2)
            else: self.hdr_icon_accept.pack_forget()

        if getattr(self, "var_priority", None) and getattr(self, "hdr_icon_priority", None):
            if self.var_priority.get(): self.hdr_icon_priority.pack(side="left", padx=2)
            else: self.hdr_icon_priority.pack_forget()
            
        if getattr(self, "var_auto_join", None) and getattr(self, "hdr_icon_auto_join", None):
            if self.var_auto_join.get(): self.hdr_icon_auto_join.pack(side="left", padx=2)
            else: self.hdr_icon_auto_join.pack_forget()
            
        if getattr(self, "var_auto_honor", None) and getattr(self, "hdr_icon_honor", None):
            if self.var_auto_honor.get(): self.hdr_icon_honor.pack(side="left", padx=2)
            else: self.hdr_icon_honor.pack_forget()

        if getattr(self, "var_skip_stats", None) and getattr(self, "hdr_icon_skip_stats", None):
            if self.var_skip_stats.get(): self.hdr_icon_skip_stats.pack(side="left", padx=2)
            else: self.hdr_icon_skip_stats.pack_forget()
            
        if getattr(self, "var_auto_runes", None) and getattr(self, "hdr_icon_auto_runes", None):
            if self.var_auto_runes.get(): self.hdr_icon_auto_runes.pack(side="left", padx=2)
            else: self.hdr_icon_auto_runes.pack_forget()
        
        arrow = "▼" if getattr(self, "auto_expanded", True) else "▶"
        base_text = f"{arrow}  AUTOMATION"
        
        if getattr(self, "lbl_auto_section", None):
            self.lbl_auto_section.configure(text=base_text)

    def update_action_log(self, text):
        """Updates the action log."""
        if self.winfo_exists():
            self.lbl_action.configure(text=text)

    def _clear_action_log(self):
        if self.winfo_exists():
            self.lbl_action.configure(text="Idle.")

    def _force_requeue(self):
        if self.lcu:
            def _execute():
                try:
                    self.lcu.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")
                    self.lcu.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
                    self.after(0, lambda: self.update_action_log("Re-queued Matchmaking."))
                except Exception as e:
                    self.after(0, lambda: self.update_action_log(f"Requeue error: {e}"))
            threading.Thread(target=_execute, daemon=True).start()

    def _force_dodge(self):
        if self.lcu:
            self.update_action_log("Client exiting (Dodging)...")
            def _execute():
                try:
                    self.lcu.request("POST", "/process-control/v1/process/quit")
                except Exception as e:
                    self.after(0, lambda: self.update_action_log(f"Dodge error: {e}"))
            threading.Thread(target=_execute, daemon=True).start()

    def _play_again(self):
        if self.lcu:
            self.update_action_log("Playing again...")
            def _execute():
                try:
                    res = self.lcu.request("POST", "/lol-lobby/v2/play-again")
                    if res and res.status_code in [200, 204]:
                        self.after(0, lambda: self.update_action_log("Entered Lobby."))
                    else:
                        self.after(0, lambda: self.update_action_log("Play Again failed."))
                except Exception as e:
                    self.after(0, lambda: self.update_action_log(f"Play Again error: {e}"))
            threading.Thread(target=_execute, daemon=True).start()

    def _show_play_again(self):
        if hasattr(self, "btn_find_match"):
            self.btn_find_match.pack_forget()
        if hasattr(self, "quick_actions_frame"):
            self.quick_actions_frame.pack_forget()
        if hasattr(self, "play_again_button"):
            self.play_again_button.pack(fill="x", pady=0)

    def _show_quick_actions(self):
        """Reveal the Requeue & Dodge buttons during active matchmaking phases."""
        if hasattr(self, "quick_actions_frame"):
            if hasattr(self, "btn_find_match"):
                self.btn_find_match.pack_forget()
            if hasattr(self, "play_again_button"):
                self.play_again_button.pack_forget()
            
            self.requeue_button.grid(row=0, column=0, padx=(0, 4), pady=0, sticky="ew")
            self.dodge_button.grid(row=0, column=1, padx=(4, 0), pady=0, sticky="ew")
            self.quick_actions_frame.pack(fill="x", pady=0)

    def _hide_quick_actions(self, show_find_match=True):
        """Hide the Requeue & Dodge buttons when idle or in-game."""
        if hasattr(self, "quick_actions_frame"):
            self.requeue_button.grid_remove()
            self.dodge_button.grid_remove()
            self.quick_actions_frame.pack_forget()
            
            if hasattr(self, "play_again_button"):
                self.play_again_button.pack_forget()
            
            if show_find_match and hasattr(self, "btn_find_match"):
                self.btn_find_match.pack(fill="x", pady=0)
            elif not show_find_match and hasattr(self, "btn_find_match"):
                self.btn_find_match.pack_forget()

    def _start_local_queue_timer(self, time_in_queue, estimated_time):
        """Start or re-sync the local queue timer. Idempotent — won't restart if already running."""
        self._estimated_queue_time = estimated_time if estimated_time > 0 else 120

        # If the timer is already ticking, only re-sync if drift is extreme (>5s)
        if self._queue_timer_job is not None:
            drift = abs(self._current_queue_time - time_in_queue)
            if drift <= 5:
                return  # Timer is running fine, don't touch it
        
        self._stop_local_queue_timer()
        self._current_queue_time = time_in_queue
        self._tick_local_timer()

    def _tick_local_timer(self):
        if not self.winfo_exists():
            return

        mins = int(self._current_queue_time // 60)
        secs = int(self._current_queue_time % 60)
        time_str = f"Queue: {mins}:{secs:02d}"

        self.time_label.configure(text=time_str)

        est = self._estimated_queue_time
        if est > 0:
            est_mins = int(est // 60)
            est_secs = int(est % 60)
            self.estimate_label.configure(text=f"Est: {est_mins}:{est_secs:02d}", text_color=get_color("colors.text.muted"))

            progress = min(1.0, self._current_queue_time / est)
            self.progress_bar.set(progress)

            if self._current_queue_time > est:
                # Overtime: solid warning color, no pulsing
                self.progress_bar.configure(progress_color=get_color("colors.state.danger", "#ff4444"))
                self.time_label.configure(text_color=get_color("colors.state.danger", "#ff4444"))
                self.estimate_label.configure(text="Overtime!", text_color=get_color("colors.state.danger", "#ff4444"))
            else:
                self.progress_bar.configure(progress_color=get_color("colors.accent.gold", "#C8AA6E"))
                self.time_label.configure(text_color=get_color("colors.text.primary"))
        else:
            self.progress_bar.set(0)

        self._current_queue_time += 1
        self._queue_timer_job = self.after(1000, self._tick_local_timer)

    def _stop_local_queue_timer(self):
        if hasattr(self, "_queue_timer_job") and self._queue_timer_job is not None:
            self.after_cancel(self._queue_timer_job)
            self._queue_timer_job = None
        if hasattr(self, "progress_bar"):
            self.progress_bar.set(0)
            self.progress_bar.configure(progress_color=get_color("colors.accent.gold", "#C8AA6E"))
        if hasattr(self, "time_label"):
            self.time_label.configure(text_color=get_color("colors.text.primary"))


    # ── ARAM Mode Detection ──
    _ARAM_MODES = frozenset({"ARAM", "ARAM Mayhem", "ARURF"})

    def _is_aram_mode(self, mode=None):
        """Return True if the given (or current) mode is ARAM-based."""
        if mode is None:
            mode = self.config.get("aram_mode", "ARAM")
        return mode in self._ARAM_MODES

    def update_queue_state(self, phase, search_state):
        """Updates the queue state."""
        if not self.winfo_exists():
            return

        # Persist the current phase for game-tool visibility decisions
        self._current_game_phase = phase

        # Track the last phase we processed to avoid redundant resets
        prev_ui_phase = self._last_ui_phase

        if phase == "Matchmaking" and search_state and search_state.get("searchState") == "Searching":
            time_in_queue = search_state.get("timeInQueue", 0)
            estimated_time = search_state.get("estimatedQueueTime", 0)
            self._start_local_queue_timer(time_in_queue, estimated_time)
            self._show_quick_actions()
            self._last_ui_phase = "Matchmaking"

        elif phase == "ReadyCheck":
            if prev_ui_phase != "ReadyCheck":
                self._stop_local_queue_timer()
                self.time_label.configure(text="Match Found!", text_color=get_color("colors.state.success", get_color("colors.state.success", "#00C853")))
                self.estimate_label.configure(text="● Ready", text_color=get_color("colors.state.success", "#00C853"))
                self.progress_bar.set(1.0)
                self.progress_bar.configure(progress_color=get_color("colors.state.success", "#00C853"))
                self._hide_quick_actions(show_find_match=False)

                try:
                    from ui.components.toast import ToastManager
                    ToastManager.get_instance().show("Match Found!", icon="⚔️", duration=4000, theme="success", confetti=True)
                except Exception as e:
                    Logger.error("UI", f"Failed to show match found toast: {e}")
            self._last_ui_phase = "ReadyCheck"

        elif phase == "ChampSelect":
            if prev_ui_phase != "ChampSelect":
                self._stop_local_queue_timer()
                self.time_label.configure(text="Champ Select", text_color=get_color("colors.accent.purple", "#A855F7"))
                self.estimate_label.configure(text="● Drafting", text_color=get_color("colors.accent.purple", "#A855F7"))
                self.progress_bar.set(1.0)
                self.progress_bar.configure(progress_color=get_color("colors.accent.purple", "#A855F7"))
                self._show_quick_actions()
            self._last_ui_phase = "ChampSelect"

        elif phase == "InProgress":
            if prev_ui_phase != "InProgress":
                self._stop_local_queue_timer()
                self.time_label.configure(text="In Game", text_color=get_color("colors.text.primary"))
                self.estimate_label.configure(text="● Playing", text_color=get_color("colors.accent.blue", "#3B82F6"))
                self.progress_bar.set(0)
                self._hide_quick_actions(show_find_match=False)
            self._last_ui_phase = phase

        elif phase in ["EndOfGame", "PreEndOfGame"]:
            if prev_ui_phase not in ["EndOfGame", "PreEndOfGame"]:
                self._stop_local_queue_timer()
                self.time_label.configure(text="Post Game", text_color=get_color("colors.text.primary"))
                self.estimate_label.configure(text="● Waiting Stats", text_color=get_color("colors.state.warning", "#F59E0B"))
                self.progress_bar.set(0)
                self._hide_quick_actions(show_find_match=False)
                self._show_play_again()
            elif not getattr(self, "play_again_button", None) or not bool(self.play_again_button.winfo_manager()):
                self._hide_quick_actions(show_find_match=False)
                self._show_play_again()
            self._last_ui_phase = phase
            
        elif phase == "Reconnect":
            if prev_ui_phase != "Reconnect":
                self._stop_local_queue_timer()
                self.time_label.configure(text="Reconnect", text_color=get_color("colors.state.danger", "#ff4444"))
                self.estimate_label.configure(text="● Crash/DC", text_color=get_color("colors.state.danger", "#ff4444"))
                self.progress_bar.set(0)
                self._hide_quick_actions(show_find_match=False)
            self._last_ui_phase = phase

        else:
            # Lobby / None
            if prev_ui_phase not in ["Lobby", "None"] or prev_ui_phase is None:
                self._stop_local_queue_timer()
                if getattr(self.master, "lcu", None) and self.master.lcu.is_connected:
                    self.time_label.configure(text="Queue: Idle", text_color=get_color("colors.text.primary"))
                    self.estimate_label.configure(text="● Connected", text_color=get_color("colors.state.success", "#00C853"))
                else:
                    self.time_label.configure(text="Disconnected", text_color=get_color("colors.state.danger", "#ff4444"))
                    self.estimate_label.configure(text="● Offline", text_color=get_color("colors.state.danger", "#ff4444"))
                self.progress_bar.set(0)
                self._hide_quick_actions(show_find_match=True)
            self._last_ui_phase = phase

        self._current_game_phase = phase

    def update_lobby_stats(self, team, bench, me=None):
        """Called from AutomationEngine during ChampSelect to show winrate stats."""
        if not self.winfo_exists(): return
        
        # Pass hovered champion to priority grid
        champ_id = me.get("championId", 0) if me else 0
        if hasattr(self, "priority_grid") and hasattr(self.priority_grid, "set_hovered_champion"):
            self.priority_grid.set_hovered_champion(champ_id)
            
        if not hasattr(self, "stats_card"):
            return
            
        if not getattr(self, "scraper", None) or not getattr(self, "assets", None):
            self.stats_card.pack_forget()
            return

        # Clear existing content
        for child in self.stats_content.winfo_children():
            child.destroy()

        stats_found = False
        
        for p in team:
            c_id = p.get("championId", 0)
            if c_id == 0:
                c_id = p.get("championPickIntent", 0)
            
            if c_id > 0:
                c_name = self.assets.get_champ_name(c_id)
                if c_name:
                    wr = self.scraper.get_winrate(c_name)
                    if wr > 0:
                        stats_found = True
                        row = ctk.CTkFrame(self.stats_content, fg_color="transparent")
                        row.pack(fill="x", pady=2)
                        
                        is_me = me and p.get("cellId") == me.get("cellId")
                        name_color = get_color("colors.accent.blue", "#4da6ff") if is_me else get_color("colors.text.primary")
                        ctk.CTkLabel(row, text=c_name, font=get_font("caption", "bold"), text_color=name_color).pack(side="left")
                        
                        if wr >= 53.0: wr_color = get_color("colors.state.success", "#00C853")
                        elif wr >= 50.0: wr_color = get_color("colors.text.primary", "#F0E6D2")
                        else: wr_color = get_color("colors.state.danger", "#ff4444")
                        
                        ctk.CTkLabel(row, text=f"{wr:.1f}%", font=get_font("caption"), text_color=wr_color).pack(side="right")

        if stats_found:
            self.stats_card.pack(fill="x", pady=(0, SECTION_GAP), before=self.spacer)
        else:
            self.stats_card.pack_forget()


