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
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

APP_NAME = "LeagueLoop"
ORG_NAME = "LeagueLoop"


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
    except Exception:
        pass


def create_app(argv: Optional[list] = None) -> QApplication:
    """Create (or return the existing) QApplication."""
    existing = QApplication.instance()
    if existing is not None:
        return existing  # type: ignore[return-value]

    _configure_dpi()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationDisplayName(APP_NAME)

    try:
        from utils.path_utils import get_asset_path  # type: ignore

        for candidate in ("assets/app.ico", "assets/icon.png"):
            path = get_asset_path(candidate)
            if path and os.path.exists(path):
                app.setWindowIcon(QIcon(path))
                break
    except Exception:
        pass

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
        print(f"[LeagueLoop] Could not build ApplicationContainer: {exc}", file=sys.stderr)
        print("[LeagueLoop] Falling back to UI-only mode.", file=sys.stderr)
        return None

    # One startup sequence, shared with the legacy shell. Anything added to
    # `bootstrap()` reaches both shells; that is the whole point of it.
    # The state service is started later, in build(), once the window's
    # view-model is subscribed.
    container.bootstrap(launch_client_func=launch_riot_client)

    for name, exc in getattr(container, "bootstrap_errors", []):
        print(f"[LeagueLoop] {name} unavailable: {exc}", file=sys.stderr)

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
    app = create_app()
    container = create_container() if with_services else None
    window = create_window(container)

    # Order matters. The state service publishes only what changed, so
    # starting it before the window's view-model has subscribed means the
    # first values go nowhere and the shell shows "Disconnected" with the
    # client open in champ select.
    service = getattr(container, "client_state", None) if container else None
    if service is not None:
        try:
            service.start()
        except Exception as exc:
            print(f"[LeagueLoop] Could not start client state: {exc}", file=sys.stderr)

    # Come up in the state the user left it in, rather than making them flip
    # the master switch once per launch before anything runs.
    controller = getattr(container, "automation_controller", None) if container else None
    if controller is not None:
        try:
            controller.apply_config()
        except Exception as exc:
            print(f"[LeagueLoop] Could not apply automation config: {exc}", file=sys.stderr)

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
        print(f"[LeagueLoop] Initial state refresh failed: {exc}", file=sys.stderr)

    return app, window, container


def run(with_services: bool = True) -> int:
    """Build everything, show the window, and run the Qt event loop."""
    app, window, container = build(with_services=with_services)
    window.show()
    try:
        return app.exec()
    finally:
        if container is not None and hasattr(container, "shutdown"):
            try:
                container.shutdown()
            except Exception:
                pass
