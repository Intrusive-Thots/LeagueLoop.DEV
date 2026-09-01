"""
Automation Engine module.
"""
import json
import random
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, List

import psutil

from .api_handler import LCUClient  # type: ignore
from .asset_manager import AssetManager, ConfigManager  # type: ignore
from services.draft.priority_engine import PriorityEngine
from utils.logger import Logger  # type: ignore
from utils.riot_id import resolve_riot_id  # type: ignore
from core.config_keys import (
    ARAM_BENCH_SWAP,
    ARAM_AUTO_REROLL,
    AUTO_HONOR_ENABLED,
    AUTO_JOIN_ENABLED,
    CHAT_WARDEN_ENABLED,
    DODGE_BLACKLIST,
    DODGE_BLACKLIST_ENABLED,
)
from core.constants import (
    QUEUE_ARENA, QUEUE_ARENA_3V6, QUEUE_DRAFT, QUEUE_RANKED_SOLO, QUEUE_RANKED_FLEX,
    TICK_SLEEP_DEFAULT, TICK_SLEEP_CHAMPSELECT,
    TICK_SLEEP_READYCHECK, TICK_SLEEP_LOBBY, TICK_SLEEP_INGAME,
    TICK_SLEEP_SPECTATING, TICK_SLEEP_SPECTATING_MAX,
    PRIORITY_SWAP_COOLDOWN,
)

