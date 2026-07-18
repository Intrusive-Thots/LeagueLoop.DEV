"""
Sidebar Layout Coordinator Widget
Incorporates CustomTitleBar, Tab navigation, page view transitions, and status bar log.
"""
import os
import threading
import time
from PIL import Image
import customtkinter as ctk

from ui.components.factory import get_color, get_font, get_radius, make_button, make_card
from ui.ui_shared import CTkTooltip
from core.constants import SECTION_GAP, BTN_HEIGHT, INNER_GAP, CARD_PAD, SPACING_XS, SPACING_SM, SPACING_MD, FOOTER_HEIGHT, GEOMETRY_THRESHOLD
from utils.logger import Logger
from utils.smooth_scroll import apply_smooth_scroll
from utils.path_utils import get_asset_path
from core.events import EventBus
from services.queue_service import get_queue_service

from ui.sidebar.navigation import NavigationWidget
from ui.sidebar.status_bar import StatusBarWidget
from ui.pages.play_page import PlayPage
from ui.pages.automations_page import AutomationsPage
from ui.pages.config_page import ConfigPage
from ui.pages.settings_page import SettingsPage

class SidebarWidget(ctk.CTkFrame):
    def __init__(self, master, toggle_callback, config, lcu=None, assets=None, scraper=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.master = master
        self.toggle_callback = toggle_callback
        self.config = config
        self.lcu = lcu
        self.assets = assets
        self.scraper = scraper
        self.root_app = self.winfo_toplevel()

        self.power_state = True
        self.var_power = ctk.BooleanVar(value=True)
        self._body_expanded = True
        self._last_ui_phase = None
        self._current_game_phase = None
        self._current_queue_time = 0
        self._estimated_queue_time = 120
        self._automation_saved_states = {}

        # Subscribe to Queue events
        EventBus.on("queue_timer_tick", self._on_queue_timer_tick)
        EventBus.on("queue_search_started", self._on_queue_search_started)
        EventBus.on("queue_search_cancelled", self._on_queue_search_cancelled)

        # ── 1. Sidebar Header Chrome ──
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", pady=(SPACING_SM, SPACING_MD), padx=SPACING_SM)

        self.lbl_title = ctk.CTkLabel(
            self.header, text="LEAGUE LOOP",
            font=get_font("header", "bold"),
            text_color=get_color("colors.accent.gold", "#C8AA6E")
        )
        self.lbl_title.pack(side="left")
        self.drag_widgets = [self.header, self.lbl_title]

        # Collapse Sidebar Button
        self.btn_collapse = ctk.CTkButton(
            self.header, text="◀", width=18, height=18,
            corner_radius=4, font=get_font("caption"),
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover"),
            command=self._toggle_body_collapse, cursor="hand2"
        )
        self.btn_collapse.pack(side="right", padx=(4, 1))
        self.tooltip_collapse = CTkTooltip(self.btn_collapse, "Collapse Sidebar")

        # Minimize Button
        self.btn_minimize = ctk.CTkButton(
            self.header, text="─", width=18, height=18,
            corner_radius=4, font=get_font("caption"),
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover"),
            command=self._minimize_window, cursor="hand2"
        )
        self.btn_minimize.pack(side="right", padx=(4, 1))
        CTkTooltip(self.btn_minimize, "Minimize")

        # Close Button
        self.btn_close = ctk.CTkButton(
            self.header, text="✕", width=18, height=18,
            corner_radius=4, font=get_font("caption"),
            fg_color="transparent",
            text_color=get_color("colors.text.muted"),
            hover_color=get_color("colors.state.hover", "#e81123"),
            command=lambda: master._on_close_request() if hasattr(master, "_on_close_request") else master.destroy(),
            cursor="hand2"
        )
        self.btn_close.pack(side="right", padx=(4, 2))
        CTkTooltip(self.btn_close, "Close")

        # ── 2. Tab Pages Body Frame ──
        self.main_body = ctk.CTkFrame(self, fg_color="transparent")

        # ── 3. Navigation Widget ──
        self.navigation = NavigationWidget(
            self.main_body,
            tabs=["Play", "Automations", "Config", "Settings"],
            on_tab_switch=self.switch_tab
        )
        self.navigation.pack(fill="x", pady=(0, INNER_GAP))

        # ── 4. Construct Decomposed Pages ──
        self.play_page = PlayPage(self.main_body, self)
        self.automations_page = AutomationsPage(self.main_body, self)
        self.config_page = ConfigPage(self.main_body, self)
        self.settings_page = SettingsPage(self.main_body, self)

        # ── 5. Status Bar Pinned Bottom Footer ──
        self.status_bar = StatusBarWidget(self)
        self.status_bar.pack(fill="x", side="bottom", padx=CARD_PAD, pady=(0, INNER_GAP))

        # Now pack main body to take up remaining central area
        self.main_body.pack(fill="both", expand=True, padx=CARD_PAD, pady=(0, SPACING_XS))

        # ── 6. Setup Backward Compatibility Bindings / Aliases ──
        self.session_frame = self.play_page.session_header
        self.queue_label = self.play_page.session_header.queue_label
        self.time_label = self.play_page.session_header.time_label
        self.estimate_label = self.play_page.session_header.estimate_label
        self.progress_bar = self.play_page.session_header.progress_bar
        self.btn_power_status = self.play_page.session_header.btn_power_status
        self.lbl_action = self.status_bar.lbl_action
        self.btn_clear_log = self.status_bar.btn_clear_log

        self.friend_list = self.play_page.friend_list
        self.requeue_button = self.play_page.requeue_button
        self.dodge_button = self.play_page.dodge_button
        self.play_again_button = self.play_page.play_again_button
        self.btn_find_match = self.play_page.btn_find_match
        self.quick_actions_frame = self.play_page.quick_actions_frame
        self.btn_launch_client = self.play_page.btn_launch_client
        self.action_container = self.play_page.action_container

        self.priority_grid = self.config_page.priority_grid
        self.arena_tool = self.config_page.arena_tool
        self.draft_tool = self.config_page.draft_tool
        self.game_tool_container = self.config_page.game_tool_container

        self._automation_rows = self.automations_page._automation_rows
        self.var_master = self.automations_page.var_master
        self._master_toggle = self.automations_page._master_toggle
        self._master_label = self.automations_page._master_label

        self.var_accept = self.automations_page.var_accept
        self.var_priority = self.automations_page.var_priority
        self.var_auto_join = self.automations_page.var_auto_join
        self.var_auto_honor = self.automations_page.var_auto_honor
        self.var_skip_stats = self.automations_page.var_skip_stats
        self.var_auto_runes = self.automations_page.var_auto_runes
        self.var_auto_add_played = self.automations_page.var_auto_add_played
        self.var_auto_ban = self.automations_page.var_auto_ban
        self.entry_status = self.settings_page.entry_status

        # ── Lobby Stats & Spacer (Bottom of main_body, always packed after pages) ──
        self.spacer = ctk.CTkFrame(self.main_body, fg_color="transparent", height=1)
        self.spacer.pack(fill="both", expand=True)

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

        # Default Active Tab
        self._current_tab = "Play"
        self.switch_tab("Play")

    def switch_tab(self, tab_name):
        self._current_tab = tab_name
        self.navigation.select_tab(tab_name)

        # Hide all page layouts
        self.play_page.pack_forget()
        self.automations_page.pack_forget()
        self.config_page.pack_forget()
        self.settings_page.pack_forget()

        # Pack selected tab layout
        if tab_name == "Play":
            self.play_page.pack(fill="both", expand=True)
            # Make sure play page sub-components are showing properly
            self.play_page.friend_list.pack(fill="x", pady=(0, SECTION_GAP))
            self.play_page.update_accounts_tool_visibility(get_league_service().is_connected)
        elif tab_name == "Automations":
            self.automations_page.pack(fill="both", expand=True)
        elif tab_name == "Config":
            self.config_page.pack(fill="both", expand=True)
        elif tab_name == "Settings":
            self.settings_page.pack(fill="both", expand=True)

    def set_account_manager(self, account_manager):
        self._account_manager = account_manager
        self.play_page.set_account_manager(account_manager)
        self.accounts_tool = self.play_page.accounts_tool

    def update_accounts_tool_visibility(self, lcu_connected: bool = False):
        self.play_page.update_accounts_tool_visibility(lcu_connected)
        self.accounts_tool = self.play_page.accounts_tool
        if hasattr(self, "switch_tab"):
            self.switch_tab(self._current_tab)

    # ── Custom Chrome Chrome drag/close handlers ──
    def _toggle_body_collapse(self):
        self._body_expanded = not self._body_expanded
        h = self.master.winfo_height()
        if self._body_expanded:
            self.header.pack_configure(fill="x", pady=(SPACING_SM, SPACING_MD), padx=SPACING_SM)
            self.lbl_title.pack(side="left")
            self.btn_close.pack(side="right", padx=(4, 2))
            self.btn_minimize.pack(side="right", padx=(4, 1))
            self.btn_collapse.pack(side="right", padx=(4, 1))
            self.main_body.pack(fill="both", expand=True)
            self.status_bar.pack(fill="x", side="bottom", padx=CARD_PAD, pady=(0, INNER_GAP))
            self.btn_collapse.configure(text="◀")
            self.master.geometry(f"200x{h}")
            if hasattr(self, 'tooltip_collapse'):
                self.tooltip_collapse.configure(text="Collapse Sidebar")
        else:
            self.main_body.pack_forget()
            self.btn_close.pack_forget()
            self.btn_minimize.pack_forget()
            self.lbl_title.pack_forget()
            self.status_bar.pack_forget()
            
            self.header.pack_configure(fill="both", expand=True, padx=0, pady=0)
            self.btn_collapse.pack_configure(side="top", pady=SPACING_MD, padx=0)
            self.btn_collapse.configure(text="▶")
            self.master.geometry("44x44")
            if hasattr(self, 'tooltip_collapse'):
                self.tooltip_collapse.configure(text="Expand Sidebar")

    def _minimize_window(self):
        import ctypes
        SW_MINIMIZE = 6
        hwnd = ctypes.windll.user32.GetParent(self.master.winfo_id())
        if hwnd == 0:
            hwnd = self.master.winfo_id()
        ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)

    def _update_game_tool_visibility(self, mode):
        self.config_page.update_game_tool_visibility(mode)

    def _on_mode_change(self, new_mode):
        self.config.set("aram_mode", new_mode)
        if self.scraper:
            self.scraper.set_mode(new_mode)
        if hasattr(self, "queue_label") and self.queue_label.winfo_exists():
            self.queue_label.configure(text=new_mode)
        self._update_game_tool_visibility(new_mode)

    def _on_lobby_event(self, lobby_data):
        if not self.winfo_exists() or not lobby_data:
            return
        queue_id = lobby_data.get("gameConfig", {}).get("queueId")
        if not queue_id: return
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
            1710: "Arena 3v6",
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
                self.root_app.after(0, lambda: self._on_mode_change(detected_mode))

    def on_lcu_connection_changed(self, connected: bool):
        if not self.winfo_exists(): return
        if not connected:
            self._hide_quick_actions()
            self._stop_local_queue_timer()
            if hasattr(self, "time_label") and self.time_label.winfo_exists():
                self.time_label.configure(text="Disconnected", text_color=get_color("colors.state.danger", "#ff4444"))
            if hasattr(self, "estimate_label") and self.estimate_label.winfo_exists():
                self.estimate_label.configure(text="● Offline", text_color=get_color("colors.state.danger", "#ff4444"))
        self.update_accounts_tool_visibility(lcu_connected=connected)

    def set_power_state(self, state: bool):
        if getattr(self, "power_state", None) == state: return
        self.power_state = state
        try:
            self.var_power.set(state)
        except Exception as e:
            Logger.debug("UI", f"State sync error: {e}")

        if hasattr(self, "btn_power_status") and self.btn_power_status.winfo_exists():
            if state:
                self.btn_power_status.configure(text="▶ Active", text_color=get_color("colors.accent.primary"))
            else:
                self.btn_power_status.configure(text="⏸ Paused", text_color=get_color("colors.text.muted"))

        if self.toggle_callback:
            self.toggle_callback(self.power_state)

    def _on_power_click(self):
        new_state = not getattr(self, "power_state", False)
        self.set_power_state(new_state)

        if self.toggle_callback:
            def _check_and_cancel():
                # Let QueueService cancel search if it's running
                queue_service = get_queue_service()
                if queue_service and queue_service.is_searching:
                    queue_service.cancel_matchmaking()
                    self.root_app.after(0, lambda: self.update_action_log("Matchmaking Cancelled."))
                    if getattr(self, "power_state", False):
                        self.root_app.after(0, lambda: self.set_power_state(False))
            threading.Thread(target=_check_and_cancel, daemon=True).start()

    def _get_queue_id_for_mode(self, mode: str):
        mode_map = {
            "Quickplay": 490,
            "Draft Pick": 400,
            "Ranked Solo/Duo": 420,
            "Ranked Flex": 440,
            "ARAM": 450,
            "ARAM Mayhem": 2400,
            "Arena": 1700,
            "Arena 3v6": 1710,
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
        return 450

    def _find_match(self):
        threading.Thread(target=lambda: get_queue_service().find_match(), daemon=True).start()

    def _on_toggle_accept(self):
        self.config.set("auto_accept", self.var_accept.get())

    def _on_toggle_priority(self):
        cfg = self.config.get("priority_picker", {})
        cfg["enabled"] = self.var_priority.get()
        self.config.set("priority_picker", cfg)

    def _on_toggle_auto_join(self):
        self.config.set("auto_join_enabled", self.var_auto_join.get())

    def _on_toggle_auto_honor(self):
        self.config.set("auto_honor_enabled", self.var_auto_honor.get())

    def _on_toggle_skip_stats(self):
        self.config.set("skip_stats_enabled", self.var_skip_stats.get())
        
    def _on_toggle_auto_runes(self):
        self.config.set("auto_runes_enabled", self.var_auto_runes.get())

    def _on_toggle_auto_add_played(self):
        self.config.set("aram_auto_add_played", self.var_auto_add_played.get())

    def _on_toggle_auto_ban(self):
        self.config.set("auto_ban_enabled", self.var_auto_ban.get())

    def _on_master_toggle(self):
        master_on = self.var_master.get()
        if master_on:
            self._master_label.configure(text="⚡ ALL ON", text_color=get_color("colors.accent.gold", "#C8AA6E"))
            for key, var, row in self._automation_rows:
                saved = self._automation_saved_states.get(key)
                if saved is not None: var.set(saved)
                row.set_enabled(True)
                row._update_icon_state()
        else:
            self._master_label.configure(text="ALL OFF", text_color=get_color("colors.text.muted", "#5B5A56"))
            for key, var, row in self._automation_rows:
                self._automation_saved_states[key] = var.get()
                var.set(False)
                row.set_enabled(False)
                row._update_icon_state()
        self._on_toggle_accept()
        self._on_toggle_priority()
        self._on_toggle_auto_join()
        self._on_toggle_auto_honor()
        self._on_toggle_skip_stats()
        self._on_toggle_auto_runes()
        self._on_toggle_auto_add_played()
        self._on_toggle_auto_ban()

    def _open_editor(self, automation_key):
        from ui.components.automation_editor import AutomationEditor
        AutomationEditor(self, automation_key, self.config, assets=self.assets)

    def _on_status_submit(self, event=None):
        text = self.entry_status.get().strip()
        engine = getattr(self.master, "automation", None)
        if engine and text:
            threading.Thread(target=lambda: engine.set_custom_status(text), daemon=True).start()

    def _on_quick_status(self, emoji, text):
        status_text = f"{emoji} {text}" if emoji else text
        self.entry_status.delete(0, "end")
        self.entry_status.insert(0, status_text)
        self._on_status_submit()
        try:
            from ui.components.toast import ToastManager
            ToastManager.get_instance(self.winfo_toplevel()).show(
                message=f"Status set: {text}", icon=emoji, theme="success", duration=2000
            )
        except Exception:
            pass

    def update_action_log(self, text):
        self.status_bar.update_action_log(text)

    def _clear_action_log(self):
        self.status_bar._clear_action_log()

    def _force_requeue(self):
        def _execute():
            qs = get_queue_service()
            qs.cancel_matchmaking()
            time.sleep(0.5)
            qs.find_match()
        threading.Thread(target=_execute, daemon=True).start()

    def _force_dodge(self):
        self.update_action_log("Client exiting (Dodging)...")
        threading.Thread(target=get_queue_service().force_dodge, daemon=True).start()

    def _play_again(self):
        self.update_action_log("Playing again...")
        threading.Thread(target=get_queue_service().play_again, daemon=True).start()

    def _show_play_again(self):
        self.play_page.btn_find_match.pack_forget()
        self.play_page.quick_actions_frame.pack_forget()
        self.play_page.play_again_button.pack(fill="x", pady=0)

    def _show_quick_actions(self):
        self.play_page.btn_find_match.pack_forget()
        self.play_page.play_again_button.pack_forget()
        self.play_page.requeue_button.grid(row=0, column=0, padx=(0, 4), pady=0, sticky="ew")
        self.play_page.dodge_button.grid(row=0, column=1, padx=(4, 0), pady=0, sticky="ew")
        self.play_page.quick_actions_frame.pack(fill="x", pady=0)

    def _hide_quick_actions(self, show_find_match=True):
        self.play_page.requeue_button.grid_remove()
        self.play_page.dodge_button.grid_remove()
        self.play_page.quick_actions_frame.pack_forget()
        self.play_page.play_again_button.pack_forget()
        
        if show_find_match:
            self.play_page.btn_find_match.pack(fill="x", pady=0)
        else:
            self.play_page.btn_find_match.pack_forget()

    def _on_queue_timer_tick(self, current_time, estimated_time):
        self._current_queue_time = current_time
        self._estimated_queue_time = estimated_time
        if not self.winfo_exists(): return
        self.root_app.after(0, self._render_timer_ui)

    def _on_queue_search_started(self, mode):
        if not self.winfo_exists(): return
        self.root_app.after(0, lambda: self.update_action_log(f"Searching ({mode})..."))
        self.root_app.after(0, lambda: self.set_power_state(True))

    def _on_queue_search_cancelled(self):
        if not self.winfo_exists(): return
        self.root_app.after(0, lambda: self.update_action_log("Matchmaking Cancelled."))
        self.root_app.after(0, lambda: self.set_power_state(False))

    def _render_timer_ui(self):
        if not self.winfo_exists(): return
        mins, secs = int(self._current_queue_time // 60), int(self._current_queue_time % 60)
        time_str = f"Queue: {mins}:{secs:02d}"
        self.time_label.configure(text=time_str)

        est = self._estimated_queue_time
        if est > 0:
            est_mins, est_secs = int(est // 60), int(est % 60)
            self.estimate_label.configure(text=f"Est: {est_mins}:{est_secs:02d}", text_color=get_color("colors.text.muted"))
            progress = min(1.0, self._current_queue_time / est)
            self.progress_bar.set(progress)
            if self._current_queue_time > est:
                self.progress_bar.configure(progress_color=get_color("colors.state.danger", "#ff4444"))
                self.time_label.configure(text_color=get_color("colors.state.danger", "#ff4444"))
                self.estimate_label.configure(text="Overtime!", text_color=get_color("colors.state.danger", "#ff4444"))
            else:
                self.progress_bar.configure(progress_color=get_color("colors.accent.gold", "#C8AA6E"))
                self.time_label.configure(text_color=get_color("colors.text.primary"))
        else:
            self.progress_bar.set(0)

    def _start_local_queue_timer(self, time_in_queue, estimated_time):
        # Compatibility shim: now managed by EventBus
        pass

    def _stop_local_queue_timer(self):
        if hasattr(self, "progress_bar"):
            self.progress_bar.set(0)
            self.progress_bar.configure(progress_color=get_color("colors.accent.gold", "#C8AA6E"))
        if hasattr(self, "time_label"):
            self.time_label.configure(text_color=get_color("colors.text.primary"))

    def _is_aram_mode(self, mode=None):
        if mode is None:
            mode = self.config.get("aram_mode", "ARAM")
        return mode in {"ARAM", "ARAM Mayhem", "ARURF"}

    def update_queue_state(self, phase, search_state):
        if not self.winfo_exists(): return
        self._current_game_phase = phase
        prev_ui_phase = self._last_ui_phase

        if phase == "Matchmaking" and search_state and search_state.get("searchState") == "Searching":
            self._start_local_queue_timer(search_state.get("timeInQueue", 0), search_state.get("estimatedQueueTime", 0))
            self._show_quick_actions()
            self._last_ui_phase = "Matchmaking"
        elif phase == "ReadyCheck":
            if prev_ui_phase != "ReadyCheck":
                self._stop_local_queue_timer()
                self.time_label.configure(text="Match Found!", text_color=get_color("colors.state.success", "#00C853"))
                self.estimate_label.configure(text="● Ready", text_color=get_color("colors.state.success", "#00C853"))
                self.progress_bar.set(1.0)
                self.progress_bar.configure(progress_color=get_color("colors.state.success", "#00C853"))
                self._hide_quick_actions(show_find_match=False)
                try:
                    from ui.components.toast import ToastManager
                    ToastManager.get_instance().show("Match Found!", icon="⚔️", duration=4000, theme="success", confetti=True)
                except Exception as e:
                    Logger.error("UI", f"Match toast failed: {e}")
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
        if not self.winfo_exists(): return
        champ_id = me.get("championId", 0) if me else 0
        if hasattr(self.config_page.priority_grid, "set_hovered_champion"):
            self.config_page.priority_grid.set_hovered_champion(champ_id)
            
        if not hasattr(self, "stats_card"): return
        if not getattr(self, "scraper", None) or not getattr(self, "assets", None):
            self.stats_card.pack_forget()
            return

        # Clear existing content
        for child in self.stats_content.winfo_children():
            child.destroy()

        stats_found = False
        for p in team:
            c_id = p.get("championId", 0) or p.get("championPickIntent", 0)
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
            # Show lobby stats panel in Settings Page when active
            self.spacer.pack_forget()
            self.stats_card.pack(fill="x", pady=(0, SECTION_GAP))
            self.spacer.pack(fill="both", expand=True)
        else:
            self.stats_card.pack_forget()
