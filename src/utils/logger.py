"""
Logging
=======

Every run of LeagueLoop leaves a complete, timestamped record on disk.

What gets written, and where
----------------------------
All three files live in ``%LOCALAPPDATA%\\LeagueLoop\\logs`` (falling back to
``%TEMP%\\LeagueLoop\\logs`` if that is not writable). ``Logger.log_dir()``
returns the resolved path; ``Logger.paths()`` returns all three.

``debug.log``
    Everything, human readable, one line per record::

        2026-08-21 19:47:03.418 -0700  INFO   MainThread    [Automation] Draft: locked in Ahri (103)

    Rotates at 10 MB, keeps 5 backups.

``error.log``
    WARNING and above only, with full tracebacks. This is the file to read
    first when something went wrong. Rotates at 4 MB, keeps 5 backups.

``session.jsonl``
    One JSON object per record, for tooling::

        {"ts":"2026-08-21T19:47:03.418-07:00","level":"INFO","tag":"Automation",
         "thread":"AutoLoop","session":"a3f9c1","msg":"...","elapsed_s":12.4}

    Rotates at 20 MB, keeps 3 backups.

Why the format is what it is
----------------------------
The previous formatter used ``datefmt='%H:%M:%S'`` — **no date**, so a log
covering two sessions on different days was unreadable, and it omitted the
level name entirely, so an ERROR and a DEBUG line were indistinguishable.
Both are fixed here, and the timestamp carries milliseconds and the UTC
offset so records can be lined up against the League client's own logs.

Session boundaries
------------------
Each run writes a banner on start and a summary on exit (see
``session_banner`` / ``session_summary``), so you can always tell where one
run ended and the next began, what version it was, and how it finished.

Recording failures
------------------
``Logger.error`` and ``Logger.warning`` accept an ``exc``:

    except Exception as exc:
        Logger.error("Loot", "Craft failed", exc=exc)

which writes the full traceback to ``error.log``. ``Logger.exception`` is
shorthand for the same thing from inside an ``except`` block.

Thread safety
-------------
The in-memory ring buffer is guarded by a lock. It is read by the
Diagnostics screen and by the support-bundle export, both on the GUI thread,
while services write to it from worker threads.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------- constants

#: Levels, in order. Used for the per-session tallies.
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "ACTION")

DEBUG_LOG_MAX_BYTES = 10 * 1024 * 1024
ERROR_LOG_MAX_BYTES = 4 * 1024 * 1024
JSONL_LOG_MAX_BYTES = 20 * 1024 * 1024

#: A short id for this run, so interleaved files can be untangled.
SESSION_ID = uuid.uuid4().hex[:8]

#: Wall-clock start of this process, for `elapsed_s` on every record.
STARTED_AT = time.time()
STARTED_AT_ISO = datetime.now().astimezone().isoformat(timespec="milliseconds")


# ------------------------------------------------------------ log location

def _resolve_log_dir() -> str:
    """Pick a writable directory, preferring %LOCALAPPDATA%/LeagueLoop/logs."""
    appdata = os.environ.get(
        "LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local")
    )
    candidates = [
        os.environ.get("LEAGUELOOP_LOG_DIR"),
        os.path.join(appdata, "LeagueLoop", "logs"),
        os.path.join(tempfile.gettempdir(), "LeagueLoop", "logs"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            os.makedirs(candidate, exist_ok=True)
            probe = os.path.join(candidate, ".writetest")
            with open(probe, "w", encoding="utf-8") as handle:
                handle.write("ok")
            os.remove(probe)
            return candidate
        except Exception:
            continue
    # Last resort: the working directory. Logging must never be the thing
    # that stops the app from starting.
    return os.getcwd()


_LOG_DIR = _resolve_log_dir()

DEBUG_LOG_PATH = os.path.join(_LOG_DIR, "debug.log")
ERROR_LOG_PATH = os.path.join(_LOG_DIR, "error.log")
JSONL_LOG_PATH = os.path.join(_LOG_DIR, "session.jsonl")


# ---------------------------------------------------------------- handlers

class _LocalTimeFormatter(logging.Formatter):
    """Full local timestamp with milliseconds and UTC offset."""

    def formatTime(self, record, datefmt=None):  # noqa: N802 (stdlib name)
        stamp = datetime.fromtimestamp(record.created).astimezone()
        if datefmt:
            return stamp.strftime(datefmt)
        return stamp.strftime("%Y-%m-%d %H:%M:%S.") + (
            "%03d %s" % (record.msecs, stamp.strftime("%z"))
        )


class _JsonLinesFormatter(logging.Formatter):
    """One JSON object per record, for tooling and the support bundle."""

    def format(self, record: logging.LogRecord) -> str:
        stamp = datetime.fromtimestamp(record.created).astimezone()
        payload: Dict[str, Any] = {
            "ts": stamp.isoformat(timespec="milliseconds"),
            "level": getattr(record, "ll_level", record.levelname),
            "tag": getattr(record, "ll_tag", ""),
            "thread": record.threadName,
            "session": SESSION_ID,
            "elapsed_s": round(record.created - STARTED_AT, 3),
            "msg": getattr(record, "ll_msg", record.getMessage()),
        }
        detail = getattr(record, "ll_detail", None)
        if detail:
            payload["detail"] = detail
        if record.exc_info:
            payload["traceback"] = "".join(
                traceback.format_exception(*record.exc_info)
            ).rstrip()
        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            # A record must never be lost because a value would not serialise.
            return json.dumps(
                {"ts": payload["ts"], "level": payload["level"],
                 "msg": str(payload.get("msg"))[:2000]}
            )


class _LevelNameFilter(logging.Filter):
    """Show our own level names in the level column.

    `ACTION` rides on stdlib INFO so filtering and rotation behave normally,
    but a line that changed the user's account should not be indistinguishable
    from an ordinary status message when you are reading the file.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        own = getattr(record, "ll_level", None)
        if own:
            record.levelname = own
        return True


