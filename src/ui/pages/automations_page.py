"""
Automations Page Component
Displays the auto-accept, sniper priority, queue mode config toggles in CustomTkinter.
"""
import customtkinter as ctk
from ui.components.factory import get_color, get_font, get_radius
from ui.components.lol_toggle import LolToggle
from ui.components.toggle_row import ToggleRow
from core.constants import SECTION_GAP, INNER_GAP, CARD_PAD

class AutomationsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, coordinator, **kwargs):
        super().__init__(
            master, 
            fg_color="transparent",
            scrollbar_button_color=get_color("colors.text.disabled"),
            scrollbar_button_hover_color=get_color("colors.text.muted"),
            scrollbar_fg_color="transparent",
            **kwargs
        )
        self.coordinator = coordinator
        self.config = coordinator.config
        self.assets = coordinator.assets
        
        try:
            self._scrollbar.configure(width=6)
        except Exception:
            pass

        # ── Master On/Off Switch ──
        self.master_switch_frame = ctk.CTkFrame(
            self, fg_color=get_color("colors.background.card", "#1E2328"),
            corner_radius=get_radius("md"), height=48
        )
        self.master_switch_frame.pack(fill="x", pady=(0, SECTION_GAP))
        self.master_switch_frame.pack_propagate(False)

        self.var_master = ctk.BooleanVar(value=True)
        self._master_label = ctk.CTkLabel(
            self.master_switch_frame, text="⚡ ALL ON",
            font=get_font("title"),
            text_color=get_color("colors.accent.gold", "#C8AA6E"),
            anchor="w"
        )
        self._master_label.pack(side="left", padx=8)

        self._master_toggle = LolToggle(
            self.master_switch_frame, width=48, height=24,
            variable=self.var_master, command=coordinator._on_master_toggle,
            bg_color=get_color("colors.background.card", "#1E2328")
        )
        self._master_toggle.pack(side="right", padx=8)

        TOGGLE_ROW_HEIGHT = 28
        self._automation_rows = []

        # Auto Accept
        self.var_accept = ctk.BooleanVar(value=self.config.get("auto_accept", True))
        self.row_accept = ToggleRow(
            self, label_text="Auto Accept", variable=self.var_accept,
            command=coordinator._on_toggle_accept, tooltip_text="Automatically accepts match queue pops",
            icon_item_id="2420", assets=self.assets, height=TOGGLE_ROW_HEIGHT,
            on_edit=lambda: coordinator._open_editor("auto_accept")
        )
        self.row_accept.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))
        self._automation_rows.append(("auto_accept", self.var_accept, self.row_accept))

        # ARAM Picker
        self.var_priority = ctk.BooleanVar(value=self.config.get("priority_picker", {}).get("enabled", False))
        self.row_priority = ToggleRow(
            self, label_text="ARAM Picker", variable=self.var_priority,
            command=coordinator._on_toggle_priority, tooltip_text="Attempts to pick highest available champion from ARAM List",
            icon_item_id="2052", assets=self.assets, height=TOGGLE_ROW_HEIGHT,
            on_edit=lambda: coordinator._open_editor("priority_picker")
        )
        self.row_priority.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))
        self._automation_rows.append(("priority_picker", self.var_priority, self.row_priority))
        
        # Friend Auto-Join
        self.var_auto_join = ctk.BooleanVar(value=self.config.get("auto_join_enabled", True))
        self.row_auto_join = ToggleRow(
            self, label_text="Friend Auto-Join", variable=self.var_auto_join,
            command=coordinator._on_toggle_auto_join, tooltip_text="Automatically joins available friend lobbies",
            icon_item_id="3109", assets=self.assets, height=TOGGLE_ROW_HEIGHT,
            on_edit=lambda: coordinator._open_editor("auto_join")
        )
        self.row_auto_join.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))
        self._automation_rows.append(("auto_join", self.var_auto_join, self.row_auto_join))

        # Auto Honor
        self.var_auto_honor = ctk.BooleanVar(value=self.config.get("auto_honor_enabled", False))
        self.row_auto_honor = ToggleRow(
            self, label_text="Auto Honor", variable=self.var_auto_honor,
            command=coordinator._on_toggle_auto_honor, tooltip_text="Automatically honors a teammate after each game",
            icon_item_id="3105", assets=self.assets, height=TOGGLE_ROW_HEIGHT,
            on_edit=lambda: coordinator._open_editor("auto_honor")
        )
        self.row_auto_honor.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))
        self._automation_rows.append(("auto_honor", self.var_auto_honor, self.row_auto_honor))

        # Skip Stats
        self.var_skip_stats = ctk.BooleanVar(value=self.config.get("skip_stats_enabled", True))
        self.row_skip_stats = ToggleRow(
            self, label_text="Skip Stats", variable=self.var_skip_stats,
            command=coordinator._on_toggle_skip_stats, tooltip_text="Automatically skips the post-match stats screen",
            icon_item_id="3111", assets=self.assets, height=TOGGLE_ROW_HEIGHT
        )
        self.row_skip_stats.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))
        self._automation_rows.append(("skip_stats", self.var_skip_stats, self.row_skip_stats))

        # Auto Runes
        self.var_auto_runes = ctk.BooleanVar(value=self.config.get("auto_runes_enabled", False))
        self.row_auto_runes = ToggleRow(
            self, label_text="Auto Runes", variable=self.var_auto_runes,
            command=coordinator._on_toggle_auto_runes, tooltip_text="Automatically equips recommended runes for your champion",
            icon_item_id="3340", assets=self.assets, height=TOGGLE_ROW_HEIGHT
        )
        self.row_auto_runes.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))
        self._automation_rows.append(("auto_runes", self.var_auto_runes, self.row_auto_runes))

        # Auto-Add Played Champions
        self.var_auto_add_played = ctk.BooleanVar(value=self.config.get("aram_auto_add_played", False))
        self.row_auto_add_played = ToggleRow(
            self, label_text="Auto-Add Played", variable=self.var_auto_add_played,
            command=coordinator._on_toggle_auto_add_played, tooltip_text="Automatically adds champions you play to the ARAM List after each game",
            icon_item_id="2052", assets=self.assets, height=TOGGLE_ROW_HEIGHT
        )
        self.row_auto_add_played.pack(fill="x", padx=CARD_PAD, pady=(0, INNER_GAP))
        self._automation_rows.append(("auto_add_played", self.var_auto_add_played, self.row_auto_add_played))

        # Auto-Ban
        self.var_auto_ban = ctk.BooleanVar(value=self.config.get("auto_ban_enabled", False))
        self.row_auto_ban = ToggleRow(
            self, label_text="Auto-Ban", variable=self.var_auto_ban,
            command=coordinator._on_toggle_auto_ban, tooltip_text="Automatically bans configured champions in champ select",
            icon_champion_id="350", icon_type="champion", assets=self.assets, height=TOGGLE_ROW_HEIGHT,
            on_edit=lambda: coordinator._open_editor("auto_ban")
        )
        self.row_auto_ban.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        self._automation_rows.append(("auto_ban", self.var_auto_ban, self.row_auto_ban))
