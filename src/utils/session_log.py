"""
Per-run session record
======================

A log is only useful if you can tell where one run of the program ended and
the next began, what version it was, what it was running against, and how it
finished. This module writes that.

On start, `session_banner()` writes a block like::

    ================ LeagueLoop session started ================
      session      3f9c1a20
      version      2-08-132-1935
      started      2026-08-21T19:47:01.204-07:00
      shell        customtkinter
      python       3.11.9 (CPython) 64-bit
      platform     Windows-11-10.0.26100-SP0
      executable   C:\\Users\\...\\python.exe
      tk           8.6 / CustomTkinter 5.2.2
      log level    DEBUG
      log dir      C:\\Users\\...\\AppData\\Local\\LeagueLoop\\logs
      services     lcu, assets, config, automation, client_state
      config       automation_master=True auto_accept=True ... (23 keys)
    ============================================================

On exit, `session_summary()` writes the counterpart: how long it ran, how
many warnings and errors it produced, and why it stopped.

It also installs the handlers that stop a crash from disappearing:

* `sys.excepthook` — an unhandled exception on the main thread
* `threading.excepthook` — the same on any worker thread (Python 3.8+),
  which is where most of this app's work happens
* Qt's own message handler — Qt warnings otherwise go to stderr and vanish
  when the app is launched from a shortcut
* `faulthandler` — a hard crash (segfault in a native Qt call) writes a
  native traceback to the log directory rather than killing the process
  silently
* `atexit` — the summary is written however the process ends

Nothing here is allowed to raise. A logging failure must never be the reason
the application does not start.
"""
from __future__ import annotations

import atexit
import os
import platform
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from utils.logger import STARTED_AT, Logger

TAG = "Session"

#: Config keys whose values must never reach a log file.
REDACTED_KEYS = (
    "password", "passwd", "secret", "token", "auth", "credential",
    "cookie", "session_id", "api_key", "apikey", "riot_id", "puuid",
    "summoner_name", "username", "email",
)

_installed = False
_summary_written = False
_faulthandler_file = None


# --------------------------------------------------------------- redaction

def _is_sensitive(key: str) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in REDACTED_KEYS)


def config_snapshot(config: Any, max_keys: int = 60) -> Dict[str, Any]:
    """A loggable view of the config: values for flags, never for secrets.

    Lists are summarised by length rather than dumped, so a 68-champion
    priority list does not fill the log, and anything whose key looks like a
    credential is replaced with `<redacted>`.
    """
    snapshot: Dict[str, Any] = {}
    try:
        raw = getattr(config, "config", None)
        if not isinstance(raw, dict):
            raw = getattr(config, "_config", None)
        if not isinstance(raw, dict):
            getter = getattr(config, "all", None) or getattr(config, "as_dict", None)
            raw = getter() if callable(getter) else None
        if not isinstance(raw, dict):
            return {}
        for key in sorted(raw)[:max_keys]:
            value = raw[key]
            if _is_sensitive(key):
                snapshot[key] = "<redacted>"
            elif isinstance(value, (list, tuple, set)):
                snapshot[key] = f"<{len(value)} items>"
            elif isinstance(value, dict):
                snapshot[key] = f"<{len(value)} keys>"
            elif isinstance(value, str) and len(value) > 60:
                snapshot[key] = value[:57] + "..."
            else:
                snapshot[key] = value
    except Exception as exc:
        Logger.debug(TAG, f"Could not snapshot config: {exc}")
    return snapshot


# ------------------------------------------------------------------ banner