_TEXT_FORMAT = "%(asctime)s  %(levelname)-8s %(threadName)-14s %(message)s"

_logger = logging.getLogger("LeagueLoop")
_logger.propagate = False
_logger.addFilter(_LevelNameFilter())

_level_name = os.environ.get("LOG_LEVEL", "DEBUG").upper()
_logger.setLevel(getattr(logging, _level_name, logging.DEBUG))

_handler_errors: List[str] = []


def _add_handler(handler: logging.Handler, level: int, formatter) -> None:
    handler.setLevel(level)
    handler.setFormatter(formatter)
    _logger.addHandler(handler)


if not _logger.handlers:
    text_formatter = _LocalTimeFormatter(_TEXT_FORMAT)

    for path, max_bytes, backups, level, formatter in (
        (DEBUG_LOG_PATH, DEBUG_LOG_MAX_BYTES, 5, logging.DEBUG, text_formatter),
        (ERROR_LOG_PATH, ERROR_LOG_MAX_BYTES, 5, logging.WARNING, text_formatter),
        (JSONL_LOG_PATH, JSONL_LOG_MAX_BYTES, 3, logging.DEBUG, _JsonLinesFormatter()),
    ):
        try:
            _add_handler(
                RotatingFileHandler(
                    path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8",
                    delay=True,
                ),
                level,
                formatter,
            )
        except Exception as exc:  # a locked or read-only file must not be fatal
            _handler_errors.append(f"{os.path.basename(path)}: {exc}")

    # The console stays terse: level, tag and message, no timestamps, and
    # INFO and above only, so running from a terminal is readable. The files
    # keep everything regardless of what the console shows.
    console_level = os.environ.get("LOG_CONSOLE_LEVEL", "INFO").upper()
    try:
        console = logging.StreamHandler()
        _add_handler(
            console,
            getattr(logging, console_level, logging.INFO),
            logging.Formatter("%(levelname)-8s %(message)s"),
        )
    except Exception as exc:
        _handler_errors.append(f"console: {exc}")


# ------------------------------------------------------------------ Logger

