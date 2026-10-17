"""
Save League replays (.rofl) through the League Client.

Replays are only kept for the current patch, and several queues (ARAM: Mayhem
among them) never show up in Riot's match API. The file the client already
records is the timeline. This service asks the client to download it.

It uses two official LCU calls and nothing else:

* ``GET  /lol-replays/v1/metadata/{gameId}``
* ``POST /lol-replays/v1/rofls/{gameId}/download``

The folder is read from ``GET /lol-replays/v1/configuration`` (with
``GET /lol-replays/v1/rofls/path`` as a fallback). Recent games come from the
same match-history endpoint the profile screen already uses.

It does not launch playback, edit the game's config file, or read the game
process. Work starts after a match ends, or when the user clicks the button.
Nothing here runs on a timer during a game.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from core.config_keys import AUTO_SAVE_REPLAYS
from services.profile_service import MATCH_HISTORY_ENDPOINT
from utils.logger import Logger

METADATA_ENDPOINT = "/lol-replays/v1/metadata/{game_id}"
DOWNLOAD_ENDPOINT = "/lol-replays/v1/rofls/{game_id}/download"
CONFIGURATION_ENDPOINT = "/lol-replays/v1/configuration"
ROFLS_PATH_ENDPOINT = "/lol-replays/v1/rofls/path"
EOG_ENDPOINT = "/lol-end-of-game/v1/eog-stats-block"
GAMEFLOW_SESSION_ENDPOINT = "/lol-gameflow/v1/session"

#: What the client's own match-history replay button sends. An empty body is
#: rejected by current clients ("contextData is required").
DOWNLOAD_BODY_COMPONENT = "replay-button_match-history"

#: Metadata states that mean "not ready yet, ask again in a moment".
RETRY_STATES = frozenset({"checking", "lost"})
#: The file is already on disk.
HAVE_STATE = "watch"
#: The client is already writing the file. Don't start a second download.
BUSY_STATE = "downloading"
#: The replay cannot be downloaded. Don't retry these.
SKIP_STATES = frozenset({"incompatible", "missing", "error", "expired"})

#: Brief, bounded. Four tries at two seconds is the whole poll, and it only
#: happens after a game (or on the manual button), never during one.
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_RETRY_DELAY_S = 2.0
DEFAULT_RECENT_LIMIT = 20

OUTCOME_SAVED = "saved"
OUTCOME_STARTED = "started"
OUTCOME_ALREADY = "already"
OUTCOME_UNAVAILABLE = "unavailable"
OUTCOME_FAILED = "failed"
OUTCOME_STOPPED = "stopped"

_SUCCESS_CODES = (200, 201, 204)


def _positive_int(value: Any) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


class ReplaySaver:
    """Download replays the League Client still has."""

    def __init__(
        self,
        lcu: Any,
        config: Any = None,
        *,
        phase_getter: Optional[Callable[[], str]] = None,
        sleep: Callable[[float], None] = None,
        spawn: Optional[Callable[[Callable[[], None]], None]] = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_delay_s: float = DEFAULT_RETRY_DELAY_S,
    ) -> None:
        self._lcu = lcu
        self._config = config
        self._phase_getter = phase_getter
        self._sleep = time.sleep if sleep is None else sleep
        self._spawn = spawn or self._spawn_daemon
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay_s = max(0.0, float(retry_delay_s))

        self._lock = threading.Lock()
        self._busy = False
        self._pending_auto = False
        self._target_game_id: Optional[int] = None
        #: Game ids we already saved or confirmed on disk this session, so a
        #: second end-of-game tick cannot post the download again.
        self._handled: set = set()
        self._listeners: List[Callable[[str, bool], None]] = []
        self.last_message = ""
        self.last_error = False

    # ----------------------------------------------------------------- status
    @property
    def enabled(self) -> bool:
        """True only when the user has opted in. Missing keys stay off.

        ``is True`` rather than ``bool(...)``: a stand-in config object is
        truthy on its own, and that must not turn the feature on.
        """
        config = self._config
        if config is None:
            return False
        try:
            return config.get(AUTO_SAVE_REPLAYS, False) is True
        except Exception:
            return False

    def add_listener(self, listener: Callable[[str, bool], None]) -> None:
        """``listener(message, is_error)`` — called for each status line."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def _publish(self, message: str, is_error: bool = False) -> None:
        self.last_message = message
        self.last_error = bool(is_error)
        for listener in list(self._listeners):
            try:
                listener(message, bool(is_error))
            except Exception as exc:
                Logger.debug("Replay", "Status listener failed.", exc=exc)

    # --------------------------------------------------------------- triggers
    def on_match_ended(self, game_id: Optional[int] = None) -> bool:
        """Download the replay for the match that just finished.

        No-op when the setting is off. Returns False when nothing was started
        (disabled, or a download is already running — that one will pick up
        the pending game when it finishes).
        """
        if not self.enabled:
            return False
        with self._lock:
            if game_id:
                self._target_game_id = _positive_int(game_id)
            if self._busy:
                # The click-to-download job (or an earlier game) is still
                # talking to the client. Pick this match up when it finishes
                # instead of starting a second download.
                self._pending_auto = True
                return False
            self._busy = True
        self._spawn(self._auto_guard)
        return True

    def download_recent(self, limit: int = DEFAULT_RECENT_LIMIT) -> bool:
        """Download replays for the current summoner's recent games.

        Explicit user action: it does not require the auto-save toggle.
        Returns False when a download is already running.
        """
        if not self._try_begin():
            self._publish("A replay download is already running.", False)
            return False
        count = max(1, int(limit))
        self._spawn(lambda: self._recent_guard(count))
        return True

    def replay_folder(self) -> str:
        """The client's replay directory, or "" when it can't be read."""
        _code, body = self._request("GET", CONFIGURATION_ENDPOINT)
        path = _folder_from_configuration(body)
        if path:
            return path
        _code, body = self._request("GET", ROFLS_PATH_ENDPOINT)
        return _folder_from_path(body)

    # --------------------------------------------------------------- workers
    def _auto_guard(self) -> None:
        try:
            self._auto_job()
        except Exception as exc:
            Logger.warning("Replay", "Auto-save failed.", exc=exc)
            self._publish("Couldn't save the replay.", True)
        finally:
            self._finish_job()

    def _recent_guard(self, limit: int) -> None:
        try:
            self._recent_job(limit)
        except Exception as exc:
            Logger.warning("Replay", "Recent-replay download failed.", exc=exc)
            self._publish("Couldn't download recent replays.", True)
        finally:
            self._finish_job()

    def _finish_job(self) -> None:
        with self._lock:
            self._busy = False
            pending = self._pending_auto
            self._pending_auto = False
            target = self._target_game_id
        if pending:
            self.on_match_ended(game_id=target)

    def _auto_job(self) -> None:
        if not self.enabled:
            return
        game_id = self._resolve_current_game_id()
        if not game_id:
            message = "Match ended, but no game id was available to save a replay."
            Logger.warning("Replay", message)
            self._publish(message, True)
            return
        outcome = self._download_game(game_id)
        self._report_one(game_id, outcome)

    def _recent_job(self, limit: int) -> None:
        self._publish("Checking recent games for replays…", False)
        game_ids = self._recent_game_ids(limit)
        if game_ids is None:
            self._publish("Couldn't read recent games from the client.", True)
            return
        if not game_ids:
            self._publish("No recent games to download.", True)
            return

        counts: Dict[str, int] = {}
        for game_id in game_ids:
            if self._in_game():
                self._publish("Stopped: a game is in progress.", True)
                return
            outcome = self._download_game(game_id)
            counts[outcome] = counts.get(outcome, 0) + 1
            Logger.info("Replay", f"Recent game {game_id}: {outcome}")
        failed = counts.get(OUTCOME_FAILED, 0)
        saved = counts.get(OUTCOME_SAVED, 0) + counts.get(OUTCOME_STARTED, 0)
        self._publish(_summary(counts), failed > 0 and saved == 0)

    # ---------------------------------------------------------------- one game
    def _download_game(self, game_id: Any) -> str:
        """Ask the client to download one replay. Never posts twice for it."""
        game_id = _positive_int(game_id)
        if game_id is None:
            return OUTCOME_FAILED
        if self._already_handled(game_id):
            return OUTCOME_ALREADY

        for attempt in range(1, self.max_attempts + 1):
            if self._in_game():
                return OUTCOME_STOPPED
            state = self._metadata_state(game_id)
            decision = _decide(state, attempt >= self.max_attempts)
            if decision == "wait":
                self._sleep(self.retry_delay_s)
                continue
            if decision == "have":
                self._mark_handled(game_id)
                return OUTCOME_ALREADY
            if decision == "busy":
                # The client is already downloading. A second POST would
                # duplicate the request; leave the file to finish.
                self._mark_handled(game_id)
                return OUTCOME_STARTED
            if decision == "skip":
                Logger.info(
                    "Replay",
                    f"Replay for game {game_id} isn't available (state={state or 'unknown'}).",
                )
                return OUTCOME_UNAVAILABLE
            if decision == "fail":
                Logger.warning(
                    "Replay",
                    f"Couldn't read replay metadata for game {game_id}.",
                )
                return OUTCOME_FAILED
            return self._post_and_confirm(game_id)
        return OUTCOME_UNAVAILABLE

    def _post_and_confirm(self, game_id: int) -> str:
        if self._in_game():
            return OUTCOME_STOPPED
        code, _body = self._request(
            "POST",
            DOWNLOAD_ENDPOINT.format(game_id=game_id),
            {
                "gameId": game_id,
                "componentType": DOWNLOAD_BODY_COMPONENT,
            },
        )
        if code in _SUCCESS_CODES:
            self._mark_handled(game_id)
            confirm = self._metadata_state(game_id)
            if confirm == HAVE_STATE:
                Logger.info("Replay", f"Saved replay for game {game_id}.")
                return OUTCOME_SAVED
            Logger.info("Replay", f"Replay download started for game {game_id}.")
            return OUTCOME_STARTED

        confirm = self._metadata_state(game_id)
        if confirm == HAVE_STATE:
            self._mark_handled(game_id)
            return OUTCOME_ALREADY
        if confirm in SKIP_STATES or confirm in RETRY_STATES:
            Logger.info(
                "Replay",
                f"Replay for game {game_id} isn't available (HTTP {code}).",
            )
            return OUTCOME_UNAVAILABLE
        Logger.warning(
            "Replay",
            f"Replay download for game {game_id} was rejected (HTTP {code}).",
        )
        return OUTCOME_FAILED

    def _report_one(self, game_id: int, outcome: str) -> None:
        if outcome == OUTCOME_SAVED:
            message, is_error = f"Saved replay for game {game_id}.", False
        elif outcome == OUTCOME_STARTED:
            message, is_error = f"Downloading replay for game {game_id}.", False
        elif outcome == OUTCOME_ALREADY:
            message, is_error = f"Replay for game {game_id} is already saved.", False
        elif outcome == OUTCOME_UNAVAILABLE:
            message, is_error = f"Replay for game {game_id} isn't available.", True
        elif outcome == OUTCOME_STOPPED:
            message, is_error = "Replay save stopped because a game is in progress.", True
        else:
            message, is_error = f"Couldn't save the replay for game {game_id}.", True
        self._publish(message, is_error)

    # ------------------------------------------------------------------- reads
    def _resolve_current_game_id(self) -> Optional[int]:
        """Game id from explicit target, the post-game screen, or match history."""
        with self._lock:
            target = self._target_game_id
            self._target_game_id = None
        if target:
            return _positive_int(target)

        for attempt in range(1, self.max_attempts + 1):
            if self._in_game():
                return None
            game_id = (
                self._game_id_from_eog()
                or self._game_id_from_session()
                or self._game_id_from_recent()
            )
            if game_id:
                return game_id
            if attempt < self.max_attempts:
                self._sleep(self.retry_delay_s)
        return None

    def _game_id_from_recent(self) -> Optional[int]:
        ids = self._recent_game_ids(1)
        return ids[0] if ids else None

    def _game_id_from_eog(self) -> Optional[int]:
        _code, body = self._request("GET", EOG_ENDPOINT)
        if isinstance(body, dict):
            return _positive_int(body.get("gameId"))
        return None

    def _game_id_from_session(self) -> Optional[int]:
        _code, body = self._request("GET", GAMEFLOW_SESSION_ENDPOINT)
        if not isinstance(body, dict):
            return None
        data = body.get("gameData") or {}
        if not isinstance(data, dict):
            return None
        return _positive_int(data.get("gameId"))

    def _recent_game_ids(self, limit: int) -> Optional[List[int]]:
        """Game ids, newest first. None when the client couldn't be read."""
        endpoint = MATCH_HISTORY_ENDPOINT.format(beg=0, end=max(1, limit) - 1)
        _code, body = self._request("GET", endpoint)
        if not isinstance(body, dict):
            return None
        return _game_ids(body, limit)

    def _metadata_state(self, game_id: int) -> Optional[str]:
        """Lower-case state, "" when the body has none, None when unread."""
        code, body = self._request(
            "GET", METADATA_ENDPOINT.format(game_id=game_id)
        )
        if isinstance(body, dict):
            state = body.get("state")
            if isinstance(state, str):
                return state.strip().lower()
            return ""
        # 404 is the client's "this replay does not exist". Treat it as lost
        # so the brief retry applies, then we skip it.
        if code == 404:
            return "lost"
        return None

    def _request(self, method: str, endpoint: str, data: Any = None):
        lcu = self._lcu
        if lcu is None:
            return None, None
        try:
            response = lcu.request(method, endpoint, data, True)
        except Exception as exc:
            Logger.warning("Replay", f"{method} {endpoint} failed.", exc=exc)
            return None, None
        if response is None:
            return None, None
        try:
            code = int(getattr(response, "status_code", 0) or 0)
        except (TypeError, ValueError):
            return None, None
        if code == 204:
            return code, None
        if code in (200, 201):
            try:
                return code, response.json()
            except Exception:
                return code, None
        return code, None

    # ------------------------------------------------------------------- gates
    def _in_game(self) -> bool:
        getter = self._phase_getter
        if getter is None:
            return False
        try:
            return getter() == "InProgress"
        except Exception:
            return False

    def _already_handled(self, game_id: int) -> bool:
        with self._lock:
            return game_id in self._handled

    def _mark_handled(self, game_id: int) -> None:
        with self._lock:
            self._handled.add(game_id)

    def _try_begin(self) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            return True

    @staticmethod
    def _spawn_daemon(target: Callable[[], None]) -> None:
        threading.Thread(target=target, name="ReplaySaver", daemon=True).start()