def _environment() -> Dict[str, str]:
    info: Dict[str, str] = {}
    try:
        from core.version import __version__ as version
    except Exception:
        version = "unknown"

    info["session"] = Logger.session_id()
    info["version"] = version
    info["started"] = datetime.fromtimestamp(STARTED_AT).astimezone().isoformat(
        timespec="milliseconds"
    )
    info["python"] = "{} ({}) {}".format(
        platform.python_version(),
        platform.python_implementation(),
        "64-bit" if sys.maxsize > 2**32 else "32-bit",
    )
    try:
        info["platform"] = platform.platform()
    except Exception:
        info["platform"] = sys.platform
    info["executable"] = sys.executable or "?"
    info["cwd"] = os.getcwd()
    info["log level"] = os.environ.get("LOG_LEVEL", "DEBUG").upper()
    info["log dir"] = Logger.log_dir()

    # The toolkit the shell is actually built on. Worth recording: a
    # CustomTkinter upgrade changes widget scaling, and "it looked different
    # after Tuesday" is otherwise impossible to place.
    try:
        import tkinter

        import customtkinter

        info["tk"] = "{} / CustomTkinter {}".format(
            tkinter.TkVersion, getattr(customtkinter, "__version__", "?"),
        )
    except Exception:
        info["tk"] = "not loaded"

    return info


def _service_names(container: Any) -> List[str]:
    if container is None:
        return []
    names = []
    for attr in (
        "config", "lcu", "assets", "db", "scraper", "accounts",
        "automation", "automation_controller", "client_state", "loot",
        "profile", "draft_actions",
    ):
        if getattr(container, attr, None) is not None:
            names.append(attr)
    return names


def session_banner(
    shell: str = "customtkinter",
    container: Any = None,
    argv: Optional[Iterable[str]] = None,
) -> None:
    """Write the start-of-run block. Call this as early as possible."""
    try:
        info = _environment()
        info["shell"] = shell
        if argv is not None:
            info["arguments"] = " ".join(str(a) for a in argv) or "(none)"

        services = _service_names(container)
        if services:
            info["services"] = ", ".join(services)
        elif container is None:
            info["services"] = "(none — running without services)"

        width = max(len(k) for k in info) + 2
        lines = ["=" * 16 + " LeagueLoop session started " + "=" * 16]
        for key in (
            "session", "version", "started", "shell", "arguments", "python",
            "platform", "executable", "cwd", "tk", "log level",
            "log dir", "services",
        ):
            if key in info:
                lines.append(f"  {key.ljust(width)}{info[key]}")
        lines.append("=" * 59)
        Logger.info(TAG, "\n".join(lines), **{"environment": info})

        for problem in Logger.handler_errors():
            Logger.warning(TAG, f"Log file unavailable — {problem}")

        config = getattr(container, "config", None) if container else None
        if config is not None:
            snapshot = config_snapshot(config)
            if snapshot:
                Logger.info(
                    TAG,
                    "Configuration at startup ({} keys): {}".format(
                        len(snapshot),
                        " ".join(f"{k}={v}" for k, v in snapshot.items()),
                    ),
                    config=snapshot,
                )

        errors = list(getattr(container, "bootstrap_errors", []) or [])
        if errors:
            for name, exc in errors:
                Logger.error(
                    TAG,
                    f"Service '{name}' did not start — the features that need "
                    f"it will not work: {exc}",
                    service=name,
                )
        elif container is not None:
            Logger.info(TAG, "All services started.")
    except Exception as exc:  # never block startup
        try:
            Logger.error(TAG, "Could not write the session banner", exc=exc)
        except Exception:
            pass