class Logger:
    """Application logging.

    The classmethod API (`debug`/`info`/`warning`/`error`) is unchanged from
    the original module so existing call sites keep working; `exc=` and
    `detail=` are new and optional.
    """

    MAX_LOGS = 2000

    _logs: List[Dict[str, Any]] = []
    _lock = threading.RLock()
    _counts: Dict[str, int] = {level: 0 for level in LEVELS}

    # ------------------------------------------------------------ internals

    @classmethod
    def _record(
        cls,
        level: str,
        tag: str,
        msg: Any,
        exc: Optional[BaseException] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        text = str(msg)
        stamp = datetime.now().astimezone()

        # `ACTION` is our own level; it rides on INFO so stdlib filtering and
        # rotation behave normally, but keeps its own name in both outputs.
        py_level = logging.INFO if level == "ACTION" else getattr(
            logging, level, logging.INFO
        )

        exc_info = None
        if exc is not None:
            exc_info = (type(exc), exc, exc.__traceback__)

        prefix = f"[{tag}] " if tag else ""
        # Structured detail is the point of `detail=` — but it is also worth
        # having in the human-readable file, where most reading happens.
        suffix = ""
        # A multi-line record (the session banner, for one) reads worse with a
        # key=value tail stapled to its last line.
        if detail and "\n" not in text:
            try:
                suffix = "  (" + " ".join(
                    f"{k}={v}" for k, v in detail.items()
                    if not isinstance(v, (dict, list, tuple))
                ) + ")"
                if suffix == "  ()":
                    suffix = ""
            except Exception:
                suffix = ""
        try:
            _logger.log(
                py_level,
                f"{prefix}{text}{suffix}",
                exc_info=exc_info,
                extra={
                    "ll_tag": tag,
                    "ll_msg": text,
                    "ll_level": level,
                    "ll_detail": detail,
                },
            )
        except Exception:
            # Logging must never raise into the caller. If the handlers are
            # broken we still keep the in-memory record below.
            pass

        entry: Dict[str, Any] = {
            "ts": stamp.isoformat(timespec="milliseconds"),
            "elapsed_s": round(time.time() - STARTED_AT, 3),
            "level": level,
            "module": tag,          # key name kept for existing callers
            "tag": tag,
            "thread": threading.current_thread().name,
            "msg": text,
        }
        if detail:
            entry["detail"] = detail
        if exc is not None:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["traceback"] = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ).rstrip()

        with cls._lock:
            cls._counts[level] = cls._counts.get(level, 0) + 1
            cls._logs.append(entry)
            if len(cls._logs) > cls.MAX_LOGS:
                del cls._logs[: len(cls._logs) - cls.MAX_LOGS]

    # -------------------------------------------------------------- writing

    @classmethod
    def debug(cls, tag: str, msg: Any, exc: BaseException = None, **detail) -> None:
        cls._record("DEBUG", tag, msg, exc, detail or None)

    @classmethod
    def info(cls, tag: str, msg: Any, exc: BaseException = None, **detail) -> None:
        cls._record("INFO", tag, msg, exc, detail or None)

    @classmethod
    def warning(cls, tag: str, msg: Any, exc: BaseException = None, **detail) -> None:
        cls._record("WARNING", tag, msg, exc, detail or None)

    @classmethod
    def warn(cls, tag: str, msg: Any, exc: BaseException = None, **detail) -> None:
        """Alias for `warning`."""
        cls._record("WARNING", tag, msg, exc, detail or None)

    @classmethod
    def error(cls, tag: str, msg: Any, exc: BaseException = None, **detail) -> None:
        cls._record("ERROR", tag, msg, exc, detail or None)

    @classmethod
    def critical(cls, tag: str, msg: Any, exc: BaseException = None, **detail) -> None:
        cls._record("CRITICAL", tag, msg, exc, detail or None)

    @classmethod
    def exception(cls, tag: str, msg: Any, **detail) -> None:
        """Log the exception currently being handled, with its traceback."""
        exc = sys.exc_info()[1]
        cls._record("ERROR", tag, msg, exc, detail or None)

    @classmethod
    def action(cls, tag: str, msg: Any, **detail) -> None:
        """Record something that changed the user's account or their data.

        Draft picks and bans, ready-check accepts, loot crafts, account
        switches, config writes the user did not make by hand. These are the
        lines you want when the question is "what did it actually do".
        """
        cls._record("ACTION", tag, msg, None, detail or None)

    # -------------------------------------------------------------- reading

    @classmethod
    def get_logs(
        cls,
        module: Optional[str] = None,
        limit: Optional[int] = None,
        level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recent in-memory records, oldest first."""
        with cls._lock:
            entries = list(cls._logs)
        if module is not None:
            entries = [e for e in entries if e.get("module") == module]
        if level is not None:
            wanted = str(level).upper()
            entries = [e for e in entries if e.get("level") == wanted]
        if limit is not None:
            if limit <= 0:
                return []
            entries = entries[-limit:]
        return entries

    @classmethod
    def counts(cls) -> Dict[str, int]:
        """How many records of each level this run has produced so far."""
        with cls._lock:
            return dict(cls._counts)

    @classmethod
    def problem_count(cls) -> int:
        """WARNING + ERROR + CRITICAL. The number worth showing a badge for."""
        counts = cls.counts()
        return sum(counts.get(name, 0) for name in ("WARNING", "ERROR", "CRITICAL"))

    @classmethod
    def log_dir(cls) -> str:
        return _LOG_DIR

    @classmethod
    def paths(cls) -> Dict[str, str]:
        return {
            "debug": DEBUG_LOG_PATH,
            "error": ERROR_LOG_PATH,
            "jsonl": JSONL_LOG_PATH,
        }

    @classmethod
    def handler_errors(cls) -> List[str]:
        """Log files that could not be opened. Empty is the normal case."""
        return list(_handler_errors)

    @classmethod
    def session_id(cls) -> str:
        return SESSION_ID

    @classmethod
    def reset_for_tests(cls) -> None:
        with cls._lock:
            cls._logs.clear()
            cls._counts = {level: 0 for level in LEVELS}


# ------------------------------------------------------------ housekeeping

def prune_old_logs(max_age_days: int = 30) -> int:
    """Delete rotated log files older than `max_age_days`. Returns the count.

    Only touches this directory's own rotated backups (``*.log.1`` and so
    on), never the live files.
    """
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    try:
        for name in os.listdir(_LOG_DIR):
            if ".log." not in name and not name.endswith(".jsonl.1"):
                continue
            path = os.path.join(_LOG_DIR, name)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                continue
    except Exception as exc:
        Logger.debug("Logger", f"Could not prune old logs: {exc}")
    return removed
