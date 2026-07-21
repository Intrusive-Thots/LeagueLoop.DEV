"""
Automation Engine module.
"""
import json
import random
import subprocess
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, List



from ..api_handler import LCUClient  # type: ignore
from ..asset_manager import AssetManager, ConfigManager  # type: ignore
from ..discord_rpc import DiscordPresenceManager  # type: ignore
from utils.logger import Logger  # type: ignore
from core.events import EventBus
from core.constants import (
    QUEUE_ARENA, QUEUE_ARENA_3V6, QUEUE_DRAFT, QUEUE_RANKED_SOLO, QUEUE_RANKED_FLEX,
    TICK_SLEEP_DEFAULT, TICK_SLEEP_CHAMPSELECT,
    TICK_SLEEP_READYCHECK, TICK_SLEEP_LOBBY, TICK_SLEEP_INGAME,
    PRIORITY_SWAP_COOLDOWN,
)

class AutomationEngine:
    """Core engine for executing automation tasks like auto-accept, priority sniper, draft assistant, and arena synergy."""
    def __init__(
        self,
        lcu: LCUClient,
        assets: AssetManager,
        config: ConfigManager,
        log_func=None,
        stop_func=None,
        **kwargs
    ):
        """Initializes the AutomationEngine with LCU client, asset manager, and config manager."""
        self.lcu = lcu
        self.assets = assets
        self.config = config
        self.log: Optional[Callable] = log_func
        self.stop_func: Optional[Callable] = stop_func
        # Legacy callback aliases — now routed through EventBus
        self.stats_func: Optional[Callable] = kwargs.get("stats_func")
        self.window_func: Optional[Callable] = kwargs.get("window_func")
        self.toast_func: Optional[Callable] = kwargs.get("toast_func")
        self.queue_func: Optional[Callable] = kwargs.get("queue_func")
        self.running: bool = False
        self.paused: bool = False
        self.thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._last_error_times: dict = {}
        self.setup_done: bool = False
        self.last_phase: str = "None"
        self.current_queue_id: Optional[int] = None
        self._blacklist = [name.strip().lower() for name in self.config.get("dodge_blacklist", "").split(",") if name.strip()]
        self._toxic_keywords = ["kys", "int", "troll", "run it down", "nword", "f slur"]
        self._chat_warden_warned = False

        self.ready_check_start: Optional[float] = None
        self.ready_check_delay: Optional[float] = None
        self.ready_check_accepted: bool = False
        self._accept_timer = None  # Item #46: Init in __init__ instead of getattr guard
        self._last_countdown_log: Optional[float] = None
        self._last_mass_invite: float = 0.0  # Item #170: Init rate-limit timer

        self._last_disconnect_log: float = 0.0
        self._requeue_handled: bool = False
        self._skin_equipped: bool = False
        self._last_priority_swap: float = 0.0
        self._last_search_state_time: float = 0.0
        self._honor_handled: bool = False
        self._runes_equipped: bool = False
        self._last_champ_id: int = 0
        self._cached_search_state: Optional[dict] = None
        self._party_puuids = set()
        self._honored_puuids = set()
        # Item #40: Consecutive error killswitch
        self._consecutive_errors: int = 0
        self._first_error_time: float = 0.0

        # Synergy / Draft / Friend action throttles (Items #163-165)
        self._last_synergy_patch: float = 0.0
        self._last_draft_action_time: float = 0.0
        self._last_friend_check: float = 0.0

        # Game process tracking — League of Legends.exe is a separate PID
        # from LeagueClient.exe, so we monitor it independently to maintain
        # InProgress phase awareness even when the LCU API connection drops.
        self._game_pid: Optional[int] = None
        self._last_game_scan: float = 0.0
        
        # External Integrations
        self.discord_rpc = DiscordPresenceManager(self.config)

    def start(self, start_paused: bool = False) -> None:
        """Starts the automation loop in a background thread."""
        if self.running: return
        self.running = True
        self.paused = start_paused
        self._stop_event.clear()
        self._wake_event.clear()
        
        # Subscribe to LCU WebSocket events to wake the loop instantly on state changes
        try:
            self.lcu.start_websocket()
            self.lcu.subscribe("OnJsonApiEvent_lol-gameflow_v1_gameflow-phase", self._on_ws_event)
            self.lcu.subscribe("OnJsonApiEvent_lol-champ-select_v1_session", self._on_ws_event)
            self.lcu.subscribe("OnJsonApiEvent_lol-lobby_v2_lobby", self._on_ws_event)
            self.lcu.subscribe("OnJsonApiEvent_lol-matchmaking_v1_search", self._on_ws_event)
            self.lcu.subscribe("OnJsonApiEvent_lol-chat_v1_friends", self._on_ws_event)
        except Exception as e:
            Logger.debug("Auto", f"WebSocket init error: {e}")

        self.discord_rpc.connect()

        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()  # type: ignore

    def _on_ws_event(self, event_name, payload):
        """Called whenever the LCU pushes a state change we care about."""
        self._wake_event.set()

    def stop(self) -> None:
        """Stop the automation engine and clean up resources."""
        self.running = False
        self._stop_event.set()
        self._wake_event.set()
        try:
            self.lcu.stop_websocket()
        except Exception as e:
            Logger.debug("Auto", f"WebSocket stop error (safe to ignore): {e}")
        self.discord_rpc.disconnect()

    def pause(self) -> None:
        """Pauses automation actions without stopping the loop."""
        self.paused = True

    def resume(self) -> None:
        """Resumes automation actions."""
        self.paused = False

    def _log(self, msg: str) -> None:
        log_hook = self.log
        if log_hook is not None:
            log_hook(msg)
        Logger.debug("Auto", msg)

    def _is_game_running(self) -> bool:
        """Check if League of Legends.exe (the game) is running using client_detector helper."""
        from utils.client_detector import is_game_running
        return is_game_running()

    def _loop(self):
        while self.running:
            if self.paused:
                self._stop_event.wait(1)
                continue

            if not self.lcu.is_connected:
                if time.time() - self._last_disconnect_log > 30:
                    Logger.debug("AutoLoop", "LCU Disconnected. Attempting Self-Heal...")
                    self._last_disconnect_log = time.time()

                # ── Auto-Launcher Option ──
                if not self._is_game_running() and (self.config.get("auto_launch_client", False) or self.config.get("auto_launch_league", False)):
                    now = time.time()
                    if now - getattr(self, "_last_autolaunch_time", 0.0) > 30.0:
                        self._last_autolaunch_time = now
                        from utils.client_detector import launch_league_client
                        success, msg = launch_league_client()
                        if success:
                            self._log(f"Auto-Launcher: {msg}")

                if self.lcu.connect(silent=True):
                    Logger.debug("AutoLoop", "Self-Heal Successful: Reconnected to LCU.")
                    default_status = self.config.get("custom_status", "").strip()
                    if default_status:
                        threading.Thread(target=lambda: self.set_custom_status(default_status), daemon=True).start()
                else:
                    # ── Fallback game-process tracking ──
                    # LCU is down but the game (League of Legends.exe) might still
                    # be running under a different PID.  Keep the UI informed.
                    game_alive = self._is_game_running()
                    inferred_phase = "InProgress" if game_alive else "None"

                    # Fire callbacks so the UI / window state stay accurate
                    if inferred_phase != self.last_phase:
                        if inferred_phase == "InProgress":
                            Logger.info("AutoLoop", "Game detected (process). Keeping window visible.")
                        elif self.last_phase == "InProgress":
                            state = "restore_quiet" if self.config.get("stealth_mode", False) else "restore"
                            EventBus.emit("automation_window_state", state)
                            Logger.info("AutoLoop", "Game ended (process). Restoring.")

                    EventBus.emit("automation_queue_state", inferred_phase, None)

                    self.last_phase = inferred_phase
                    if self._stop_event.wait(2.0):
                        break
                continue

            try:
                self._tick()
                self._consecutive_errors = 0  # Reset on success
            except Exception as e:
                # Item #40: Safety killswitch — auto-pause if 5+ errors within 10s
                now = time.time()
                if now - self._first_error_time > 10:
                    self._consecutive_errors = 0
                    self._first_error_time = now
                self._consecutive_errors += 1
                if self._consecutive_errors >= 5:
                    Logger.error("AutoLoop", f"KILLSWITCH: {self._consecutive_errors} consecutive errors in 10s. Auto-pausing.")
                    self._log("⚠ Automation paused (error killswitch).")
                    self.paused = True
                    self._consecutive_errors = 0
                    continue

                # Flood-suppress: only log identical errors once per 30s
                err_key = str(e)
                last_time = self._last_error_times.get(err_key, 0)
                if now - last_time > 30:
                    tb = traceback.format_exc()
                    Logger.error("AutoLoop", f"Critical Error: {e}\n{tb}")
                    self._last_error_times[err_key] = now
                if self._stop_event.wait(3.0):
                    break

    def _tick(self):
        f_phase = self.executor.submit(self.lcu.request, "GET", "/lol-gameflow/v1/gameflow-phase", None, True)
        
        f_lobby = None
        if self.last_phase in ("None", "EndOfGame", "Lobby", "Matchmaking"):
            f_lobby = self.executor.submit(self.lcu.request, "GET", "/lol-lobby/v2/lobby", None, True)

        f_session = None
        if self.last_phase in ("Matchmaking", "ReadyCheck", "ChampSelect"):
            f_session = self.executor.submit(self.lcu.request, "GET", "/lol-champ-select/v1/session", None, True)

        phase_req = f_phase.result()
        phase = phase_req.json() if phase_req and phase_req.status_code == 200 else "None"

        # LCU Ghost ChampSelect Bug Fix: if gameflow says we're in ChampSelect but we have no session, we're actually in the Lobby
        if phase == "ChampSelect":
            if not f_session:
                f_session = self.executor.submit(self.lcu.request, "GET", "/lol-champ-select/v1/session", None, True)
            try:
                sess_req = f_session.result()
                if not sess_req or sess_req.status_code in [404, 500]:
                    Logger.debug("AutoLoop", "Ghost ChampSelect phase detected. Correcting to Lobby.")
                    phase = "Lobby"
            except Exception as e:
                Logger.debug("AutoLoop", f"Ghost ChampSelect check failed: {e}")

        # Cross-check: LCU says "None" but the game process is alive → correct to InProgress.
        # This catches race conditions during game launch / LCU restart transitions.
        if phase == "None" and self._is_game_running():
            Logger.debug("AutoLoop", "LCU reports None but League of Legends.exe is running. Correcting to InProgress.")
            phase = "InProgress"

        search_state = None
        if phase == "Matchmaking":
            search_req = self.lcu.request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state", silent=True)
            if search_req and search_req.status_code == 200:
                search_state = search_req.json()

        EventBus.emit("automation_queue_state", phase, search_state)

        # Auto-minimize/restore based on InProgress state
        if phase != self.last_phase:
            if phase == "InProgress":
                Logger.info("AutoLoop", "Game phase transition to InProgress. Keeping window visible.")
            elif self.last_phase == "InProgress" and phase in ["EndOfGame", "Lobby", "None"]:
                state = "restore_quiet" if self.config.get("stealth_mode", False) else "restore"
                EventBus.emit("automation_window_state", state)
                self._game_pid = None

        self.last_phase = phase
        self._is_first_tick = False
        self._update_discord_rpc(phase)

        lobby_data = None
        if f_lobby:
            try:
                l_req = f_lobby.result()
                if l_req and l_req.status_code == 200:
                    lobby_data = l_req.json()
                    self.current_queue_id = lobby_data.get("gameConfig", {}).get("queueId")
                    members = lobby_data.get("members", [])
                    self._party_puuids = {m.get("puuid") for m in members if m.get("puuid")}
                    EventBus.emit("lobby_event", lobby_data)
            except Exception as e:
                Logger.debug("AutoLoop", f"Lobby data fetch error: {e}")

        session_data = None
        if f_session:
            try:
                sess_req = f_session.result()
                if sess_req and sess_req.status_code == 200:
                    session_data = sess_req.json()
            except Exception as e:
                Logger.debug("AutoLoop", f"Session data fetch error: {e}")

        self._handle_ready_check(phase)
        self._handle_champ_select(phase, session_data)
        self._handle_dodge_requeue(phase)
        self._handle_end_of_game(phase)
        self._check_friend_lobby(phase)

        # Optimization: Websockets will wake us instantly on updates. 
        # These sleep times act as long-polling safety fallbacks.
        sleep_time = TICK_SLEEP_DEFAULT
        if phase == "ChampSelect": sleep_time = max(2.0, TICK_SLEEP_CHAMPSELECT)
        elif phase == "ReadyCheck": sleep_time = max(2.0, TICK_SLEEP_READYCHECK)
        elif phase in ["Lobby", "Matchmaking"]: sleep_time = max(5.0, TICK_SLEEP_LOBBY)
        elif phase == "InProgress": sleep_time = max(10.0, TICK_SLEEP_INGAME)

        # Wait for either stop event, wake event (websocket ping), or timeout
        # We check both to exit cleanly on stop()
        timeout_time = time.time() + sleep_time
        while time.time() < timeout_time:
            if self._stop_event.is_set():
                break
            if self._wake_event.wait(0.1):
                self._wake_event.clear()
                # Throttled wake: avoid slamming if websocket sends 10 events a second
                time.sleep(0.1) 
                break

    def _handle_ready_check(self, phase):
        from .ready_check import handle_ready_check
        return handle_ready_check(self, phase)

    def _handle_dodge_requeue(self, phase):
        from .dodge_requeue import handle_dodge_requeue
        return handle_dodge_requeue(self, phase)

    def _handle_champ_select(self, phase, session):
        from .champ_select import handle_champ_select
        return handle_champ_select(self, phase, session)

    def _check_friend_lobby(self, phase):
        from .friend_lobby import check_friend_lobby
        return check_friend_lobby(self, phase)

    def _handle_end_of_game(self, phase):
        from .end_game import handle_end_of_game
        return handle_end_of_game(self, phase)

    def mass_invite_friends(self):
        """Invite all online friends (or VIP list) to the current lobby."""
        # Item #170: Rate-limit mass invites to prevent API spam
        now = time.time()
        if now - self._last_mass_invite < 10:
            self._log("Mass invite on cooldown (10s).")
            return 0
        self._last_mass_invite = now

        try:
            vip_raw = self.config.get("vip_invite_list", "")
            vip_names = set()
            if vip_raw.strip():
                vip_names = {n.strip().lower() for n in vip_raw.split(",") if n.strip()}

            res = self.lcu.request("GET", "/lol-chat/v1/friends")
            if not res or res.status_code != 200:
                self._log("Failed to fetch friends.")
                return 0
            friends = res.json()

            invitations = []
            for f in friends:
                avail = f.get("availability", "offline")
                if avail == "offline":
                    continue
                game_name = f.get("gameName", "")
                summoner_id = f.get("summonerId", 0)
                if not summoner_id:
                    continue
                if vip_names and game_name.lower() not in vip_names:
                    continue
                invitations.append({
                    "toSummonerId": summoner_id,
                    "state": "Requested",
                })

            if not invitations:
                self._log("No online friends to invite.")
                return 0

            inv_res = self.lcu.request("POST", "/lol-lobby/v2/lobby/invitations", invitations)
            count = len(invitations)
            if inv_res and inv_res.status_code in [200, 204]:
                self._log(f"Invited {count} friend(s) to lobby!")
            else:
                self._log(f"Invite failed (status {inv_res.status_code if inv_res else 'N/A'})")
            return count
        except Exception as e:
            Logger.debug("Auto", f"Mass invite error: {e}")
            self._log("Mass invite failed.")
            return 0

    # ── Custom Status ──
    def set_custom_status(self, status_text: str):
        """Push a custom status message to the League Client."""
        try:
            body = {"statusMessage": status_text}
            res = self.lcu.request("PUT", "/lol-chat/v1/me", body)
            if res and res.status_code in [200, 201]:
                self._log(f"Status → \"{status_text}\"")
            else:
                self._log("Status update failed.")
        except Exception as e:
            Logger.debug("Auto", f"Set status error: {e}")

    def _update_discord_rpc(self, phase: str):
        """Background method to calculate and push Discord Rich Presence States based on LCU Queue State."""
        if not self.config.get("discord_rpc_enabled", True):
            self.discord_rpc.disconnect()
            return

        # Item #171: Guard against reconnect spam — only connect if not already connected
        if not self.discord_rpc.is_connected:
            self.discord_rpc.connect()

        state_text = self.config.get("custom_status", "LeagueLoop API").strip()
        custom_status = f"Phase: {phase}" if not state_text else state_text

        if phase == "None":
            self.discord_rpc.update_presence("Idle", custom_status)
        elif phase == "Lobby":
            lobby = self.lcu.request("GET", "/lol-lobby/v2/lobby", silent=True)
            details = "In Lobby"
            party_size = None
            if lobby and hasattr(lobby, "json"):
                resp = lobby.json()
                members = resp.get("members", [])
                max_party = resp.get("gameConfig", {}).get("maxLobbySize", 5)
                # Ensure it defaults gracefully
                if type(max_party) is not int: max_party = 5
                
                party_size = [len(members), max_party]
                queue_name = resp.get("gameConfig", {}).get("showPositionSelector", False)
                details = f"Lobby - {'Draft/Ranked' if queue_name else 'Blind/ARAM'}"
            self.discord_rpc.update_presence(details, custom_status, party_size=party_size)
        elif phase == "Matchmaking":
            self.discord_rpc.update_presence("In Queue", custom_status, start_time=int(time.time()))
        elif phase == "ReadyCheck":
            self.discord_rpc.update_presence("Match Found!", custom_status)
        elif phase == "ChampSelect":
            self.discord_rpc.update_presence("In Champ Select", custom_status)
        elif phase == "InProgress":
            self.discord_rpc.update_presence("In Game", custom_status, start_time=int(time.time()))
        elif phase == "PreEndOfGame":
            self.discord_rpc.update_presence("Game Ended", custom_status)
        elif phase == "EndOfGame":
            self.discord_rpc.update_presence("Post-Game Lobby", custom_status)

    def _get_local_player(self, session):
        from .champ_select import get_local_player
        return get_local_player(self, session)

    def _equip_random_skin(self, session):
        from .champ_select import equip_random_skin
        return equip_random_skin(self, session)

    def _auto_equip_runes(self, session):
        from .champ_select import auto_equip_runes
        return auto_equip_runes(self, session)

    def _handle_auto_dodge(self, session):
        from .dodge_requeue import handle_auto_dodge
        return handle_auto_dodge(self, session)

    def _handle_chat_warden(self, session):
        from .chat_warden import handle_chat_warden
        return handle_chat_warden(self, session)

    def _perform_arena_synergy(self, session):
        from .draft_assistant import perform_arena_synergy
        return perform_arena_synergy(self, session)

    def _handle_arena_ban(self, session, action, banned_ids):
        from .draft_assistant import handle_arena_ban
        return handle_arena_ban(self, session, action, banned_ids)

    def _handle_arena_pick(self, session, me, action, banned_ids):
        from .draft_assistant import handle_arena_pick
        return handle_arena_pick(self, session, me, action, banned_ids)

    def _perform_draft_assistant(self, session):
        from .draft_assistant import perform_draft_assistant
        return perform_draft_assistant(self, session)

    def _perform_priority_sniper(self, session, priority_list):
        from .draft_assistant import perform_priority_sniper
        return perform_priority_sniper(self, session, priority_list)
