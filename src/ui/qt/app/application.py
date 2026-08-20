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

    The container leaves the lazily-created services (automation, accounts)
    as None; each shell is expected to construct the ones it uses. The Qt
    shell was not creating the account manager, so the Accounts screen came
    up permanently empty with every control disabled.
    """
    try:
        from core.container import ApplicationContainer  # type: ignore

        container = ApplicationContainer()
    except Exception as exc:
        print(f"[LeagueLoop] Could not build ApplicationContainer: {exc}", file=sys.stderr)
        print("[LeagueLoop] Falling back to UI-only mode.", file=sys.stderr)
        return None

    # Champion names, ids and icons come from Riot's Data Dragon, and nothing
    # fetches them unless this is called. Without it `assets.champ_data` stays
    # empty forever: no champion tiles on Priority / ARAM / Bans / Champ
    # Select, and every champion renders as a bare numeric id.
    try:
        container.assets.start_loading()
    except Exception as exc:
        print(f"[LeagueLoop] Asset loading failed to start: {exc}", file=sys.stderr)

    # Accounts is a first-class screen, not an optional extra. A failure here
    # must not take down the whole shell, so the screen degrades to its empty
    # state instead (§54).
    try:
        container.create_account_manager(launch_client_func=launch_riot_client)
    except Exception as exc:
        print(
            f"[LeagueLoop] Account manager unavailable: {exc}", file=sys.stderr
        )

    # The automation engine. Without this `container.automation` is None and
    # every toggle on the Automation screen writes a config key that nothing
    # reads at runtime - the switches look live and do nothing.
    try:
        container.create_automation_controller()
    except Exception as exc:
        print(f"[LeagueLoop] Automation unavailable: {exc}", file=sys.stderr)

    # Nothing else populates ApplicationState, and every Qt view renders from
    # it. Without this the shell shows "Disconnected" with the client open.
    # Created here, started in build() once the window is listening.
    try:
        container.create_client_state_service()
    except Exception as exc:
        print(f"[LeagueLoop] Client state service unavailable: {exc}", file=sys.stderr)

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
