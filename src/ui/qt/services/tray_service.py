"""
LLSystemTray — System Tray Service for PySide6 Shell (UI/UX Master Plan §22).

Provides:
- QSystemTrayIcon with LeagueLoop icon
- Context menu for fast open, automation toggle, stealth mode, and exit
- Balloon message alerts for game events
"""
from __future__ import annotations

import os
from typing import Optional
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from utils.path_utils import get_asset_path


class LLSystemTray(QObject):
    """Manages the system tray icon, context menu, and desktop notifications."""

    show_window_requested = Signal()
    toggle_orb_requested = Signal()
    toggle_automation_requested = Signal()
    quit_requested = Signal()

    def __init__(
        self,
        config=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.config = config
        self.parent_widget = parent

        self.tray_icon = QSystemTrayIcon(parent)
        self._setup_icon()
        self._setup_menu()

        self.tray_icon.activated.connect(self._on_tray_activated)

    def _setup_icon(self) -> None:
        for candidate in ("assets/app.ico", "assets/icon.png"):
            path = get_asset_path(candidate)
            if path and os.path.exists(path):
                self.tray_icon.setIcon(QIcon(path))
                break

    def _setup_menu(self) -> None:
        menu = QMenu(self.parent_widget)
        menu.setStyleSheet("""
            QMenu {
                background-color: #091428;
                border: 1px solid #785A28;
                color: #F0E6D2;
                font-size: 12px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #1E282D;
                color: #0AC8B9;
            }
            QMenu::separator {
                height: 1px;
                background-color: #1E282D;
                margin: 4px 0;
            }
        """)

        act_show = QAction("Open LeagueLoop", menu)
        act_show.triggered.connect(self.show_window_requested.emit)
        menu.addAction(act_show)

        act_orb = QAction("Compact Orb Mode", menu)
        act_orb.triggered.connect(self.toggle_orb_requested.emit)
        menu.addAction(act_orb)

        menu.addSeparator()

        self.act_auto = QAction("Toggle Automation", menu)
        self.act_auto.triggered.connect(self.toggle_automation_requested.emit)
        menu.addAction(self.act_auto)

        menu.addSeparator()

        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(act_quit)

        self.tray_icon.setContextMenu(menu)

    def show(self) -> None:
        self.tray_icon.show()

    def hide(self) -> None:
        self.tray_icon.hide()

    def show_message(self, title: str, message: str, icon=QSystemTrayIcon.Information, timeout_ms: int = 3000) -> None:
        if self.config and self.config.get("stealth_mode", False):
            return
        if self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message, icon, timeout_ms)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_window_requested.emit()
