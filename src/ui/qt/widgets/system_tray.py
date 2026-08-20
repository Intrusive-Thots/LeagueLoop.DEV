"""
QtSystemTray — PySide6 System Tray Integration (UI/UX Master Plan §10, §72).

Integrates LeagueLoop into the Windows system tray with a native tray menu,
double-click restore, automation toggle, and clean minimize-to-tray handling.
"""
from __future__ import annotations

import os
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from utils.path_utils import get_asset_path

if TYPE_CHECKING:
    from ui.qt.main_window import LeagueLoopMainWindow


class QtSystemTray(QSystemTrayIcon):
    """Native PySide6 system tray icon and context menu."""

    def __init__(self, main_window: Any = None, parent: Optional[QObject] = None):
        tray_parent = parent if isinstance(parent, QObject) else (main_window if isinstance(main_window, QObject) else None)
        super().__init__(tray_parent)
        self.main_window = main_window
        self._setup_tray()

    def _setup_tray(self) -> None:
        icon_path = get_asset_path("assets/app.ico") or get_asset_path("assets/icon.png")
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        self.setToolTip("LeagueLoop")

        menu = QMenu()
        act_show = menu.addAction("Show LeagueLoop")
        act_show.triggered.connect(self._show_window)

        menu.addSeparator()

        act_auto = menu.addAction("Toggle Automation")
        act_auto.triggered.connect(self._toggle_automation)

        menu.addSeparator()

        act_quit = menu.addAction("Quit")
        act_quit.triggered.connect(self._quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._show_window()

    def _show_window(self) -> None:
        self.main_window.showNormal()
        self.main_window.activateWindow()

    def _toggle_automation(self) -> None:
        ctrl = getattr(self.main_window.container, "automation_controller", None) if self.main_window.container else None
        if ctrl is not None:
            ctrl.set_master(not ctrl.is_master_enabled)

    def _quit(self) -> None:
        app = QApplication.instance()
        if app:
            app.quit()