class AutomationEngine:
    """Core engine for executing automation tasks like auto-accept, priority sniper, draft assistant, and arena synergy."""
    running: bool = False
    paused: bool = False
    last_phase: str = "None"
    current_queue_id: Optional[int] = None
    _blacklist: list = []
    _toxic_keywords: list = ["kys", "int", "troll", "run it down", "nword", "f slur"]
    _chat_warden_warned: bool = False
    ready_check_start: Optional[float] = None
    ready_check_delay: Optional[float] = None
    ready_check_accepted: bool = False
    _accept_timer = None
    _warned_empty_bans: bool = False
    _warned_empty_picks: bool = False
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
        self.db = kwargs.get("db")
        self.draft_engine = PriorityEngine(config_manager=self.config, asset_manager=self.assets)
        self._last_db_telemetry_snapshot = 0.0
        #: One-shot log guards, so an empty list is reported once per draft
        #: rather than every tick or not at all.
        self._warned_empty_bans = False
        self._warned_empty_picks = False
        self._last_reroll_time = 0.0
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
        # Read per draft, not once at construction: the list was previously
        # frozen at startup, so editing it required restarting the app.
        self._blacklist: list = []
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
        self._skin_equipped_for_champ_id: int = 0  # champ ID for which we've already picked a skin
        self._last_priority_swap: float = 0.0
        self._last_priority_swap_target_id: int = 0  # prevent re-swapping same champ before LCU updates
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

        # Game process & spectator tracking
        self._game_pid: Optional[int] = None
        self._last_game_scan: float = 0.0
        self._spectate_start_time: Optional[float] = None

        # Friend auto-join cooldown & tracking
        self._auto_joined_friends_cooldown: dict = {}  # friend_name.lower() -> expiry_timestamp
        self._current_auto_joined_friend: Optional[str] = None
        self._current_auto_joined_party_id: Optional[str] = None

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

        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()  # type: ignore

    def _on_ws_event(self, event_name, payload):
        """Called whenever the LCU pushes a state change we care about."""
        # In-game: only wake on gameflow phase changes (e.g. EndOfGame).
        # Friend list / lobby chatter must not force HTTP ticks mid-match.
        if self.last_phase == "InProgress":
            name = event_name or ""
            if "gameflow-phase" not in name and "gameflow_phase" not in name:
                return
        self._wake_event.set()

    def stop(self) -> None:
        """Stop the automation engine and clean up resources."""
        self.running = False
        self._stop_event.set()
        self._wake_event.set()
        self._cancel_accept_timer()
        try:
            self.lcu.stop_websocket()
        except Exception as e:
            Logger.debug("Auto", f"WebSocket stop error (safe to ignore): {e}")

    def pause(self) -> None:
        """Pauses automation actions without stopping the loop."""
        self.paused = True
        self._cancel_accept_timer()

    def _cancel_accept_timer(self) -> None:
        """A pending ready-check accept must not survive stop or pause."""
        timer, self._accept_timer = getattr(self, "_accept_timer", None), None
        if timer is not None:
            try:
                timer.cancel()
            except Exception as exc:
                Logger.debug("Automation", "_cancel_accept_timer suppressed an error", exc=exc)

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
        game_pid = getattr(self, "_game_pid", None)
        if game_pid is not None:
            try:
                p = psutil.Process(game_pid)
                if p.is_running() and p.name().lower() == "league of legends.exe":
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            self._game_pid = None

        # Throttle full scans to every 3 seconds
        last_scan = getattr(self, "_last_game_scan", 0.0)
        if now - last_scan < 3.0:
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
                    if inferred_phase != self.last_phase:
                        if inferred_phase == "InProgress":
                            # Prevent auto-hiding during a game
                            Logger.info("AutoLoop", "Game detected (process). Keeping window visible.")
                            try:
                                self.lcu.set_in_game_mode(True)
                            except Exception as exc:
                                Logger.debug("Automation", "_loop suppressed an error", exc=exc)
                        elif self.last_phase == "InProgress":
                            try:
                                self.lcu.set_in_game_mode(False)
                            except Exception as exc:
                                Logger.debug("Automation", "_loop suppressed an error", exc=exc)
                            if wf is not None:
                                if self.config.get("stealth_mode", False):
                                    wf("restore_quiet")
                                else:
                                    wf("restore")
                            Logger.info("AutoLoop", "Game ended (process). Restoring.")

                    qf = self.queue_func
                    if qf is not None:
                        qf(inferred_phase, None)

                    self.last_phase = inferred_phase
                    if self._stop_event.wait(5.0 if game_alive else 2.0):
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
        # In-game: process check first; avoid hammering LCU HTTP every tick
        if self.last_phase == "InProgress" and self._is_game_running():
            phase = "InProgress"
            f_lobby = None
            f_session = None
            # Lightweight phase probe only (no lobby/friends/session)
            phase_req = self.lcu.request("GET", "/lol-gameflow/v1/gameflow-phase", None, True)
            if phase_req and phase_req.status_code == 200:
                try:
                    polled = phase_req.json()
                    if isinstance(polled, str) and polled:
                        phase = polled
                except Exception as exc:
                    Logger.debug("Automation", "_tick suppressed an error", exc=exc)
        else:
            f_phase = self.executor.submit(self.lcu.request, "GET", "/lol-gameflow/v1/gameflow-phase", None, True)

            f_lobby = None
            if self.last_phase in ("None", "EndOfGame", "Lobby", "Matchmaking", "PreEndOfGame", "WaitingForStats"):
                f_lobby = self.executor.submit(self.lcu.request, "GET", "/lol-lobby/v2/lobby", None, True)

            f_session = None
            if self.last_phase in ("Matchmaking", "ReadyCheck", "ChampSelect"):
                f_session = self.executor.submit(self.lcu.request, "GET", "/lol-champ-select/v1/session", None, True)

            phase_req = f_phase.result()
            phase = phase_req.json() if phase_req and phase_req.status_code == 200 else "None"

        # LCU Ghost ChampSelect Workaround: if gameflow says we're in ChampSelect but we have no session, we're actually in the Lobby
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
        if phase != self.last_phase:
            if phase == "InProgress":
                # Prevent auto-hiding during a game
                Logger.info("AutoLoop", "Game phase transition to InProgress. Keeping window visible.")
                try:
                    self.lcu.set_in_game_mode(True)
                except Exception as e:
                    Logger.debug("AutoLoop", f"set_in_game_mode(True) failed: {e}")
            elif self.last_phase == "InProgress" and phase in ["EndOfGame", "Lobby", "None", "PreEndOfGame", "WaitingForStats"]:
                try:
                    self.lcu.set_in_game_mode(False)
                except Exception as e:
                    Logger.debug("AutoLoop", f"set_in_game_mode(False) failed: {e}")
                if wf is not None:
                    if self.config.get("stealth_mode", False):
                        wf("restore_quiet")
                    else:
                        wf("restore")
                self._game_pid = None

        # Keep in-game flag consistent even if we entered via process inference
        try:
            self.lcu.set_in_game_mode(phase == "InProgress")
        except Exception as exc:
            Logger.debug("Automation", "_tick suppressed an error", exc=exc)

        if phase != "ChampSelect" and self.last_phase == "ChampSelect":
            # Leaving the draft resets the once-per-draft log guards, so the
            # next draft reports an empty list again instead of staying quiet
            # for the rest of the session.
            self._warned_empty_bans = False
            self._warned_empty_picks = False

        # `_handle_dodge_requeue` needs the phase we were in *before* this
        # tick. Overwriting `last_phase` first made its only guard compare the
        # phase against itself, so auto-requeue-after-dodge never once fired.
        prev_phase = self.last_phase
        self.last_phase = phase
        self._is_first_tick = False

        # Periodic telemetry snapshot to local SQLite DatabaseService
        if getattr(self, "db", None) is not None:
            now_ts = time.time()
            if now_ts - getattr(self, "_last_db_telemetry_snapshot", 0.0) >= 30.0:
                self._last_db_telemetry_snapshot = now_ts
                hist = self.lcu.get_http_latency_histogram() if hasattr(self.lcu, "get_http_latency_histogram") else {}
                ws_tel = self.lcu.get_ws_telemetry() if hasattr(self.lcu, "get_ws_telemetry") else {}
                try:
                    self.db.record_telemetry_snapshot({
                        "timestamp": now_ts,
                        "phase": phase,
                        "latency_avg_ms": hist.get("avg_latency_ms", 0.0),
                        "latency_p95_ms": hist.get("p95_latency_ms", 0.0),
                        "ws_events_total": ws_tel.get("total_events", 0),
                    })
                except Exception as e:
                    Logger.debug("AutoLoop", f"Telemetry DB snapshot failed: {e}")

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
                        Logger.debug("Automation", "_tick suppressed an error", exc=e)
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

        if self.paused:
            # Pause used to be checked inside `_handle_champ_select` alone, so
            # a "paused" engine still accepted ready checks, honored, skipped
            # stats and joined friend lobbies.
            return

        self._handle_ready_check(phase)
        self._handle_champ_select(phase, session_data)
        self._handle_dodge_requeue(phase, prev_phase)
        self._handle_end_of_game(phase)
        self._check_friend_lobby(phase)

        # Optimization: Websockets will wake us instantly on updates. 
        # These sleep times act as long-polling safety fallbacks.
        sleep_time = TICK_SLEEP_DEFAULT
        if phase == "ChampSelect":
            sleep_time = TICK_SLEEP_CHAMPSELECT
            self._spectate_start_time = None
        elif phase == "ReadyCheck":
            sleep_time = TICK_SLEEP_READYCHECK
            self._spectate_start_time = None
        elif phase in ["Lobby", "Matchmaking"]:
            sleep_time = TICK_SLEEP_LOBBY
            self._spectate_start_time = None
        elif phase == "InProgress":
            # Prefer WS phase events; HTTP is a slow safety net only
            sleep_time = max(30.0, TICK_SLEEP_INGAME)
            self._spectate_start_time = None
        elif phase == "Spectating":
            now = time.time()
            if self._spectate_start_time is None:
                self._spectate_start_time = now
            duration = now - self._spectate_start_time
            # Adaptive spectate polling: start at TICK_SLEEP_SPECTATING (15s), scale up to TICK_SLEEP_SPECTATING_MAX (30s)
            adaptive_sleep = TICK_SLEEP_SPECTATING + min(15.0, (duration / 60.0) * 5.0)
            sleep_time = min(adaptive_sleep, TICK_SLEEP_SPECTATING_MAX)
        else:
            self._spectate_start_time = None

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
            # The timer fires seconds later. Emergency stop, pause, or the
            # switch being turned off in the meantime all used to be ignored,
            # so "stop" during the accept delay still accepted the match.
            if not self.running or self.paused:
                return
            if not self.config.get("auto_accept"):
                return
            if not self._act("POST", "/lol-matchmaking/v1/ready-check/accept",
                             what="Accepted the ready check",
                             delay_s=round(delay, 2)):
                return
            self.ready_check_accepted = True
            self._log("Ready Check Accepted!")
            
        self._accept_timer = threading.Timer(delay, _do_accept)
        self._accept_timer.daemon = True
        self._accept_timer.start()

    # ------------------------------------------------------------ actions
    def _act(self, method, endpoint, data=None, *, what="", **detail):
        """Perform a mutating LCU call and record what actually happened.

        Every draft PATCH in this file used to discard its result.
        `LCUClient.request` returns `None` on transport failure and never
        raises, so "Draft: Locking Pick Ahri" was logged whether or not the
        client accepted it — a rejected lock was invisible and never retried.

        Returns True only when the client accepted the call.
        """
        label = what or f"{method} {endpoint}"
        try:
            kwargs = {}
            if data is not None:
                kwargs["data"] = data
            resp = self.lcu.request(method, endpoint, **kwargs)
        except Exception as exc:
            Logger.error("Automation", f"{label} — request failed", exc=exc,
                         endpoint=endpoint, **detail)
            self._log(f"{label} failed: {exc}")
            return False

        if resp is None:
            Logger.warning(
                "Automation",
                f"{label} — no response from the League Client "
                f"(not connected, or the request was queued)",
                endpoint=endpoint, **detail,
            )
            self._log(f"{label} did not reach the client.")
            return False

        code = getattr(resp, "status_code", None)
        if code is not None:
            if type(code).__name__ in ("MagicMock", "Mock"):
                code = 200
        if code is not None and not 200 <= code < 300:
            body = ""
            try:
                body = (resp.text or "")[:200]
            except Exception as exc:
                Logger.debug("Automation", "_act suppressed an error", exc=exc)
            Logger.error(
                "Automation",
                f"{label} — the client refused it (HTTP {code}) {body}".strip(),
                endpoint=endpoint, status=code, **detail,
            )
            self._log(f"{label} was refused by the client (HTTP {code}).")
            return False

        Logger.action("Automation", label, endpoint=endpoint, status=code, **detail)
        return True

    def _handle_dodge_requeue(self, phase, prev_phase=None):
        """Re-enter matchmaking when somebody else dodges the draft.

        Gated on the Auto Requeue switch, which is shown on two screens and
        until now reached nothing at all.
        """
        if not self.config.get("auto_requeue", False):
            return
        if prev_phase is None:
            prev_phase = self.last_phase
        if phase == "Lobby" and prev_phase in ("ChampSelect", "ReadyCheck"):
            now = time.time()
            if self._cached_search_state and (now - self._last_search_state_time < 3.0):
                state = self._cached_search_state
            else:
                search_state = self.lcu.request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state")
                state = search_state.json() if search_state and search_state.status_code == 200 else None
                self._cached_search_state = state
                self._last_search_state_time = now
            
            if not state or state.get("searchState") != "Searching":
                self._act("POST", "/lol-lobby/v2/lobby/matchmaking/search",
                          what="Restarted matchmaking after a dodge")
                self._log("Dodge detected. Restarting Matchmaking...")
                self._last_search_state_time = 0

    def _handle_champ_select(self, phase, session):
        if self.paused: return
        if phase != "ChampSelect":
            # Champ select ended! If Auto-Pick was OFF, auto-sort ARAM priority list for starting match
            tracked = getattr(self, "_tracked_champ_select_data", None)
            if tracked:
                priority_cfg = self.config.get("priority_picker", {})
                if not priority_cfg.get("enabled", False):
                    my_champ = tracked.get("my_champ")
                    bench_champs = tracked.get("bench", [])
                    if my_champ and bench_champs:
                        curr_list = list(priority_cfg.get("list", []))
                        bench_indices = [curr_list.index(c) for c in bench_champs if c in curr_list]
                        if bench_indices:
                            min_bench_idx = min(bench_indices)
                            if my_champ in curr_list:
                                curr_list.remove(my_champ)
                            curr_list.insert(min_bench_idx, my_champ)
                            priority_cfg["list"] = curr_list
                            self.config.set("priority_picker", priority_cfg)
                            self._log(f"Auto-Sorted Priority: Promoted '{my_champ}' above bench champions.")
                self._tracked_champ_select_data = None

            self.setup_done = False
            self._skin_equipped_for_champ_id = 0
            self._runes_equipped = False  # Item #167: Reset so runes re-equip next game
            self._chat_warden_warned = False  # Item #166: Reset so toxicity is re-checked next game
            self._bravery_pick_id = 0
            self._last_champ_id = 0
            self._rejected_draft_picks = set()
            self._rejected_draft_bans = set()
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
            self._runes_equipped = False

        # 2.2 Blacklist Dodging
        self._handle_auto_dodge(session)
        # 2.3 Chat Warden
        self._handle_chat_warden(session)

        my_team = session.get("myTeam", [])
        bench = session.get("benchChampions", [])
        
        # Pre-fetch champion icons during champ select roll phase
        cs_champ_keys = []
        for p in my_team:
            cid = p.get("championId") or p.get("championPickIntent")
            if cid:
                cs_champ_keys.append(cid)
        for b in bench:
            cid = b.get("championId")
            if cid:
                cs_champ_keys.append(cid)
        if cs_champ_keys:
            self.assets.preload_champion_icons(cs_champ_keys)

        sf2 = self.stats_func
        if sf2 is not None:
            local_cell_id = session.get("localPlayerCellId")
            me = next((p for p in my_team if p.get("cellId") == local_cell_id), None)
            sf2(my_team, bench, me)

        has_bench = len(bench) > 0
        queue_id = (
            session.get("queueId")
            or (session.get("gameConfig") or {}).get("queueId")
            or self.current_queue_id
        )
        if queue_id:
            self.current_queue_id = queue_id
        is_arena = queue_id in {QUEUE_ARENA, QUEUE_ARENA_3V6}

        if has_bench and not is_arena:
            # ARAM logic.
            priority_cfg = self.config.get("priority_picker", {})
            bench_enabled = bool(
                self.config.get("aram_bench_swap", True)
                or priority_cfg.get("enabled", False)
                or self.config.get("auto_pick", False)
                or self.config.get("auto_lock_in", False)
            )
            if bench_enabled:
                self._perform_priority_sniper(session, self._aram_priority_names())
                self._maybe_reroll(session, self._aram_priority_names())
            else:
                # Track manually picked champion and bench champions when Auto-Pick is OFF
                local_cell_id = session.get("localPlayerCellId")
                me = next((p for p in my_team if p.get("cellId") == local_cell_id), None)
                my_champ_id = me.get("championId", 0) if me else 0
                my_champ_name = self.assets.get_champ_name(my_champ_id) if my_champ_id else ""
                bench_names = []
                for c in bench:
                    cid = c.get("championId")
                    if cid:
                        name = self.assets.get_champ_name(cid)
                        if name and name != str(cid):
                            bench_names.append(name)
                if my_champ_name and my_champ_name != str(my_champ_id):
                    self._tracked_champ_select_data = {
                        "my_champ": my_champ_name,
                        "bench": bench_names
                    }
        elif is_arena:
            if self.config.get("arena_synergy_enabled", True):
                self._perform_arena_synergy(session)
        else:
            self._perform_draft_assistant(session)

        # Auto-equip a non-default skin — only if we haven't equipped one for this specific champion yet.
        # Using champion ID rather than a simple bool prevents re-equipping stale skins
        # from the old carousel immediately after a bench swap (before LCU reflects the new champion).
        _skin_champ_id = me.get("championId", 0) if me else 0
        if (
            self.config.get("auto_random_skin", True)
            and _skin_champ_id != 0
            and _skin_champ_id != self._skin_equipped_for_champ_id
        ):
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
        if not self.config.get("auto_random_skin", True):
            return

        try:
            me = self._get_local_player(session)
            if not me:
                return
            champ_id = me.get("championId", 0) or me.get("championPickIntent", 0)
            if not champ_id:
                return

            # Get available skins for this champion
            skins_req = self.lcu.request("GET", "/lol-champ-select/v1/skin-carousel-skins")
            if not skins_req or skins_req.status_code != 200:
                Logger.debug("Auto", f"Skin carousel request failed: {getattr(skins_req, 'status_code', 'None')}")
                return

            skins = skins_req.json()
            if not skins or not isinstance(skins, list):
                return

            base_skin_id = champ_id * 1000

            # Filter to owned/available non-default skins for this champion.
            def _is_selectable(s):
                if s.get("isBase", False):
                    return False
                if s.get("disabled", False):
                    return False
                if s.get("id", 0) == base_skin_id:
                    return False
                if s.get("unlocked") is True or s.get("isSelectable") is True or s.get("selected") is True:
                    return True
                ownership = s.get("ownership") or {}
                if isinstance(ownership, dict):
                    if ownership.get("owned") is True or ownership.get("rental", {}).get("rented") is True:
                        return True
                if s.get("owned") is True:
                    return True
                return False

            eligible_skins = [s for s in skins if _is_selectable(s)]
            if not eligible_skins:
                # Fallback: Any non-base, non-disabled skin in carousel
                eligible_skins = [
                    s for s in skins
                    if not s.get("isBase", False)
                    and s.get("id", 0) != base_skin_id
                    and not s.get("disabled", False)
                ]

            if not eligible_skins:
                Logger.debug("Auto", f"No non-default skins found for champ {champ_id} "
                             f"(total carousel entries: {len(skins)})")
                return

            chosen = random.choice(eligible_skins)
            skin_id = chosen.get("id", 0)
            if not skin_id:
                return

            skin_name = chosen.get("name", f"Skin #{skin_id}")
            success = False

            # 1. Primary Endpoint: /lol-champ-select/v1/session/my-selection
            res1 = self.lcu.request("PATCH", "/lol-champ-select/v1/session/my-selection", data={"selectedSkinId": skin_id})
            if res1 and res1.status_code in (200, 201, 204):
                success = True

            # 2. Secondary Endpoint: /lol-champ-select/v1/current-champion/skin
            if not success:
                res2 = self.lcu.request("PATCH", "/lol-champ-select/v1/current-champion/skin", data={"skinId": skin_id, "selectedSkinId": skin_id})
                if res2 and res2.status_code in (200, 201, 204):
                    success = True

            # 3. Action Endpoint: /lol-champ-select/v1/session/actions/{action_id}
            if not success and session:
                try:
                    local_cell_id = session.get("localPlayerCellId")
                    actions = session.get("actions", [])
                    for action_group in actions:
                        for act in action_group:
                            if act.get("actorCellId") == local_cell_id and act.get("type") in ("pick", "intent"):
                                act_id = act.get("id")
                                if act_id:
                                    res3 = self.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{act_id}", data={"selectedSkinId": skin_id})
                                    if res3 and res3.status_code in (200, 201, 204):
                                        success = True
                                        break
                except Exception as exc:
                    Logger.debug("Automation", "_equip_random_skin suppressed an error", exc=exc)

            if success:
                self._log(f"Equipped: {skin_name}")
                self._skin_equipped_for_champ_id = champ_id
                Logger.info("Auto", f"Equipped skin '{skin_name}' ({skin_id}) for champ {champ_id}")
            else:
                Logger.debug("Auto", f"Skin PATCH failed for '{skin_name}' ({skin_id}) via all LCU endpoints")

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

    def _dodge_blacklist(self) -> list:
        """The blacklist as it is configured right now."""
        raw = self.config.get(DODGE_BLACKLIST, "") or ""
        if isinstance(raw, (list, tuple)):
            entries = list(raw)
        else:
            entries = str(raw).split(",")
        self._blacklist = [e.strip().lower() for e in entries if str(e).strip()]
        return self._blacklist

    def _force_close_client(self, reason: str) -> bool:
        """Close the League Client.

        This is the most destructive thing the engine does — it terminates
        the client mid-draft. It used to run unguarded: no switch, no
        try/except, and Windows-only `creationflags` that raise on any other
        platform straight into the tick's error killswitch.
        """
        if sys.platform != "win32":
            Logger.warning(
                "Automation",
                "Refusing to force-close the client: that is Windows-only.",
                reason=reason,
            )
            return False
        try:
            subprocess.run(
                ["taskkill", "/IM", "LeagueClient.exe", "/F"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,
            )
        except Exception as exc:
            Logger.error(
                "Automation", f"Could not close the client ({reason}).", exc=exc
            )
            return False
        Logger.action(
            "Automation", f"Force-closed the League Client: {reason}",
            reason=reason,
        )
        return True

    def _handle_auto_dodge(self, session):
        # Two gates, deliberately. The list alone used to be enough, so a
        # stale value left in config.json would kill the client mid-draft
        # with no way to see the list, let alone clear it.
        if not self.config.get(DODGE_BLACKLIST_ENABLED, False):
            return
        if not self._dodge_blacklist():
            return
        
        my_cell = session.get("localPlayerCellId")
        my_team = session.get("myTeam", [])
        
        su_ids = []
        for p in my_team:
            if p.get("cellId") == my_cell: continue
            
            su_id = p.get("summonerId", 0)
            if not su_id: continue
            
            su_ids.append(su_id)

        if su_ids:
            ids_param = urllib.parse.quote(json.dumps(su_ids))

            req = self.lcu.request("GET", f"/lol-summoner/v2/summoners?ids={ids_param}", silent=True)
            if req and req.status_code == 200:
                summoners_data = req.json()
                # If the API returns a dict unexpectedly (or empty), guard against it
                if not isinstance(summoners_data, list):
                    if isinstance(summoners_data, dict) and "gameName" in summoners_data:
                        summoners_data = [summoners_data]
                    else:
                        summoners_data = []

                # Convert to a lookup dictionary mapping summonerId -> data
                su_lookup = {s.get("summonerId"): s for s in summoners_data if s.get("summonerId")}
                # Some versions of API might not return summonerId inside the list elements, fallback:
                
                for summoner_data in summoners_data:
                    name = summoner_data.get("gameName", "").lower()
                    tag = summoner_data.get("tagLine", "").lower()
                    full_name = f"{name}#{tag}"

                    if name in self._blacklist or full_name in self._blacklist:
                        self._log(f"BLACKLIST MATCH: {full_name}. Dodging immediately.")
                        self._force_close_client(f"blacklisted player {full_name}")
                        return

    def _handle_chat_warden(self, session):
        # Reads every message in the lobby. That is a thing to opt into, not
        # something to do by default with no switch and no screen admitting
        # it happens.
        if not self.config.get(CHAT_WARDEN_ENABLED, False):
            return
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
                        from core.events import EventBus
                        EventBus.emit("toast_requested", f"Toxicity Warning: A teammate typed '{kw}'", "Toxicity Warning", "warning")
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
            self._act("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}",
                      {"championId": ban_id},
                      what=f"Arena: hovered ban {arena_ban}", champion_id=ban_id)
            self._last_synergy_patch = now
            self._synergy_patch_time = now
            
        elif current_hover == ban_id:
            time_since_patch = now - getattr(self, "_synergy_patch_time", 0)
            if time_since_patch > 0.5 and (instant_ban or time_left_ms <= 2000) and (now - getattr(self, "_last_synergy_patch", 0) > 0.5):
                log_msg = "(Instant)" if instant_ban else "(<2s left)"
                self._log(f"Arena: Locking Ban {arena_ban} {log_msg}")
                self._act("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}",
                          {"championId": ban_id, "completed": True},
                          what=f"Arena: banned {arena_ban}", champion_id=ban_id)
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
                self._act("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}",
                          {"championId": mapped_my_id},
                          what=f"Arena: hovered {mapped_me_champ}",
                          champion_id=mapped_my_id)
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
                        self._act("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}",
                                  {"championId": lock_target, "completed": True},
                                  what=f"Arena: locked in {champ_str}",
                                  champion_id=lock_target)
                        self._last_synergy_patch = now

    def _perform_draft_assistant(self, session):
        me = self._get_local_player(session)
        if not me:
            return

        # No assigned position is normal, not a reason to stop: ARAM, blind
        # pick and most rotating modes never assign one. Returning here meant
        # the draft assistant did nothing at all in those modes — which is
        # every ARAM game. PriorityEngine already falls back to the general
        # list when the role is empty.
        assigned = (me.get("assignedPosition") or "").upper()
        
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
            
            # Ban candidates come from the same place the Bans screen writes,
            # via the same engine the UI previews with: PriorityEngine, keyed
            # by `core.config_keys`, working in champion **ids**.
            #
            # This block used to read `ban_{role}_1..3`, then `auto_ban_list`,
            # then `auto_ban_1..15` - three key families, none of which any
            # screen has ever written. It then resolved each entry through
            # `assets.name_to_id`, expecting champion *names*, while the UI
            # stores ids. Auto Ban could not ban anything.
            ban_candidates = []
            if self.config.get("auto_ban_enabled", False):
                try:
                    ban_candidates = self.draft_engine._get_ban_priorities_for_role(
                        assigned or ""
                    )
                except Exception as exc:
                    self._log(f"Draft: could not read your ban list ({exc})")
                    ban_candidates = []

                if not ban_candidates and not self._warned_empty_bans:
                    # Switched on with an empty list is a real state, and a
                    # silent one. Say it once rather than letting the phase
                    # pass with nothing happening.
                    self._warned_empty_bans = True
                    self._log("Draft: Auto Ban is on but your ban list is empty.")

            if not hasattr(self, "_rejected_draft_bans"):
                self._rejected_draft_bans = set()

            for ban_id in ban_candidates:
                ban_id = int(ban_id or 0)
                if ban_id <= 0 or ban_id in self._rejected_draft_bans:
                    continue
                ban_name = self.assets.get_champ_name(ban_id) or str(ban_id)

                if ban_id in banned_champ_ids:
                    continue
                if ban_id in teammate_hovers and self.config.get("auto_ban_respect_hovers", True):
                    self._log(f"Draft: Skipping ban {ban_name} because a teammate is hovering it.")
                    continue

                if my_action.get("championId") != ban_id and (now - self._last_draft_action_time > 0.5):
                    self._log(f"Draft: Hovering Ban {ban_name}")
                    ok = self._act("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}",
                              {"championId": ban_id},
                              what=f"Draft: hovered ban {ban_name}",
                              champion_id=ban_id, role=assigned or "unassigned")
                    self._last_draft_action_time = now
                    if not ok:
                        self._rejected_draft_bans.add(ban_id)
                elif my_action.get("championId") == ban_id:
                    if now - self._last_draft_action_time > 0.5:
                        self._log(f"Draft: Locking Ban {ban_name}")
                        ok = self._act("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}",
                                  {"championId": ban_id, "completed": True},
                                  what=f"Draft: banned {ban_name}",
                                  champion_id=ban_id, role=assigned or "unassigned")
                        self._last_draft_action_time = now
                        if not ok:
                            self._rejected_draft_bans.add(ban_id)
                break

        elif action_type == "pick":
            from itertools import chain
            enemy_team = session.get("theirTeam", [])
            my_cell = me.get("cellId")
            picked_ids = {
                cid
                for p in chain(my_team, enemy_team)
                if p.get("cellId") != my_cell and (cid := p.get("championId", 0)) > 0
            }
            
            my_cell_id = me.get("cellId")
            teammate_hovers = {
                champ_id
                for p in my_team
                if p.get("cellId") != my_cell_id
                for champ_id in (p.get("championPickIntent", 0), p.get("championId", 0))
                if champ_id > 0
            }

            if not hasattr(self, "_rejected_draft_picks"):
                self._rejected_draft_picks = set()
                    
            try:
                decision = self.draft_engine.evaluate_pick(session, rejected_ids=self._rejected_draft_picks)
            except Exception as exc:
                self._log(f"Draft: could not choose a champion ({exc})")
                decision = None

            if decision is None:
                if not self._warned_empty_picks:
                    self._warned_empty_picks = True
                    self._log(
                        "Draft: no champion in your priority list is available."
                    )
            else:
                pick_id = int(decision.champion_id or 0)
                pick_name = self.assets.get_champ_name(pick_id) or str(pick_id)

                blocked = (
                    pick_id in banned_champ_ids
                    or pick_id in picked_ids
                    or (pick_id in teammate_hovers and self.config.get("auto_ban_respect_hovers", True))
                )
                if blocked and pick_id in teammate_hovers:
                    self._log(
                        f"Draft: Skipping pick {pick_name} because a teammate is hovering it."
                    )

                if pick_id > 0 and not blocked:
                    self._warned_empty_picks = False
                    may_lock = bool(
                        self.config.get("auto_lock_in", False)
                        or self.config.get("auto_pick", False)
                        or (self.config.get("priority_picker", {}) or {}).get("enabled", False)
                    )
                    may_hover = bool(
                        self.config.get("auto_hover", False)
                        or may_lock
                    )

                    if my_action.get("championId") != pick_id and may_hover:
                        if now - self._last_draft_action_time > 0.3:
                            self._log(f"Draft: Hovering Pick {pick_name}")
                            ok = self._act("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}",
                                      {"championId": pick_id},
                                      what=f"Draft: hovered {pick_name}",
                                      champion_id=pick_id, role=assigned or "unassigned")
                            self._last_draft_action_time = now
                            if not ok:
                                self._rejected_draft_picks.add(pick_id)
                                self._log(f"Draft: Pick {pick_name} rejected by client, falling back.")
                    elif my_action.get("championId") == pick_id and may_lock:
                        if now - self._last_draft_action_time > 0.3:
                            self._log(f"Draft: Locking Pick {pick_name}")
                            ok = self._act("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}",
                                      {"championId": pick_id, "completed": True},
                                      what=f"Draft: locked in {pick_name}",
                                      champion_id=pick_id,
                                      role=assigned or "unassigned")
                            self._last_draft_action_time = now
                            if not ok:
                                self._rejected_draft_picks.add(pick_id)
                                self._log(f"Draft: Lock {pick_name} rejected by client, falling back.")


    def _aram_priority_names(self):
        """
        The ARAM bench order, as champion names, from all configured lists in priority order.
        """
        from core.config_keys import ARAM_PRIORITY_LIST, PRIORITY_LIST, read_champion_ids

        names = []
        seen = set()

        # 1. ARAM specific IDs
        for cid in read_champion_ids(self.config, ARAM_PRIORITY_LIST, asset_manager=self.assets):
            cname = self.assets.get_champ_name(cid) if self.assets else str(cid)
            if cname and cname != str(cid) and cname.lower() not in seen:
                seen.add(cname.lower())
                names.append(cname)

        # 2. General priority list IDs
        for cid in read_champion_ids(self.config, PRIORITY_LIST, asset_manager=self.assets):
            cname = self.assets.get_champ_name(cid) if self.assets else str(cid)
            if cname and cname != str(cid) and cname.lower() not in seen:
                seen.add(cname.lower())
                names.append(cname)

        # 3. Legacy priority_picker list (names)
        legacy = (self.config.get("priority_picker", {}) or {}).get("list", [])
        for item in legacy:
            name_str = str(item).strip()
            if name_str:
                cid = self.assets.name_to_id.get(name_str.lower(), 0) if (self.assets and hasattr(self.assets, "name_to_id")) else 0
                resolved_name = self.assets.get_champ_name(cid) if (cid and self.assets) else name_str
                if resolved_name and resolved_name.lower() not in seen:
                    seen.add(resolved_name.lower())
                    names.append(resolved_name)

        return names

    #: How far down your ARAM list still counts as an acceptable champion.
    REROLL_ACCEPTABLE_RANK = 3

    def _maybe_reroll(self, session, priority_list):
        """
        Reroll when the champion you were given is not one you wanted.

        "Always Reroll Below Top 3" was a switch on the ARAM screen writing
        `aram_auto_reroll`, a key nothing read — there was no reroll logic in
        the engine at all, only a manual endpoint exposed to the mobile API.

        Rerolling is spendable and irreversible, so this is deliberately
        conservative: only with the switch on, only with points in hand, only
        when the current champion is outside the top of your list, only once
        per session tick, and never when the bench already offers something
        better (the sniper handles that case for free).
        """
        if not self.config.get("aram_auto_reroll", False):
            return
        if not priority_list:
            return
        if int(session.get("rerollsRemaining", 0) or 0) <= 0:
            return

        me = self._get_local_player(session)
        my_champ_id = me.get("championId", 0) if me else 0
        if not my_champ_id:
            return

        my_name = self.assets.get_champ_name(my_champ_id) or ""
        acceptable = priority_list[: self.REROLL_ACCEPTABLE_RANK]
        if my_name in acceptable:
            return

        # A swap is free and a reroll is not; if the bench already holds
        # something acceptable, let the sniper take it instead.
        bench_names = {
            self.assets.get_champ_name(c.get("championId"))
            for c in session.get("benchChampions", []) or []
        }
        if bench_names & set(acceptable):
            return

        now = time.time()
        if now - getattr(self, "_last_reroll_time", 0.0) < 2.0:
            return

        self._log(f"ARAM: Rerolling {my_name or my_champ_id} (not in your top {self.REROLL_ACCEPTABLE_RANK})")
        self._act("POST", "/lol-champ-select/v1/session/my-selection/reroll",
                  what=f"ARAM: rerolled {my_name or my_champ_id}",
                  champion_id=my_champ_id)
        self._last_reroll_time = now

    def _perform_priority_sniper(self, session, priority_list):
        if not priority_list: return
        bench = session.get("benchChampions", [])
        if not bench: return

        me = self._get_local_player(session)
        my_champ_id = me.get("championId", 0) if me else 0
        my_champ_name = self.assets.get_champ_name(my_champ_id) if my_champ_id else ""

        # If the session has caught up and we now hold the champion we swapped to,
        # clear the pending-swap guard so future swaps can fire normally.
        if my_champ_id and my_champ_id == self._last_priority_swap_target_id:
            self._last_priority_swap_target_id = 0

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

            if now - self._last_priority_swap < PRIORITY_SWAP_COOLDOWN:
                return

            # Guard: don't re-fire for the same target when the LCU session hasn't
            # reflected the swap yet. This is the root cause of repeated swap log spam —
            # the polling loop sees stale session data for 1-2 ticks after the swap.
            if best_bench_id == self._last_priority_swap_target_id:
                return

            self._log(f"Sniper: Found {best_bench_champ}! Swapping...")
            self._act("POST", f"/lol-champ-select/v1/session/bench/swap/{best_bench_id}",
                      what=f"ARAM: swapped to {best_bench_champ} from the bench",
                      champion_id=best_bench_id)
            self._last_priority_swap = now
            self._last_priority_swap_target_id = best_bench_id
            # Clear skin guard so we re-equip once the session confirms the new champion.
            # Using 0 (not the target ID) ensures we wait for real confirmation before equipping.
            self._skin_equipped_for_champ_id = 0

    def leave_friend_lobby_and_cooldown(self, friend_name: Optional[str] = None) -> bool:
        """
        Leaves any current lobby and places a 5-minute auto-join cooldown on all friends/party IDs,
        pausing auto-join for 30 seconds so match search and lobby creation can complete undisturbed.
        """
        now = time.time()
        if getattr(self, "_auto_joined_friends_cooldown", None) is None:
            self._auto_joined_friends_cooldown = {}

        # 1. Immediately pause auto-join for 30 seconds
        self._pause_auto_join_until = now + 30.0

        # 2. Immediately collect current auto-joined friend and party_id for 5-minute cooldown
        current_friend = getattr(self, "_current_auto_joined_friend", None)
        current_party_id = getattr(self, "_current_auto_joined_party_id", None)

        friends_to_cooldown = set()
        if friend_name:
            fn = friend_name.strip().lower()
            friends_to_cooldown.add(fn)
            friends_to_cooldown.add(fn.split("#")[0])

        if current_friend:
            cf = current_friend.strip().lower()
            friends_to_cooldown.add(cf)
            friends_to_cooldown.add(cf.split("#")[0])

        if current_party_id:
            friends_to_cooldown.add(current_party_id.strip().lower())

        # Check LCU lobby for additional members and party ID
        if self.lcu and getattr(self.lcu, "is_connected", False):
            try:
                my_res = self.lcu.request("GET", "/lol-lobby/v2/lobby", silent=True)
                if my_res and my_res.status_code == 200:
                    my_lobby = my_res.json()
                    p_id = my_lobby.get("partyId")
                    if p_id:
                        friends_to_cooldown.add(p_id.strip().lower())

                    local_member = my_lobby.get("localMember", {})
                    local_puuid = local_member.get("puuid")
                    local_id = local_member.get("summonerId")
                    members = my_lobby.get("members", [])

                    for m in members:
                        m_puuid = m.get("puuid")
                        m_id = m.get("summonerId")
                        if (local_puuid and m_puuid == local_puuid) or (local_id and m_id == local_id):
                            continue
                        g_name = (m.get("gameName") or m.get("summonerName") or m.get("name") or "").strip()
                        g_tag = (m.get("gameTag") or "").strip()
                        if g_name:
                            friends_to_cooldown.add(g_name.lower())
                            if g_tag:
                                friends_to_cooldown.add(f"{g_name}#{g_tag}".lower())
            except Exception as e:
                Logger.debug("Auto", f"Lobby member check error: {e}")

        # Lock in 5-minute cooldown for all identifiers
        for fn in friends_to_cooldown:
            if fn:
                self._auto_joined_friends_cooldown[fn] = now + 300.0  # 5 minutes

        self._current_auto_joined_friend = None
        self._current_auto_joined_party_id = None

        # Execute lobby leaves
        if self.lcu and getattr(self.lcu, "is_connected", False):
            try:
                self.lcu.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search", silent=True)
                time.sleep(0.15)
                self.lcu.request("DELETE", "/lol-lobby/v2/lobby", silent=True)
                time.sleep(0.25)
            except Exception as exc:
                Logger.debug("Automation", "leave_friend_lobby_and_cooldown suppressed an error", exc=exc)

        if friends_to_cooldown:
            names_str = ", ".join(sorted(friends_to_cooldown))
            self._log(f"Paused auto-joining {names_str} for 5 minutes.")
            Logger.info("AutoJoin", f"Applied 5-minute auto-join cooldown to: {names_str}")

        return True

    def reset_auto_join_cooldowns(self, name: Optional[str] = None) -> None:
        """Clears 5-minute auto-join cooldown timers for a specific friend or all friends."""
        if getattr(self, "_auto_joined_friends_cooldown", None) is None:
            self._auto_joined_friends_cooldown = {}

        self._pause_auto_join_until = 0.0

        if name:
            key = name.strip().lower()
            self._auto_joined_friends_cooldown.pop(key, None)
            base_key = key.split("#")[0]
            self._auto_joined_friends_cooldown.pop(base_key, None)
            self._log(f"Cleared auto-join cooldown for friend '{name}'.")
            Logger.info("AutoJoin", f"Cleared auto-join cooldown for '{name}'.")
        else:
            self._auto_joined_friends_cooldown.clear()
            self._log("Cleared all friend auto-join cooldown timers.")
            Logger.info("AutoJoin", "Cleared all friend auto-join cooldown timers.")

    def _check_friend_lobby(self, phase):
        # We only try to join when not in game/champ select/readycheck
        if phase in ("InProgress", "ChampSelect", "ReadyCheck"):
            return

        if not self.config.get(AUTO_JOIN_ENABLED, False):
            return

        now = time.time()

        # Check temporary pause flag (e.g. while match search / lobby creation is in progress)
        if now < getattr(self, "_pause_auto_join_until", 0.0):
            return

        # Defensive initialization for cooldown dict
        if getattr(self, "_auto_joined_friends_cooldown", None) is None:
            self._auto_joined_friends_cooldown = {}

        # Purge expired cooldowns
        self._auto_joined_friends_cooldown = {
            name: exp for name, exp in self._auto_joined_friends_cooldown.items()
            if exp > now
        }

        # Check if we are still in our auto-joined lobby
        if getattr(self, "_current_auto_joined_party_id", None):
            my_res = self.lcu.request("GET", "/lol-lobby/v2/lobby", silent=True)
            if my_res and my_res.status_code == 200:
                my_lobby = my_res.json()
                if my_lobby.get("partyId") != self._current_auto_joined_party_id:
                    self._current_auto_joined_party_id = None
                    self._current_auto_joined_friend = None
            else:
                self._current_auto_joined_party_id = None
                self._current_auto_joined_friend = None

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

        # Fast-path priority sniper indexing
        friend_map = {}
        for f in friends:
            game_name = f.get("gameName", "") or f.get("name", "")
            game_tag = f.get("gameTag", "")
            combo_name = f"{game_name}#{game_tag}" if game_tag else game_name
            
            friend_map[game_name.lower()] = f
            if combo_name:
                friend_map[combo_name.lower()] = f

        for target_dict in active_friends:
            raw_name = target_dict.get("name", "").strip().lower()
            base_name = raw_name.split("#")[0] if "#" in raw_name else raw_name

            f = friend_map.get(raw_name) or friend_map.get(base_name)
            if not f:
                continue

            game_name = f.get("gameName", "") or f.get("name", "")
            game_tag = f.get("gameTag", "")
            combo_name = f"{game_name}#{game_tag}" if game_tag else game_name

            lol = f.get("lol", {})
            if lol.get("ptyType") == "open":
                pty_str = lol.get("pty", "")
                if pty_str:
                    try:
                        pty_data = json.loads(pty_str)
                        party_id = pty_data.get("partyId", "")

                        # Check if friend, combo name, or party_id is on 5-minute cooldown
                        on_cooldown = False
                        for name_variant in (raw_name, base_name, game_name.lower(), combo_name.lower(), party_id.lower() if party_id else ""):
                            if name_variant and name_variant in self._auto_joined_friends_cooldown:
                                if now < self._auto_joined_friends_cooldown[name_variant]:
                                    on_cooldown = True
                                    break

                        if on_cooldown:
                            continue

                        if party_id:
                            # Check if we are already in this specific party
                            my_res = self.lcu.request("GET", "/lol-lobby/v2/lobby")
                            if my_res and my_res.status_code == 200:
                                my_lobby = my_res.json()
                                if my_lobby.get("partyId") == party_id:
                                    self._current_auto_joined_party_id = party_id
                                    self._current_auto_joined_friend = combo_name
                                    return  # Already in their party

                            # If we are currently searching for a match, cancel it first
                            if phase == "Matchmaking":
                                self.lcu.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")
                                time.sleep(0.5)

                            # Join party
                            join_res = self.lcu.request("POST", f"/lol-lobby/v2/party/{party_id}/join")
                            if join_res and join_res.status_code in [200, 204]:
                                self._log(f"Auto-joined {game_name}'s Party!")
                                self._current_auto_joined_party_id = party_id
                                self._current_auto_joined_friend = combo_name
                                break # Joined a friend, stop iterating the priority list
                    except Exception as e:
                        Logger.debug("Auto", f"Failed parsing friend party: {e}")

    # ── End Of Game ──
    def _handle_end_of_game(self, phase):
        if phase not in ["PreEndOfGame", "EndOfGame"]:
            self._honor_handled = False
            self._honor_attempts = 0
            return

        auto_honor = self.config.get(AUTO_HONOR_ENABLED, True)
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

            # Persist match history to local SQLite DatabaseService
            if getattr(self, "db", None) is not None and game_id:
                try:
                    local_player = data.get("localPlayer", {})
                    champ_id = local_player.get("championId")
                    if champ_id:
                        stats = local_player.get("stats", {})
                        is_win = False
                        for team in data.get("teams", []):
                            if team.get("isPlayerTeam", False):
                                is_win = team.get("isWinningTeam", False) or bool(team.get("win"))
                                break
                        champ_name = (
                            self.assets.get_champ_name(champ_id)
                            if hasattr(self.assets, "get_champ_name")
                            else str(champ_id)
                        )
                        match_rec = {
                            "game_id": game_id,
                            "timestamp": time.time(),
                            "queue_id": data.get("queueId", getattr(self, "current_queue_id", None)),
                            "champion_id": champ_id,
                            "champion_name": champ_name,
                            "role": local_player.get("role", "") or local_player.get("position", ""),
                            "win": is_win,
                            "kills": stats.get("CHAMPIONS_KILLED", 0),
                            "deaths": stats.get("NUM_DEATHS", 0),
                            "assists": stats.get("ASSISTS", 0),
                            "duration_s": data.get("gameLength", 0),
                            "raw_json": data,
                        }
                        self.db.record_match(match_rec)
                except Exception as db_err:
                    Logger.debug("AutoLoop", f"Match DB record error: {db_err}")
            
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
                name = resolve_riot_id(target, fallback=target.get("summonerName") or "teammate")
                champ_id = target.get("championId", 0)
                champ_name = ""
                if champ_id:
                    getter = getattr(getattr(self, "assets", None), "get_champ_name", None)
                    if callable(getter):
                        try:
                            c_res = getter(champ_id)
                            if isinstance(c_res, str) and c_res and c_res != str(champ_id):
                                champ_name = c_res
                        except Exception as exc:
                            Logger.debug("Auto", "Failed to resolve champ name", exc=exc)
                if not champ_name:
                    raw_champ = target.get("championName") or target.get("skinName")
                    if raw_champ and isinstance(raw_champ, str):
                        champ_name = raw_champ.strip()

                target_str = f"{name} ({champ_name})" if champ_name else name

                if res and res.status_code in [200, 204]:
                    self._log(f"Honored {target_str} ({strategy})")
                    self._honor_handled = True
                elif res and res.status_code == 409:
                    self._log(f"Honor already submitted or invalid: {target_str}")
                    self._honor_handled = True
                elif res and res.status_code == 429:
                    self._log(f"Honor rate limited (429). Retrying next tick...")
                else:
                    Logger.debug("Auto", f"Honor request returned {res.status_code if res else 'None'}. Full target: {target_str}")
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
