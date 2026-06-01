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

import psutil

from .api_handler import LCUClient  # type: ignore
from .asset_manager import AssetManager, ConfigManager  # type: ignore
from .discord_rpc import DiscordPresenceManager  # type: ignore
from utils.logger import Logger  # type: ignore
from core.constants import (
    QUEUE_ARENA, QUEUE_DRAFT, QUEUE_RANKED_SOLO, QUEUE_RANKED_FLEX,
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
        """Check if League of Legends.exe (the game) is running.

        This is the actual game process — a different PID from LeagueClient.exe.
        We cache the PID to avoid full process scans every tick.
        """
        now = time.time()

        # Fast-path: reuse cached PID if still alive
        if self._game_pid is not None:
            try:
                p = psutil.Process(self._game_pid)
                if p.is_running() and p.name().lower() == "league of legends.exe":
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            self._game_pid = None

        # Throttle full scans to every 3 seconds
        if now - self._last_game_scan < 3.0:
            return False
        self._last_game_scan = now

        for p in psutil.process_iter(attrs=["name"]):
            try:
                if (p.info["name"] or "").lower() == "league of legends.exe":
                    self._game_pid = p.pid
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, KeyError):
                continue
        return False

    def _loop(self):
        while self.running:
            if self.paused:
                self._stop_event.wait(1)
                continue

            if not self.lcu.is_connected:
                if time.time() - self._last_disconnect_log > 30:
                    Logger.debug("AutoLoop", "LCU Disconnected. Attempting Self-Heal...")
                    self._last_disconnect_log = time.time()

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
                    wf = self.window_func
                    if wf is not None and inferred_phase != self.last_phase:
                        if inferred_phase == "InProgress":
                            # Prevent auto-hiding during a game
                            Logger.info("AutoLoop", "Game detected (process). Keeping window visible.")
                        elif self.last_phase == "InProgress":
                            if self.config.get("stealth_mode", False):
                                wf("restore_quiet")
                            else:
                                wf("restore")
                            Logger.info("AutoLoop", "Game ended (process). Restoring.")

                    qf = self.queue_func
                    if qf is not None:
                        qf(inferred_phase, None)

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
            search_req = self.lcu.request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state")
            if search_req and search_req.status_code == 200:
                search_state = search_req.json()

        qf = self.queue_func
        if qf is not None:
            qf(phase, search_state)

        # Auto-minimize/restore based on InProgress state
        wf = self.window_func
        is_first = getattr(self, "_is_first_tick", True)
        if wf is not None and phase != self.last_phase:
            if phase == "InProgress":
                # Prevent auto-hiding during a game
                Logger.info("AutoLoop", "Game phase transition to InProgress. Keeping window visible.")
            elif self.last_phase == "InProgress" and phase in ["EndOfGame", "Lobby", "None"]:
                if self.config.get("stealth_mode", False):
                    wf("restore_quiet")
                else:
                    wf("restore")
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
                    # Emit so UI components stay in sync even on startup
                    try:
                        from core.events import EventBus
                        EventBus.emit("lobby_event", lobby_data)
                    except Exception as e:
                        pass
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
        if phase != "ReadyCheck":
            if self._accept_timer:
                self._accept_timer.cancel()
                self._accept_timer = None
            self.ready_check_start = None
            self.ready_check_delay = None
            self.ready_check_accepted = False
            self._last_countdown_log = None
            return

        if not self.config.get("auto_accept"): return
        if self._accept_timer or self.ready_check_accepted: return

        self.ready_check_start = time.time()
        base_delay = self.config.get("accept_delay", 2.0)
        delay = base_delay + random.uniform(0.0, 1.5) if base_delay > 0 else 0.0
        self.ready_check_delay = delay
        
        def _do_accept():
            self.lcu.request("POST", "/lol-matchmaking/v1/ready-check/accept")
            self.ready_check_accepted = True
            self._log("Ready Check Accepted!")
            
        self._accept_timer = threading.Timer(delay, _do_accept)
        self._accept_timer.daemon = True
        self._accept_timer.start()

    def _handle_dodge_requeue(self, phase):
        # Auto requeue is stripped out, but we still ensure we re-enter matchmaking
        # if another player dodges and drops us back to the Lobby phase unexpectedly.
        if phase == "Lobby" and self.last_phase in ("ChampSelect", "ReadyCheck"):
            now = time.time()
            if self._cached_search_state and (now - self._last_search_state_time < 3.0):
                state = self._cached_search_state
            else:
                search_state = self.lcu.request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state")
                state = search_state.json() if search_state and search_state.status_code == 200 else None
                self._cached_search_state = state
                self._last_search_state_time = now
            
            if not state or state.get("searchState") != "Searching":
                self.lcu.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
                self._log("Dodge detected. Restarting Matchmaking...")
                self._last_search_state_time = 0

    def _handle_champ_select(self, phase, session):
        if self.paused: return
        if phase != "ChampSelect":
            self.setup_done = False
            self._skin_equipped = False
            self._runes_equipped = False  # Item #167: Reset so runes re-equip next game
            self._chat_warden_warned = False  # Item #166: Reset so toxicity is re-checked next game
            self._bravery_pick_id = 0
            self._last_champ_id = 0
            sf = self.stats_func
            if sf is not None:
                sf([], [])
            return
            
        if not session:
            sf = self.stats_func
            if sf is not None:
                sf([], [])
            return

        # Track champion changes to re-equip runes and skins
        me = self._get_local_player(session)
        my_champ_id = me.get("championId", 0) if me else 0
        if my_champ_id != 0 and my_champ_id != getattr(self, "_last_champ_id", 0):
            self._last_champ_id = my_champ_id
            self._skin_equipped = False
            self._runes_equipped = False

        # 2.2 Blacklist Dodging
        self._handle_auto_dodge(session)
        # 2.3 Chat Warden
        self._handle_chat_warden(session)

        my_team = session.get("myTeam", [])
        bench = session.get("benchChampions", [])
        
        sf2 = self.stats_func
        if sf2 is not None:
            local_cell_id = session.get("localPlayerCellId")
            me = next((p for p in my_team if p.get("cellId") == local_cell_id), None)
            sf2(my_team, bench, me)

        has_bench = len(bench) > 0
        is_arena = self.current_queue_id == QUEUE_ARENA
        is_draft = self.current_queue_id in {QUEUE_DRAFT, QUEUE_RANKED_SOLO, QUEUE_RANKED_FLEX}

        if has_bench and not is_arena:
            # ARAM logic
            priority_cfg = self.config.get("priority_picker", {})
            if priority_cfg.get("enabled", False):
                self._perform_priority_sniper(session, priority_cfg.get("list", []))
        elif is_arena:
            if self.config.get("arena_synergy_enabled", True):
                self._perform_arena_synergy(session)
        elif is_draft:
            self._perform_draft_assistant(session)

        # Auto-equip a non-default skin
        if not self._skin_equipped:
            self._equip_random_skin(session)

        # 2.1 Auto-Equip Runes
        if not self._runes_equipped:
            self._auto_equip_runes(session)

    def _get_local_player(self, session):
        local_cell_id = session.get("localPlayerCellId")
        my_team = session.get("myTeam", [])
        return next((p for p in my_team if p["cellId"] == local_cell_id), None)

    def _equip_random_skin(self, session):
        """Pick a random non-default skin from the available skins for the current champion."""
        try:
            me = self._get_local_player(session)
            if not me:
                return
            champ_id = me.get("championId", 0)
            if not champ_id:
                return

            # Get available skins for this champion
            skins_req = self.lcu.request("GET", f"/lol-champ-select/v1/skin-carousel-skins")
            if not skins_req or skins_req.status_code != 200:
                return

            skins = skins_req.json()
            # Filter to owned/available non-default skins for this champion
            owned_skins = [
                s for s in skins
                if s.get("ownership", {}).get("owned", False)
                and not s.get("isBase", False)
                and s.get("id", 0) != (champ_id * 1000)
                and not s.get("disabled", False)
            ]

            if not owned_skins:
                return

            chosen = random.choice(owned_skins)
            skin_id = chosen.get("id", 0)

            # Patch the skin selection
            self.lcu.request(
                "PATCH",
                f"/lol-champ-select/v1/session/my-selection",
                data={"selectedSkinId": skin_id}
            )
            skin_name = chosen.get("name", f"Skin #{skin_id}")
            self._log(f"Equipped: {skin_name}")
            self._skin_equipped = True

        except Exception as e:
            Logger.error("Auto", f"Skin equip error: {e}")

    def _auto_equip_runes(self, session):
        """Inject baseline recommended runes via LCU."""
        if not self.config.get("auto_runes_enabled", False):
            self._runes_equipped = True
            return

        try:
            me = self._get_local_player(session)
            if not me: return
            champ_id = me.get("championId", 0)
            if not champ_id: return

            # Item #168: Use empty string for ARAM/Arena (no assigned position)
            # so the API returns the best generic page instead of defaulting to UTILITY
            assigned = me.get("assignedPosition", "")
            pos = assigned if assigned else ""
            req = self.lcu.request("GET", f"/lol-perks/v1/recommended-pages/{champ_id}?position={pos}", silent=True)
            if not req or req.status_code != 200: return
            
            recs = req.json()
            if not recs: return

            best_page = recs[0] # Usually the most popular
            
            apply_res = self.lcu.request("POST", f"/lol-perks/v1/recommended-pages/{champ_id}/apply", data={"pageId": best_page.get("id")}, silent=True)
            if apply_res and apply_res.status_code in [200, 204]:
                self._runes_equipped = True
                self._log("Auto-Equipped Recommended Runes!")
        except Exception as e:
            Logger.debug("Auto", f"Rune equip error: {e}")

    def _handle_auto_dodge(self, session):
        if not self._blacklist: return
        
        my_cell = session.get("localPlayerCellId")
        my_team = session.get("myTeam", [])
        
        for p in my_team:
            if p.get("cellId") == my_cell: continue
            
            su_id = p.get("summonerId", 0)
            if not su_id: continue
            
            req = self.lcu.request("GET", f"/lol-summoner/v1/summoners/{su_id}", silent=True)
            if req and req.status_code == 200:
                summoner_data = req.json()  # Item #160: Parse JSON once
                name = summoner_data.get("gameName", "").lower()
                tag = summoner_data.get("tagLine", "").lower()
                full_name = f"{name}#{tag}"
                
                if name in self._blacklist or full_name in self._blacklist:
                    self._log(f"BLACKLIST MATCH: {full_name}. Dodging immediately.")
                    subprocess.run(["taskkill", "/IM", "LeagueClient.exe", "/F"], creationflags=subprocess.CREATE_NO_WINDOW)
                    return

    def _handle_chat_warden(self, session):
        chat_room = session.get("chatDetails", {}).get("chatRoomName")
        if not chat_room: return
        
        if self._chat_warden_warned: return

        req = self.lcu.request("GET", f"/lol-chat/v1/conversations/{chat_room}/messages", silent=True)
        if not req or req.status_code != 200: return
        
        msgs = req.json()
        for m in msgs:
            text = m.get("body", "").lower()
            for kw in self._toxic_keywords:
                if kw in text:
                    self._chat_warden_warned = True
                    self._log(f"Toxicity detected in lobby: '{kw}'")
                    try:
                        from ui.components.toast import ToastManager
                        ToastManager.get_instance().show(f"Toxicity Warning: A teammate typed '{kw}'", theme="error")
                    except Exception as e:
                        Logger.debug("Auto", f"Toast notification failed: {e}")
                    return

    def _perform_arena_synergy(self, session):
        me = self._get_local_player(session)
        if not me:
            return

        actions = session.get("actions", [])
        my_action = None
        for row in actions:
            for action in row:
                if action.get("actorCellId") == me.get("cellId") and not action.get("completed"):
                    my_action = action
                    break
            if my_action:
                break

        if not my_action:
            return

        # Cache banned IDs once for both phases
        banned_ids = []
        for b in session.get("bannedChampions", []):
            if isinstance(b, dict):
                banned_ids.append(b.get("championId", 0))
            else:
                banned_ids.append(b)

        action_type = my_action.get("type", "")
        if action_type == "ban":
            self._handle_arena_ban(session, my_action, banned_ids)
        elif action_type == "pick":
            self._handle_arena_pick(session, me, my_action, banned_ids)
        else:
            # Fallback for empty or unknown action types
            if my_action.get("isAllyAction", True) and not my_action.get("completed"):
                self._log(f"Arena: Unknown action type '{action_type}'. Assuming pick.")
                self._handle_arena_pick(session, me, my_action, banned_ids)

    def _handle_arena_ban(self, session, action, banned_ids):
        arena_ban = self.config.get("arena_ban", "")
        if not arena_ban:
            return
            
        ban_id = self.assets.name_to_id.get(arena_ban.lower(), 0)
        if not ban_id or ban_id in banned_ids:
            return

        now = time.time()
        action_id = action.get("id", 0)
        current_hover = action.get("championId", 0)
        
        timer = session.get("timer", {})
        time_left_ms = timer.get("adjustedTimeLeftInPhase", 15000)
        instant_ban = self.config.get("arena_instant_ban", False)
        
        if current_hover != ban_id and (now - getattr(self, "_last_synergy_patch", 0) > 0.5):
            self._log(f"Arena: Hovering Ban {arena_ban}")
            self.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": ban_id})
            self._last_synergy_patch = now
            self._synergy_patch_time = now
            
        elif current_hover == ban_id:
            time_since_patch = now - getattr(self, "_synergy_patch_time", 0)
            if time_since_patch > 0.5 and (instant_ban or time_left_ms <= 2000) and (now - getattr(self, "_last_synergy_patch", 0) > 0.5):
                log_msg = "(Instant)" if instant_ban else "(<2s left)"
                self._log(f"Arena: Locking Ban {arena_ban} {log_msg}")
                res = self.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": ban_id, "completed": True})
                if res and res.status_code not in (200, 204):
                    Logger.error("Auto", f"Arena ban lock FAILED: {res.status_code} {res.text[:200]}")
                self._last_synergy_patch = now

    def _handle_arena_pick(self, session, me, action, banned_ids):
        action_id = action.get("id", 0)
        current_hover = action.get("championId", 0)
        now = time.time()
        
        my_team = session.get("myTeam", [])
        teammate = next((p for p in my_team if p.get("cellId") != me.get("cellId")), None)
        
        target_id = 0
        if teammate:
            teammate_champ_id = teammate.get("championId", 0)
            teammate_intent = teammate.get("championPickIntent", 0)
            target_id = teammate_champ_id if teammate_champ_id != 0 else teammate_intent
        
        pairs = self.config.get("arena_pairs", [])
        mapped_me_list = []
        
        if target_id != 0:
            teammate_champ_name = self.assets.get_champ_name(target_id)
            if teammate_champ_name:
                teammate_name_lower = teammate_champ_name.lower()
                for pair in pairs:
                    if pair.get("enabled", True) and pair.get("teammate", "").lower() == teammate_name_lower:
                        val = pair.get("me", [])
                        mapped_me_list = val if isinstance(val, list) else [val]
                        break

        if not mapped_me_list:
            fallback = self.config.get("arena_fallback_pick", "")
            if not fallback:
                fallback = self.config.get("auto_pick", "") # Try legacy auto_pick
                
            if fallback:
                mapped_me_list = [fallback]
                
        mapped_my_id, mapped_me_champ = 0, ""
        
        # Try arena pairs or arena fallback first
        if mapped_me_list:
            for champ_name in mapped_me_list:
                if champ_name.lower() in ("bravery", "random"):
                    if getattr(self, "_bravery_pick_id", 0) in banned_ids or getattr(self, "_bravery_pick_id", 0) == target_id:
                        self._bravery_pick_id = 0
                    if not getattr(self, "_bravery_pick_id", 0):
                        req = self.lcu.request("GET", "/lol-champ-select/v1/pickable-champion-ids", silent=True)
                        if req and req.status_code == 200:
                            pickable = req.json()
                            valid = [cid for cid in pickable if cid not in banned_ids and cid != target_id]
                            if valid:
                                self._bravery_pick_id = random.choice(valid)
                    if getattr(self, "_bravery_pick_id", 0):
                        mapped_my_id = self._bravery_pick_id
                        mapped_me_champ = self.assets.get_champ_name(mapped_my_id) or "Random"
                        break
                else:
                    cid = self.assets.name_to_id.get(champ_name.lower())
                    if cid and cid not in banned_ids and cid != target_id:
                        mapped_my_id = cid
                        mapped_me_champ = champ_name
                        break
                    
        # If still 0, try global auto_pick
        if mapped_my_id == 0:
            legacy_fallback = self.config.get("auto_pick", "")
            if legacy_fallback:
                cid = self.assets.name_to_id.get(legacy_fallback.lower())
                if cid and cid not in banned_ids and cid != target_id:
                    mapped_my_id = cid
                    mapped_me_champ = legacy_fallback
                
        timer = session.get("timer", {})
        time_left_ms = timer.get("adjustedTimeLeftInPhase", 15000)
        
        # Check if teammate has locked by inspecting their action
        teammate_locked = False
        if teammate:
            actions = session.get("actions", [])
            for row in actions:
                for act in row:
                    if act.get("actorCellId") == teammate.get("cellId") and act.get("type") == "pick":
                        if act.get("completed", False):
                            teammate_locked = True
                        break
                if teammate_locked:
                    break
                    
        # Fallback to championId check just in case
        if not teammate_locked and target_id != 0 and teammate and teammate.get("championId", 0) != 0:
            teammate_locked = True

        # Handle Hovering
        if mapped_my_id != 0 and current_hover != mapped_my_id:
            if now - getattr(self, "_last_synergy_patch", 0) > 0.5:
                self._log(f"Arena: Selecting {mapped_me_champ}...")
                self.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": mapped_my_id})
                self._last_synergy_patch = now
                self._synergy_patch_time = now
        else:
            # Handle Locking
            if self.config.get("arena_auto_lock", False):
                # Lock if we are hovering something valid, AND (it's our target OR we have no target)
                lock_target = mapped_my_id if mapped_my_id != 0 else current_hover
                
                if lock_target != 0 and current_hover == lock_target:
                    time_since_patch = now - getattr(self, "_synergy_patch_time", 0)
                    if time_since_patch > 0.5 and (time_left_ms <= 2000 or teammate_locked) and (now - getattr(self, "_last_synergy_patch", 0) > 0.5):
                        champ_str = mapped_me_champ if mapped_my_id != 0 else self.assets.get_champ_name(current_hover)
                        log_msg = "(Teammate Locked)" if teammate_locked else "(<2s left)"
                        self._log(f"Arena: Locking Pick {champ_str} {log_msg}")
                        self.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": lock_target, "completed": True})
                        self._last_synergy_patch = now

    def _perform_draft_assistant(self, session):
        me = self._get_local_player(session)
        if not me:
            return

        assigned = me.get("assignedPosition", "")
        if not assigned:
            return
            
        assigned = assigned.upper()
        
        # Find active action for me
        actions = session.get("actions", [])
        my_action = None
        for row in actions:
            for action in row:
                if action.get("actorCellId") == me.get("cellId") and action.get("isInProgress"):
                    my_action = action
                    break
            if my_action:
                break

        if not my_action:
            return

        action_type = my_action.get("type", "")
        action_id = my_action.get("id", 0)
        
        my_team = session.get("myTeam", [])
        banned_champ_ids = []
        for b in session.get("bannedChampions", []):
            if isinstance(b, dict): banned_champ_ids.append(b.get("championId", 0))
            else: banned_champ_ids.append(b)

        now = time.time()

        if action_type == "ban":
            my_cell_id = me.get("cellId")
            teammate_hovers = {
                champ_id
                for p in my_team
                if p.get("cellId") != my_cell_id
                for champ_id in (p.get("championPickIntent", 0), p.get("championId", 0))
                if champ_id > 0
            }
            
            for i in range(1, 4):
                ban_str = self.config.get(f"ban_{assigned}_{i}", "")
                if not ban_str: continue
                ban_id = self.assets.name_to_id.get(ban_str.lower(), 0)
                if not ban_id: continue
                
                if ban_id in banned_champ_ids: continue
                if ban_id in teammate_hovers:
                    self._log(f"Draft: Skipping ban {ban_str} because a teammate is hovering it.")
                    continue
                
                # Prevent spamming
                if my_action.get("championId") != ban_id and (now - self._last_draft_action_time > 0.5):
                    self._log(f"Draft: Hovering Ban {ban_str}")
                    self.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": ban_id})
                    self._last_draft_action_time = now
                elif my_action.get("championId") == ban_id and self.config.get("auto_lock_in", False):
                    if now - self._last_draft_action_time > 0.5:
                        self._log(f"Draft: Locking Ban {ban_str}")
                        self.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": ban_id, "completed": True})
                        self._last_draft_action_time = now
                break

        elif action_type == "pick":
            from itertools import chain
            enemy_team = session.get("theirTeam", [])
            picked_ids = {cid for p in chain(my_team, enemy_team) if (cid := p.get("championId", 0)) > 0}
            
            my_cell_id = me.get("cellId")
            teammate_hovers = {
                champ_id
                for p in my_team
                if p.get("cellId") != my_cell_id
                for champ_id in (p.get("championPickIntent", 0), p.get("championId", 0))
                if champ_id > 0
            }
                    
            for i in range(1, 4):
                pick_str = self.config.get(f"pick_{assigned}_{i}", "")
                if not pick_str: continue
                pick_id = self.assets.name_to_id.get(pick_str.lower(), 0)
                if not pick_id: continue
                
                if pick_id in banned_champ_ids or pick_id in picked_ids or pick_id in teammate_hovers:
                    if pick_id in teammate_hovers:
                        self._log(f"Draft: Skipping pick {pick_str} because a teammate is hovering it.")
                    continue
                
                if my_action.get("championId") != pick_id and (now - self._last_draft_action_time > 0.5):
                    self._log(f"Draft: Hovering Pick {pick_str}")
                    self.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": pick_id})
                    self._last_draft_action_time = now
                elif my_action.get("championId") == pick_id and self.config.get("auto_lock_in", False):
                    if now - self._last_draft_action_time > 0.5:
                        self._log(f"Draft: Locking Pick {pick_str}")
                        self.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": pick_id, "completed": True})
                        self._last_draft_action_time = now
                break

    def _perform_priority_sniper(self, session, priority_list):
        if not priority_list: return
        bench = session.get("benchChampions", [])
        if not bench: return

        me = self._get_local_player(session)
        my_champ_id = me.get("championId", 0) if me else 0
        my_champ_name = self.assets.get_champ_name(my_champ_id) if my_champ_id else ""
        
        # ⚡ Bolt: Fast-path priority sniper early-return optimization.
        # Instead of traversing the entire bench and evaluating every champion against a priority map,
        # we index the bench for O(1) lookups, then walk down the sorted priority list.
        # The first priority champion found on the bench is mathematically guaranteed to be the best,
        # allowing an instant early-return break without further iteration.
        bench_map = {}
        for champ in bench:
            cid = champ.get("championId")
            cname = self.assets.get_champ_name(cid)
            if cname:
                bench_map[cname] = cid

        my_priority_idx = 9999
        try:
            my_priority_idx = priority_list.index(my_champ_name)
        except ValueError:
            pass

        best_bench_champ = None
        best_bench_id = 0
        best_bench_idx = 9999

        for i, target_name in enumerate(priority_list):
            if i >= my_priority_idx:
                # We've reached or passed our current champion's priority.
                # Any further matches would be downgrades.
                break

            if target_name in bench_map:
                # Guaranteed best pick due to priority list ordering
                best_bench_champ = target_name
                best_bench_id = bench_map[target_name]
                best_bench_idx = i
                break

        if best_bench_id != 0:
            now = time.time()

            if now - self._last_priority_swap < PRIORITY_SWAP_COOLDOWN: return
            
            self._log(f"Sniper: Found {best_bench_champ}! Swapping...")
            self.lcu.request("POST", f"/lol-champ-select/v1/session/bench/swap/{best_bench_id}")
            self._last_priority_swap = now
            # Reset skin flag so we re-equip for the new champion
            self._skin_equipped = False

    def _check_friend_lobby(self, phase):
        # We only try to join when not in game/champ select/readycheck
        if phase in ("InProgress", "ChampSelect", "ReadyCheck"):
            return

        if not self.config.get("auto_join_enabled", True):
            return

        friend_list = self.config.get("auto_join_list", [])
        active_friends = [f for f in friend_list if f.get("enabled") and f.get("name", "").strip()]
        if not active_friends:
            return

        from core.state import State
        friends = State.friends

        # Fallback if State is empty (first run before WS push)
        if not friends or not isinstance(friends, list):
            res = self.lcu.request("GET", "/lol-chat/v1/friends", silent=True)
            if res and res.status_code == 200:
                friends = res.json()
                State.friends = friends
            else:
                return

        # ⚡ Bolt: Fast-path priority sniper early-return optimization.
        # Instead of an O(N*M) nested loop evaluating every friend against the priority list,
        # we index the active online friends into an O(1) dictionary mapping their lowercased names.
        friend_map = {}
        for f in friends:
            game_name = f.get("gameName", "") or f.get("name", "")
            game_tag = f.get("gameTag", "")
            combo_name = f"{game_name}#{game_tag}" if game_tag else game_name
            
            friend_map[game_name.lower()] = f
            if combo_name:
                friend_map[combo_name.lower()] = f

        for target_dict in active_friends:
            target_friend = target_dict.get("name", "").strip().lower()
            
            f = friend_map.get(target_friend)
            if not f:
                continue

            game_name = f.get("gameName", "")
            lol = f.get("lol", {})
            if lol.get("ptyType") == "open":
                pty_str = lol.get("pty", "")
                if pty_str:
                    try:
                        pty_data = json.loads(pty_str)
                        party_id = pty_data.get("partyId")
                        if party_id:
                            # Check if we are already in this specific party
                            my_res = self.lcu.request("GET", "/lol-lobby/v2/lobby")
                            if my_res and my_res.status_code == 200:
                                my_lobby = my_res.json()
                                if my_lobby.get("partyId") == party_id:
                                    return  # Already in their party

                            # If we are currently searching for a match, cancel it first
                            if phase == "Matchmaking":
                                self.lcu.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")
                                time.sleep(0.5)

                            # Join party
                            join_res = self.lcu.request("POST", f"/lol-lobby/v2/party/{party_id}/join")
                            if join_res and join_res.status_code in [200, 204]:
                                self._log(f"Auto-joined {game_name}'s Party!")
                                break # Joined a friend, stop iterating the priority list
                    except Exception as e:
                        Logger.debug("Auto", f"Failed parsing friend party: {e}")

    # ── End Of Game ──
    def _handle_end_of_game(self, phase):
        if phase not in ["PreEndOfGame", "EndOfGame"]:
            self._honor_handled = False
            self._honor_attempts = 0
            return

        auto_honor = self.config.get("auto_honor_enabled", False)
        skip_stats = self.config.get("skip_stats_enabled", True)

        if not auto_honor and not skip_stats:
            return

        if self._honor_handled:
            return

        try:
            eog = self.lcu.request("GET", "/lol-end-of-game/v1/eog-stats-block", silent=True)
            if not eog or eog.status_code != 200:
                return
            
            data = eog.json()
            game_id = data.get("gameId")
            
            my_puuid = data.get("localPlayer", {}).get("puuid")
            if not my_puuid:
                me_req = self.lcu.request("GET", "/lol-chat/v1/me")
                if me_req and me_req.status_code == 200:
                    my_puuid = me_req.json().get("puuid")

            teams = data.get("teams", [])
            teammates = []
            
            for team in teams:
                players = team.get("players", [])

                is_my_team = team.get("isPlayerTeam", False)
                if not is_my_team and my_puuid:
                    for p in players:
                        if p.get("puuid") == my_puuid:
                            is_my_team = True
                            break

                if is_my_team:
                    for p in players:
                        puuid = p.get("puuid", "")
                        if puuid and puuid != my_puuid:
                            teammates.append(p)
                    break

            if not teammates:
                self._honor_handled = True
                return

            friend_teammates = []
            friends_res = self.lcu.request("GET", "/lol-chat/v1/friends")
            if friends_res and friends_res.status_code == 200:
                friend_puuids = {f.get("puuid", "") for f in friends_res.json()}
                friend_teammates = [p for p in teammates if p.get("puuid", "") in friend_puuids]
            
            candidates = friend_teammates if friend_teammates else teammates

            if auto_honor:
                strategy = self.config.get("honor_strategy", "random")
                if strategy == "best_kda":
                    def kda(p):
                        """Calculates KDA."""
                        k = p.get("stats", {}).get("CHAMPIONS_KILLED", 0)
                        a = p.get("stats", {}).get("ASSISTS", 0)
                        d = max(p.get("stats", {}).get("NUM_DEATHS", 1), 1)
                        return (k + a) / d
                    target = max(candidates, key=kda)
                elif strategy == "mvp":
                    def score(p):
                        """Calculates score."""
                        s = p.get("stats", {})
                        return s.get("CHAMPIONS_KILLED", 0) + s.get("ASSISTS", 0)
                    target = max(candidates, key=score)
                else:
                    target = random.choice(candidates)

                summoner_id = target.get("summonerId", 0)
                puuid = target.get("puuid", "")
                honor_body = {
                    "gameId": game_id,
                    "honorCategory": "HEART",
                    "honorType": "HEART",
                    "summonerId": summoner_id,
                    "puuid": puuid
                }
                res = self.lcu.request("POST", "/lol-honor-v2/v1/honor-player", honor_body)
                name = target.get("summonerName", "teammate")
                if res and res.status_code in [200, 204]:
                    self._log(f"Honored {name} ({strategy})")
                    self._honor_handled = True
                elif res and res.status_code == 409:
                    self._log(f"Honor already submitted or invalid: {name}")
                    self._honor_handled = True
                elif res and res.status_code == 429:
                    self._log(f"Honor rate limited (429). Retrying next tick...")
                else:
                    Logger.debug("Auto", f"Honor request returned {res.status_code if res else 'None'}. Full target: {name}")
                    self._honor_attempts = getattr(self, "_honor_attempts", 0) + 1
                    if self._honor_attempts >= 3:
                        self._log(f"Honor failed after 3 attempts. Giving up.")
                        self._honor_handled = True
                        self._honor_attempts = 0
            else:
                self._honor_handled = True

            if self._honor_handled:
                if skip_stats:
                    # Auto proceed to lobby ("Play Again")
                    play_again = self.lcu.request("POST", "/lol-lobby/v2/play-again", silent=True)
                    if play_again and play_again.status_code in [200, 204]:
                        self._log("Proceeded to Lobby (Skipped Stats)")

                # Auto-add played champion to ARAM list
                if self.config.get("aram_auto_add_played", False):
                    try:
                        local_player = data.get("localPlayer", {})
                        played_champ_id = local_player.get("championId", 0)
                        if played_champ_id:
                            played_name = self.assets.get_champ_name(played_champ_id)
                            if played_name and played_name != str(played_champ_id):
                                priority_cfg = self.config.get("priority_picker", {})
                                plist = priority_cfg.get("list", [])
                                # Check if already in list (case-insensitive)
                                played_lower = played_name.lower()
                                already_in = any(p.lower() == played_lower for p in plist)
                                if not already_in:
                                    plist.append(played_name)
                                    priority_cfg["list"] = plist
                                    self.config.set("priority_picker", priority_cfg)
                                    self._log(f"ARAM List: Auto-added {played_name}")
                    except Exception as e:
                        Logger.debug("Auto", f"Auto-add played champion error: {e}")
                
        except Exception as e:
            Logger.debug("Auto", f"End of game error: {e}")

    # ── Mass Invite ──
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
            lobby = self.lcu.request("GET", "/lol-lobby/v2/lobby")
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
