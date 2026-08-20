"""
ClientStateService — the missing producer for `ApplicationState`.

The Qt shell renders everything from `core.state.ApplicationState` via
`ShellViewModel` (§2.1 "State First"). That was only ever half a pipeline:
**nothing in the application called `StateManager.update_client()`**, so the
state stayed at its defaults forever. The header said "Disconnected" and the
phase said "Idle" with the League Client open in champ select, and the
follow-the-draft behaviour (§5) could never fire because the phase it watches
for never arrived.

This service is the producer. It owns one background thread that keeps the
LCU connection alive and mirrors the client's reality into `StateManager`:

    connection  -> ClientState.connected / connection_state
    summoner    -> ClientState.summoner_name / ids
    gameflow    -> ClientState.phase
    matchmaking -> QueueState

Design notes:

* **Writes only on change.** Every `update_*` emits STATE_CHANGED, which
  repaints Qt widgets. Polling once a second and writing unconditionally
  would repaint the whole shell once a second for no reason.
* **Backs off while disconnected.** Probing a client that is not running
  every second is wasted work; the idle interval is longer.
* **Summoner is fetched once per connection**, not every tick - it does not
  change while connected, and it is the most expensive of the three calls.
* **Injectable clock and sleep**, so tests do not spend real seconds.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from core.state import ConnectionStateEnum, GameflowPhase
from utils.logger import Logger

#: How often to refresh while the client is reachable.
DEFAULT_POLL_INTERVAL_S = 1.0
#: How often to re-probe while it is not. Deliberately slower.
DEFAULT_IDLE_INTERVAL_S = 3.0

PHASE_ENDPOINT = "/lol-gameflow/v1/gameflow-phase"
SUMMONER_ENDPOINT = "/lol-summoner/v1/current-summoner"
SEARCH_ENDPOINT = "/lol-matchmaking/v1/search"
LOBBY_ENDPOINT = "/lol-lobby/v2/lobby"
CHAMP_SELECT_ENDPOINT = "/lol-champ-select/v1/session"

#: Phases in which no lobby/queue information is meaningful.
_NO_QUEUE_PHASES = (
    GameflowPhase.NONE.value,
    GameflowPhase.IN_PROGRESS.value,
    GameflowPhase.SPECTATING.value,
)


def _summoner_display_name(payload: dict) -> str:
    """
    Riot ID first, falling back to the legacy display name.

    `displayName` has been empty for Riot-ID accounts since the rename, so
    reading it alone gives a blank header on a perfectly connected client.
    """
    game_name = (payload.get("gameName") or "").strip()
    tag_line = (payload.get("tagLine") or "").strip()
    if game_name and tag_line:
        return "{}#{}".format(game_name, tag_line)
    return game_name or (payload.get("displayName") or "").strip()


class ClientStateService:
    """Keeps `ApplicationState` in step with the League Client."""

    def __init__(
        self,
        lcu: Any,
        state_manager: Any,
        automation_controller: Any = None,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        idle_interval_s: float = DEFAULT_IDLE_INTERVAL_S,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
    ):
        self._lcu = lcu
        self._state = state_manager
        # The engine can stop itself (errors, game exit), so the UI cannot
        # rely on controller calls alone to stay truthful.
        self._automation = automation_controller
        self._poll_interval_s = poll_interval_s
        self._idle_interval_s = idle_interval_s
        self._sleep = sleep
        self._now = now

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        # Last values written, so we only publish transitions.
        self._last_connected: Optional[bool] = None
        self._last_phase: Optional[str] = None
        self._last_queue: Optional[tuple] = None
        self._last_automation: Optional[tuple] = None
        self._summoner_loaded = False

    # ------------------------------------------------------------- lifecycle
    def resync(self) -> None:
        """
        Forget what we last published, so the next tick republishes it all.

        "Only write on change" is what keeps the shell from repainting once a
        second, but it means a subscriber that appears *after* the first tick
        sees nothing until something moves. Call this whenever a new consumer
        binds - notably right before `start()`, once the UI exists.
        """
        self._last_connected = None
        self._last_phase = None
        self._last_queue = None
        self._last_automation = None
        self._summoner_loaded = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self.resync()
        self._thread = threading.Thread(
            target=self._loop, name="ClientStateService", daemon=True
        )
        self._thread.start()

    def stop(self, timeout_s: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout_s)
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                connected = self.tick()
            except Exception as exc:  # a bad tick must not kill the loop
                Logger.debug("ClientState", f"poll failed: {exc}")
                connected = False
            self._stop.wait(
                self._poll_interval_s if connected else self._idle_interval_s
            )

    # ------------------------------------------------------------------ poll
    def tick(self) -> bool:
        """One poll cycle. Returns whether the client is currently reachable."""
        self._mirror_automation()
        connected = self._ensure_connected()
        self._publish_connection(connected)

        if not connected:
            self._summoner_loaded = False
            self._publish_phase(GameflowPhase.NONE.value)
            self._publish_queue(None, "", False, 0.0, 0.0)
            return False

        if not self._summoner_loaded:
            self._publish_summoner()

        phase = self._read_phase()
        self._publish_phase(phase)
        self._read_and_publish_queue(phase)
        if phase == GameflowPhase.CHAMP_SELECT.value:
            self._read_and_publish_champ_select()
        return True

    def _mirror_automation(self) -> None:
        """Republish automation flags only when the engine's reality moved."""
        controller = self._automation
        if controller is None:
            return
        engine = getattr(controller, "engine", None)
        key = (
            bool(getattr(engine, "running", False)),
            bool(getattr(engine, "paused", False)),
        )
        if key == self._last_automation:
            return
        self._last_automation = key
        try:
            controller.publish()
        except Exception as exc:
            Logger.debug("ClientState", f"automation publish failed: {exc}")

    def _ensure_connected(self) -> bool:
        try:
            if not getattr(self._lcu, "is_connected", False):
                self._lcu.connect(silent=True)
            return bool(getattr(self._lcu, "is_connected", False))
        except Exception as exc:
            Logger.debug("ClientState", f"connect failed: {exc}")
            return False

    def _get_json(self, endpoint: str):
        try:
            res = self._lcu.request("GET", endpoint, silent=True)
        except Exception:
            return None
        if res is None or getattr(res, "status_code", 0) != 200:
            return None
        try:
            return res.json()
        except Exception:
            return None

    # --------------------------------------------------------------- publish
    def _publish_connection(self, connected: bool) -> None:
        if connected == self._last_connected:
            return
        self._last_connected = connected

        state = ConnectionStateEnum.CONNECTED if connected else ConnectionStateEnum.DISCONNECTED
        try:
            state = self._lcu.connection_state
        except Exception:
            pass

        fields = {"connected": connected, "connection_state": state}
        if not connected:
            # Stale identity on a dead client is worse than none: it reads as
            # "signed in" when the client is gone.
            fields.update(
                summoner_name=None, summoner_id=None, puuid=None, profile_icon_id=0
            )
        self._state.update_client(**fields)

    def _publish_summoner(self) -> None:
        payload = self._get_json(SUMMONER_ENDPOINT)
        if not payload:
            return
        self._summoner_loaded = True
        self._state.update_client(
            summoner_name=_summoner_display_name(payload) or None,
            summoner_id=payload.get("summonerId"),
            puuid=payload.get("puuid"),
            profile_icon_id=payload.get("profileIconId") or 0,
        )

    def _read_phase(self) -> str:
        payload = self._get_json(PHASE_ENDPOINT)
        # The endpoint returns a bare JSON string, e.g. "ChampSelect".
        if isinstance(payload, str) and payload:
            return payload
        return GameflowPhase.NONE.value

    def _publish_phase(self, phase: str) -> None:
        if phase == self._last_phase:
            return
        self._last_phase = phase
        self._state.update_client(phase=phase)

        in_draft = phase == GameflowPhase.CHAMP_SELECT.value
        if in_draft:
            self._state.update_champ_select(active=True)
        else:
            # Reset rather than just flipping `active`: a leftover roster and
            # a frozen timer are worse than an honest empty state (§54).
            self._state.update_champ_select(
                active=False, cell_id=-1, local_role="", timer_remaining_s=0.0,
                locked_in=False, selected_champion_id=0,
                my_team=(), their_team=(), actions=(),
            )

    def _read_and_publish_queue(self, phase: str) -> None:
        if phase in _NO_QUEUE_PHASES:
            self._publish_queue(None, "", False, 0.0, 0.0)
            return

        search = self._get_json(SEARCH_ENDPOINT) or {}
        searching = str(search.get("searchState") or "").lower() == "searching"

        queue_id = None
        lobby = self._get_json(LOBBY_ENDPOINT) or {}
        game_config = lobby.get("gameConfig") or {}
        raw_id = game_config.get("queueId")
        if isinstance(raw_id, int) and raw_id > 0:
            queue_id = raw_id

        self._publish_queue(
            queue_id,
            self._queue_name(queue_id),
            searching,
            float(search.get("estimatedQueueTime") or 0.0),
            float(search.get("timeInQueue") or 0.0),
        )

    # -------------------------------------------------------- champ select
    def _read_and_publish_champ_select(self) -> None:
        """
        Mirror the live draft.

        Published on every tick while the draft is open rather than only on
        change: the timer counts down continuously, so there is no steady
        state to debounce, and this is the one screen where a stale second is
        actually expensive (§80).
        """
        session = self._get_json(CHAMP_SELECT_ENDPOINT)
        if not session:
            return

        cell_id = session.get("localPlayerCellId")
        cell_id = int(cell_id) if isinstance(cell_id, int) else -1

        my_team = tuple(session.get("myTeam") or ())
        their_team = tuple(session.get("theirTeam") or ())
        actions = tuple(
            action
            for group in (session.get("actions") or ())
            for action in (group or ())
        )

        timer = session.get("timer") or {}
        # The LCU reports milliseconds; every consumer here works in seconds.
        remaining_ms = timer.get("adjustedTimeLeftInPhase")
        if not isinstance(remaining_ms, (int, float)):
            remaining_ms = timer.get("timeLeftInPhase") or 0
        remaining_s = max(0.0, float(remaining_ms) / 1000.0)

        me = next(
            (p for p in my_team if p.get("cellId") == cell_id and cell_id >= 0),
            None,
        ) or {}
        selected = me.get("championId") or me.get("championPickIntent") or 0

        locked = any(
            a.get("actorCellId") == cell_id
            and a.get("type") == "pick"
            and a.get("completed")
            for a in actions
        )

        self._state.update_champ_select(
            active=True,
            cell_id=cell_id,
            local_role=str(me.get("assignedPosition") or ""),
            timer_remaining_s=remaining_s,
            locked_in=locked,
            selected_champion_id=int(selected or 0),
            my_team=my_team,
            their_team=their_team,
            actions=actions,
        )

    @staticmethod
    def _queue_name(queue_id: Optional[int]) -> str:
        if queue_id is None:
            return ""
        try:
            from services.queue_manager import resolve_mode_name

            return resolve_mode_name(queue_id)
        except Exception:
            return ""

    def _publish_queue(
        self,
        queue_id: Optional[int],
        queue_name: str,
        is_searching: bool,
        estimated_delay_s: float,
        elapsed_s: float,
    ) -> None:
        # `elapsed_s` ticks every second while queueing, so it is deliberately
        # excluded from the change key - otherwise "did anything change?" is
        # always yes and the shell repaints on every poll.
        key = (queue_id, queue_name, is_searching)
        if key == self._last_queue and not is_searching:
            return
        self._last_queue = key
        self._state.update_queue(
            queue_id=queue_id,
            queue_name=queue_name,
            is_searching=is_searching,
            estimated_delay_s=estimated_delay_s,
            elapsed_s=elapsed_s,
        )