def session_summary(reason: str = "exit") -> None:
    """Write the end-of-run block. Safe to call more than once."""
    global _summary_written
    if _summary_written:
        return
    _summary_written = True
    try:
        duration = time.time() - STARTED_AT
        counts = Logger.counts()
        hours, remainder = divmod(int(duration), 3600)
        minutes, seconds = divmod(remainder, 60)
        pretty = (
            f"{hours}h {minutes}m {seconds}s" if hours
            else f"{minutes}m {seconds}s" if minutes
            else f"{seconds}s"
        )
        tally = " ".join(
            f"{name.lower()}={counts.get(name, 0)}"
            for name in ("ACTION", "WARNING", "ERROR", "CRITICAL")
        )
        lines = [
            "=" * 17 + " LeagueLoop session ended " + "=" * 17,
            f"  session    {Logger.session_id()}",
            f"  reason     {reason}",
            f"  ran for    {pretty}",
            f"  records    {tally} (total {sum(counts.values())})",
            f"  logs       {Logger.log_dir()}",
        ]
        problems = Logger.problem_count()
        if problems:
            lines.append(
                f"  ** {problems} warning(s)/error(s) this run — see error.log **"
            )
        lines.append("=" * 59)
        Logger.info(TAG, "\n".join(lines), reason=reason,
                    duration_s=round(duration, 1), counts=counts)
    except Exception:
        pass


# ---------------------------------------------------------- crash handlers

def _handle_uncaught(exc_type, exc_value, exc_tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        Logger.info(TAG, "Interrupted by the user (Ctrl-C).")
    else:
        Logger.critical(
            "Crash",
            f"Unhandled {exc_type.__name__} on the main thread — the "
            f"application is stopping.",
            exc=exc_value,
        )
    session_summary(reason=f"unhandled {exc_type.__name__}")
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _handle_thread_exception(args) -> None:
    """Worker-thread crashes. Most of this app's work happens off the GUI
    thread, and without this hook those failures are printed to a stderr
    nobody sees and then forgotten."""
    name = getattr(args.thread, "name", "?")
    Logger.error(
        "Crash",
        f"Unhandled {args.exc_type.__name__} on thread '{name}'",
        exc=args.exc_value,
        thread=name,
    )


def install_crash_handlers(enable_faulthandler: bool = True) -> None:
    """Install every hook that turns a silent death into a log entry."""
    global _installed, _faulthandler_file
    if _installed:
        return
    _installed = True

    sys.excepthook = _handle_uncaught

    try:
        threading.excepthook = _handle_thread_exception
    except Exception as exc:
        Logger.debug(TAG, f"Thread exception hook unavailable: {exc}")

    if enable_faulthandler:
        try:
            import faulthandler

            path = os.path.join(Logger.log_dir(), "crash.log")
            _faulthandler_file = open(path, "a", encoding="utf-8")
            _faulthandler_file.write(
                f"\n--- session {Logger.session_id()} "
                f"{datetime.now().astimezone().isoformat(timespec='seconds')} ---\n"
            )
            _faulthandler_file.flush()
            faulthandler.enable(file=_faulthandler_file, all_threads=True)
        except Exception as exc:
            Logger.debug(TAG, f"faulthandler not enabled: {exc}")

    atexit.register(session_summary, "process exit")


# ------------------------------------------------------------ support data

def support_bundle(dest_dir: Optional[str] = None) -> str:
    """Zip the log directory plus a manifest, for handing to someone else.

    Returns the path to the archive. Secrets are already redacted at write
    time, so the logs themselves are safe to share; `accounts.json` and the
    config file are deliberately **not** included.
    """
    import zipfile

    dest_dir = dest_dir or Logger.log_dir()
    os.makedirs(dest_dir, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    archive = os.path.join(dest_dir, f"leagueloop-logs-{stamp}.zip")

    manifest = _environment()
    manifest["records"] = str(Logger.counts())
    manifest["problems"] = str(Logger.problem_count())

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "manifest.txt",
            "\n".join(f"{k}: {v}" for k, v in manifest.items()),
        )
        log_dir = Logger.log_dir()
        for name in sorted(os.listdir(log_dir)):
            if not (".log" in name or name.endswith(".jsonl")):
                continue
            path = os.path.join(log_dir, name)
            if os.path.isfile(path) and os.path.abspath(path) != os.path.abspath(archive):
                try:
                    zf.write(path, arcname=name)
                except Exception as exc:
                    Logger.debug(TAG, f"Could not add {name} to the bundle: {exc}")
    Logger.info(TAG, f"Support bundle written to {archive}")
    return archive
