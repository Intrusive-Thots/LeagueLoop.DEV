"""
Play Page Component
Handles CustomTkinter play, queue search controls, friends list, and accounts tool layout.
"""
import customtkinter as ctk
from ui.components.factory import get_color, get_font, make_button
from ui.components.session_header import SessionHeader
from ui.components.friend_list import FriendPriorityList
from ui.components.game_tools.accounts_tool import AccountsTool
from ui.ui_shared import CTkTooltip
from core.constants import SECTION_GAP, BTN_HEIGHT, INNER_GAP

class PlayPage(ctk.CTkFrame):
    def __init__(self, master, coordinator, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.coordinator = coordinator
        self.config = coordinator.config
        self.lcu = coordinator.lcu
        self.assets = coordinator.assets

        # ── Session Info Block (always visible) ──
        self.session_header = SessionHeader(
            self,
            config=self.config,
            on_mode_change=coordinator._on_mode_change,
            on_power_click=coordinator._on_power_click,
            initial_mode=self.config.get("aram_mode", "ARAM")
        )
        self.session_header.pack(fill="x", pady=(0, SECTION_GAP))

        # ── Action Buttons ──
        self.action_container = ctk.CTkFrame(
            self,
            fg_color=get_color("colors.background.card", "#0F1923"),
            corner_radius=8,
            border_width=1,
            border_color="#1A2332"
        )
        self.action_container.pack(fill="x", pady=(0, SECTION_GAP))

        self.btn_frame = ctk.CTkFrame(self.action_container, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=8, pady=8)

        # ── Find Match / Quick Actions Container ──
        self.queue_actions_container = ctk.CTkFrame(self.btn_frame, fg_color="transparent")
        self.queue_actions_container.pack(fill="x", pady=0)

        # ── Find Match ──
        self.btn_find_match = make_button(
            self.queue_actions_container, 
            text="▶  Find Match",
            style="primary",
            font=get_font("body", "bold"), 
            height=BTN_HEIGHT,
            border_width=1,
            border_color=get_color("colors.accent.primary", "#F0E6D2"),
            command=coordinator._find_match
        )
        self.btn_find_match.pack(fill="x", pady=0)
        hk_find = self.config.get("hotkey_find_match", "ctrl+shift+f").upper()
        CTkTooltip(self.btn_find_match, f"Start or Cancel Matchmaking ({hk_find})")

        # ── Quick Actions Row ──
        self.quick_actions_frame = ctk.CTkFrame(
            self.queue_actions_container,
            height=BTN_HEIGHT,
            fg_color="transparent"
        )
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
            command=coordinator._force_requeue,
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
            command=coordinator._force_dodge,
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
            command=coordinator._play_again
        )
        CTkTooltip(self.play_again_button, "Return to lobby and play again")

        # ── Launch Client ──
        self.btn_launch_client = make_button(
            self.btn_frame,
            text="🚀 Launch Client",
            style="secondary",
            font=get_font("body", "bold"),
            height=BTN_HEIGHT,
            command=lambda: self.master.master._hotkey_launch_client() if hasattr(self.master.master, "_hotkey_launch_client") else None
        )
        self.btn_launch_client.pack(fill="x", pady=(INNER_GAP, 0))
        hk_launch = self.config.get("hotkey_launch_client", "ctrl+shift+l").upper()
        CTkTooltip(self.btn_launch_client, f"Open the Riot Client and start League ({hk_launch})")

        # ── Friends List ──
        self.friend_list = FriendPriorityList(self, config=self.config, lcu=self.lcu)
        self.friend_list.pack(fill="x", pady=(0, SECTION_GAP))

        # ── Accounts Tool (dynamic placeholder) ──
        self.accounts_tool = None
        self._accounts_tool_visible = False

        # Spacer to push layout elements upwards
        self.spacer = ctk.CTkFrame(self, fg_color="transparent", height=1)
        self.spacer.pack(fill="both", expand=True)

    def set_account_manager(self, account_manager):
        if self.accounts_tool is not None:
            self.accounts_tool.destroy()
        self.accounts_tool = AccountsTool(self, account_manager, lcu=self.lcu)
        self.update_accounts_tool_visibility(self.lcu.is_connected)

    def update_accounts_tool_visibility(self, lcu_connected: bool = False):
        if self.accounts_tool is None or not self.winfo_exists():
            return

        riot_running = False
        if hasattr(self.coordinator, "_account_manager") and self.coordinator._account_manager:
            riot_running = self.coordinator._account_manager.riot_client.is_riot_client_running()

        should_show = riot_running and not lcu_connected
        self._accounts_tool_visible = should_show

        # Toggle accounts tool pack placement
        if should_show:
            self.spacer.pack_forget()
            self.accounts_tool.pack(fill="x", pady=(0, SECTION_GAP))
            self.spacer.pack(fill="both", expand=True)
        else:
            self.accounts_tool.pack_forget()

        # Toggle Launch Client Button
        if not lcu_connected and not riot_running:
            self.btn_launch_client.pack(fill="x", pady=(INNER_GAP, 0))
        else:
            self.btn_launch_client.pack_forget()
