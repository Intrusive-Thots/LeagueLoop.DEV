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


def create_container() -> Any:
    """Build the real service graph. Returns None if construction fails."""
    try:
        from core.container import ApplicationContainer  # type: ignore

        return ApplicationContainer()
    except Exception as exc:
        print(f"[LeagueLoop] Could not build ApplicationContainer: {exc}", file=sys.stderr)
        print("[LeagueLoop] Falling back to UI-only mode.", file=sys.stderr)
        return None


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
