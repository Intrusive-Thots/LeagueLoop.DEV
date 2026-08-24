"""
Qt application bootstrap (UI/UX Master Plan §72, §74).

Owns QApplication construction and window creation so entry points stay
thin. Two modes:

    with services     — builds the real ApplicationContainer (LCU, assets,
                        config, automation) and binds the window to it.
    without services  — `container=None`, for UI development, screenshots
                        and visual-regression runs (§70) that must not touch
                        the League Client.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from utils.logger import Logger, prune_old_logs
from utils.session_log import (
    install_crash_handlers,
    install_qt_message_handler,
    session_banner,
    session_summary,
)

APP_NAME = "LeagueLoop"
ORG_NAME = "LeagueLoop"
TAG = "Startup"


def _configure_dpi() -> None:
    """
    Fractional-scaling support (§31: 100 / 125 / 150 / 175 / 200 %).

    Qt 6 enables high-DPI scaling by default; PassThrough keeps fractional
    factors intact instead of rounding them, which is what makes 125 % and
    175 % look correct rather than slightly oversized.
    """
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception as exc:
        Logger.debug("Application", "_configure_dpi suppressed an error", exc=exc)


def create_app(argv: Optional[list] = None) -> QApplication:
    """Create (or return the existing) QApplication."""
    existing = QApplication.instance()
    if existing is not None:
        return existing  # type: ignore[return-value]

    _configure_dpi()
    # Before the first window exists: Windows reads the AppUserModelID when a
    # window is created, and a process without one inherits python.exe's —
    # which is why the taskbar showed a generic icon no matter what icon the
    # window itself carried.
    from ui.qt.services.app_icon import apply_to, install_identity

    install_identity()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationDisplayName(APP_NAME)

    if not apply_to(app):
        Logger.warning(
            "Application",
            "The application icon could not be applied; windows will use the "
            "platform default.",
        )

    return app


def launch_riot_client() -> None:
    """
    Start the Riot Client (or the League Client) if it is installed.

    Switching accounts needs the Riot Client running, so the switcher asks for
    this when the client is absent. Shared with the legacy shell's launch
    hotkey rather than duplicated, so there is one place that knows how to
    find the executable.
    """
    import subprocess

    from utils.client_detector import (  # type: ignore
        get_league_executable_path,
        get_riot_executable_path,
    )

    exe = get_riot_executable_path() or get_league_executable_path()
    if not exe or not os.path.exists(exe):
        raise FileNotFoundError("No Riot or League executable found")
    subprocess.Popen([exe], shell=False)


def create_container() -> Any:
    """
    Build the real service graph. Returns None if construction fails.

    Delegates the startup sequence to `ApplicationContainer.bootstrap()`,
    which both shells share. The Qt shell used to build a container and a
    window and never run that sequence, so automation, the account manager
    and asset downloading simply did not exist here.
    """
    try:
        from core.container import ApplicationContainer  # type: ignore

        container = ApplicationContainer()
    except Exception as exc:
        Logger.error(
            TAG,
            "Could not build the service container — falling back to UI-only "
            "mode. Nothing that needs the League Client will work.",
            exc=exc,
        )
        return None

    # One startup sequence, shared with the legacy shell. Anything added to
    # `bootstrap()` reaches both shells; that is the whole point of it.
    # The state service is started later, in build(), once the window's
    # view-model is subscribed.
    container.bootstrap(launch_client_func=launch_riot_client)

    # `session_banner` logs the bootstrap errors in full, with tracebacks.
    # They used to go to a stderr that is invisible when the app is started
    # from a shortcut or a .bat that closes on exit.
    return container


def create_window(container: Any = None):
    """Create the main window bound to an optional service container."""
    from ui.qt.main_window import LeagueLoopMainWindow

    return LeagueLoopMainWindow(container=container)


def build(with_services: bool = True) -> Tuple[QApplication, Any, Any]:
    """
    Create app + container + window without entering the event loop.

    Returns (app, window, container) so callers — including screenshot and
    visual-regression tooling — can drive the window themselves.
    """
    install_crash_handlers()
    app = create_app()
    install_qt_message_handler()

    container = create_container() if with_services else None
    session_banner(shell="qt", container=container, argv=sys.argv[1:])

    try:
        window = create_window(container)
    except Exception as exc:
        Logger.critical(TAG, "The main window could not be built.", exc=exc)
        raise

    # Order matters. The state service publishes only what changed, so
    # starting it before the window's view-model has subscribed means the
    # first values go nowhere and the shell shows "Disconnected" with the
    # client open in champ select.
    tracker = getattr(container, "client_window_tracker", None) if container else None
    if tracker is not None:
        try:
            tracker.start()
            Logger.info(TAG, "League Client window tracker started.")
        except Exception as exc:
            Logger.error(
                TAG,
                "Could not start the window tracker — the companion panel will "
                "not follow the League Client.",
                exc=exc,
            )

    service = getattr(container, "client_state", None) if container else None
    if service is not None:
        try:
            service.start()
            Logger.info(TAG, "Client state service started.")
        except Exception as exc:
            Logger.error(
                TAG,
                "Could not start the client state service — the app will not "
                "notice the League Client connecting.",
                exc=exc,
            )

    # Come up in the state the user left it in, rather than making them flip
    # the master switch once per launch before anything runs.
    controller = getattr(container, "automation_controller", None) if container else None
    if controller is not None:
        try:
            controller.apply_config()
            Logger.info(
                TAG,
                "Automation restored from config (master={}).".format(
                    controller.master_enabled()
                ),
            )
        except Exception as exc:
            Logger.error(
                TAG,
                "Could not apply the saved automation settings — automation "
                "is off for this run.",
                exc=exc,
            )

    # Bring every bound view up to date from authoritative state.
    #
    # Views bind in the window's constructor, which happens before the
    # services above have published anything. The view-model only emits its
    # granular signals when a slice *changes*, so a view that renders solely
    # on those signals keeps whatever it was constructed with — the footer
    # read "Automation off" while the header two rows up read "Automation on".
    # `refresh()` was written for exactly this and was never called.
    try:
        window.view_model.refresh()
    except Exception as exc:
        Logger.error(
            TAG,
            "The initial state refresh failed — screens may show stale or "
            "empty values until something changes.",
            exc=exc,
        )

    Logger.info(TAG, "Startup complete; entering the event loop.")
    return app, window, container


#: How long to let in-flight background work finish before giving up on it.
#: Long enough for an LCU call to return, short enough that a hung request
#: does not stop the app closing.
SHUTDOWN_DRAIN_MS = 3000


def _drain_background_work() -> None:
    """Let the thread pool finish before Qt starts deleting widgets.

    `crash.log` recorded two `Windows fatal exception: access violation`
    inside `app.exec()`, both with a pool thread parked in
    `profile_service.load()`. That is the shape: the event loop returns, Qt
    begins destroying the window, and a worker still holding references to
    widgets delivers its result into memory that has just been freed. A
    RuntimeError would be the polite version of this; an access violation is
    what happens when the timing is worse.

    Draining first makes the ordering explicit rather than hoping the pool
    happens to be idle.
    """
    try:
        from PySide6.QtCore import QThreadPool

        pool = QThreadPool.globalInstance()
        if pool is None:
            return
        active = pool.activeThreadCount()
        if active:
            Logger.info(
                TAG, f"Waiting for {active} background task(s) before closing."
            )
        if not pool.waitForDone(SHUTDOWN_DRAIN_MS):
            Logger.warning(
                TAG,
                "Background work did not finish within "
                f"{SHUTDOWN_DRAIN_MS}ms; closing anyway.",
            )
    except Exception as exc:
        Logger.debug(TAG, "Could not drain the thread pool", exc=exc)


def run(with_services: bool = True, single_instance: bool = True) -> int:
    """Build everything, show the window, and run the Qt event loop.

    `single_instance` is on by default. Four copies sharing one cache, one
    config and one account store is not a configuration anybody chose — it is
    what happens when the window is behind the League Client and the shortcut
    gets double-clicked again.
    """
    app = create_app()

    guard = None
    if single_instance:
        from ui.qt.services.single_instance import SingleInstance

        guard = SingleInstance()
        if not guard.acquire():
            guard.raise_existing()
            Logger.info(
                TAG,
                "LeagueLoop is already running; brought that window forward "
                "instead of starting a second copy.",
            )
            return 0

    app, window, container = build(with_services=with_services)
    if guard is not None:
        guard.activated.connect(window.surface_now)
    window.show()
    code = 1
    try:
        code = app.exec()
        return code
    finally:
        Logger.info(TAG, f"Event loop returned {code}; shutting down.")
        if guard is not None:
            guard.release()
        _drain_background_work()
        if container is not None and hasattr(container, "shutdown"):
            try:
                container.shutdown()
                Logger.info(TAG, "Services shut down cleanly.")
            except Exception as exc:
                Logger.error(TAG, "Shutdown did not complete cleanly.", exc=exc)
        prune_old_logs()
        session_summary(reason=f"normal exit (code {code})")