def _decide(state: Optional[str], last_attempt: bool) -> str:
    """What to do with one metadata read.

    ``wait``     — checking or lost (or the call failed); try again shortly
    ``have``     — already on disk
    ``busy``     — client is downloading; do not post again
    ``skip``     — not available
    ``fail``     — metadata could not be read
    ``download`` — post the download
    """
    if state == HAVE_STATE:
        return "have"
    if state == BUSY_STATE:
        return "busy" if last_attempt else "wait"
    if state in SKIP_STATES:
        return "skip"
    if state in RETRY_STATES or state is None or state == "":
        if not last_attempt:
            return "wait"
        return "fail" if state is None else "skip"
    return "download"


def _folder_from_configuration(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    path = body.get("replayFolderPath") or body.get("replaysFolderPath") or ""
    return path.strip() if isinstance(path, str) else ""


def _folder_from_path(body: Any) -> str:
    if isinstance(body, str):
        return body.strip()
    if isinstance(body, dict):
        path = body.get("path") or body.get("replayFolderPath") or ""
        return path.strip() if isinstance(path, str) else ""
    return ""


def _game_ids(body: Any, limit: int) -> List[int]:
    if not isinstance(body, dict):
        return []
    games = body.get("games")
    if isinstance(games, dict):
        games = games.get("games")
    if not isinstance(games, list):
        return []
    found: List[int] = []
    for game in games:
        if not isinstance(game, dict):
            continue
        game_id = _positive_int(game.get("gameId"))
        if game_id and game_id not in found:
            found.append(game_id)
        if len(found) >= limit:
            break
    return found


def _summary(counts: Dict[str, int]) -> str:
    saved = counts.get(OUTCOME_SAVED, 0) + counts.get(OUTCOME_STARTED, 0)
    already = counts.get(OUTCOME_ALREADY, 0)
    missing = counts.get(OUTCOME_UNAVAILABLE, 0)
    failed = counts.get(OUTCOME_FAILED, 0)
    parts = []
    if saved:
        noun = "replay" if saved == 1 else "replays"
        parts.append(f"Saved {saved} {noun}")
    if already:
        parts.append(f"{already} already saved")
    if missing:
        parts.append(f"{missing} not available")
    if failed:
        parts.append(f"{failed} failed")
    if not parts:
        return "No replays downloaded."
    return ". ".join(parts) + "."
