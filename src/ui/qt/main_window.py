"""
LeagueLoop PySide6 main window.

Implements the global application layout from UI/UX Master Plan §3:

    ┌──────────────────────────────────────────┐
    │ LeagueLoop                 ● Connected   │   persistent header (§2.4)
    ├──────────────┬───────────────────────────┤
    │ Navigation   │          CONTENT          │   one primary expandable region
    ├──────────────┴───────────────────────────┤
    │ Ready • League Client connected          │   fixed status footer
    └──────────────────────────────────────────┘

Fixed-height header and footer, a single expandable content region, and all
state rendered from `ApplicationState` through `ShellViewModel` rather than
polled from services (§2.1).
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.card import LLCard
from ui.qt.components.toast import LLToastManager
from ui.qt.theme import get_global_stylesheet
from ui.qt.theme.colors import TEXT_MUTED, TEXT_SECONDARY
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import TEXT_BODY, TEXT_PAGE_TITLE
from ui.qt.viewmodels.shell_viewmodel import ShellViewModel
from ui.qt.widgets.accounts_tab import QtAccountsTab
from ui.qt.widgets.app_header import LLAppHeader
from ui.qt.widgets.aram_tab import QtAramTab
from ui.qt.widgets.automation_tab import QtAutomationTab
from ui.qt.widgets.ban_list_dialog import QtBanListDialog
from ui.qt.widgets.champ_select_tab import QtChampSelectTab
from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab
from ui.qt.widgets.loot_tab import QtLootTab
from ui.qt.widgets.navigation.sidebar import QtNavigationSidebar
from ui.qt.widgets.orb_widget import QtOrbWidget
from ui.qt.widgets.play_tab import QtPlayTab
from ui.qt.widgets.priority_tab import QtPriorityTab
from ui.qt.widgets.settings_tab import QtSettingsTab
from ui.qt.widgets.status_bar import LLStatusBar
from ui.qt.services.tray_service import LLSystemTray

DEFAULT_WIDTH = 980
DEFAULT_HEIGHT = 660
MIN_WIDTH = 760
MIN_HEIGHT = 560


def _app_version() -> str:
    try:
        from core.version import __version__  # type: ignore

        return f"v{__version__}"
    except Exception:
        return ""


class LeagueLoopMainWindow(QMainWindow):
    """Primary PySide6 application window."""

    def __init__(self, container: Any = None):
        super().__init__()
        self.container = container
        self.config = getattr(container, "config", None) if container else None

        self.setWindowTitle("LeagueLoop")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.setStyleSheet(get_global_stylesheet())

        # Presentation state for header/footer and mode switching
        self.view_model = ShellViewModel(container=container, parent=self)
        self.toast_mgr = LLToastManager.instance(self)

        root_widget = QWidget(self)
        self.setCentralWidget(root_widget)

        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Header (fixed) ----------------------------------------------
        self.header = LLAppHeader(self)
        self.header.minimize_requested.connect(self.showMinimized)
        self.header.close_requested.connect(self.close)
        root_layout.addWidget(self.header)

        # --- Body: navigation + content ----------------------------------
        body = QWidget(root_widget)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root_layout.addWidget(body, 1)

        self.sidebar = QtNavigationSidebar(parent=self)
        self.sidebar.tab_selected.connect(self._on_tab_switched)
        body_layout.addWidget(self.sidebar)

        self.tab_stack = QStackedWidget(body)
        body_layout.addWidget(self.tab_stack, 1)

        self.tab_pages: Dict[str, QWidget] = {}
        for key, name, _icon in self.sidebar.DEFAULT_TABS:
            self.tab_stack.addWidget(self._build_page(key, name))

        # --- Footer (fixed) ----------------------------------------------
        self.status_bar = LLStatusBar(version=_app_version(), parent=self)
        grip = QSizeGrip(self.status_bar)
        self.status_bar.layout().addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)
        root_layout.addWidget(self.status_bar)

        # --- Floating Orb Mode --------------------------------------------
        self.orb_widget = QtOrbWidget(container=self.container, view_model=self.view_model)
        self.orb_widget.restore_requested.connect(self._on_restore_from_orb)

        # --- System Tray --------------------------------------------------
        self.tray = LLSystemTray(config=self.config, parent=self)
        self.tray.show_window_requested.connect(self._show_and_raise)
        self.tray.toggle_orb_requested.connect(self._toggle_orb_mode)
        self.tray.quit_requested.connect(self._force_quit)
        if self.config and self.config.get("run_in_tray", True):
            self.tray.show()

        # --- Bind state ---------------------------------------------------
        self.header.bind(self.view_model)
        self.status_bar.bind(self.view_model)

        self._restore_window_state()

        # Mode-based UX (§5): follow the client into the draft automatically
        self.view_model.phase_changed.connect(self._on_phase_changed)

        # Start focus on navigation
        current = self.sidebar.buttons.get(self.sidebar.DEFAULT_TABS[0][0])
        if current is not None:
            current.setFocus()

    # ------------------------------------------------------------- pages
    def _build_page(self, key: str, name: str) -> QWidget:
        """Construct the page for a nav key, falling back to an empty state."""
        builders = {
            "play": QtPlayTab,
            "champ_select": QtChampSelectTab,
            "automation": QtAutomationTab,
            "aram": QtAramTab,
            "priority": QtPriorityTab,
            "loot": QtLootTab,
            "accounts": QtAccountsTab,
            "diagnostics": QtDiagnosticsTab,
            "settings": QtSettingsTab,
        }
        builder = builders.get(key)

        page: QWidget
        if builder is not None:
            try:
                kwargs = {"container": self.container, "parent": self}
                if "view_model" in inspect.signature(builder.__init__).parameters:
                    kwargs["view_model"] = self.view_model
                page = builder(**kwargs)

                # Connect automation config triggers
                if key == "automation" and hasattr(page, "configure_requested"):
                    page.configure_requested.connect(self._on_configure_automation)
            except Exception as exc:
                page = self._create_empty_page(
                    name,
                    f"This screen could not be loaded.\n\n{type(exc).__name__}: {exc}",
                )
        else:
            page = self._create_empty_page(
                name,
                "This screen has not been migrated to the new interface yet.",
            )

        self.tab_pages[key] = page
        return page

    def _create_empty_page(self, name: str, message: str) -> QWidget:
        """Intentional empty state (§54) — never a blank panel, never fake data."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN
        )
        layout.setSpacing(SPACE_MD)

        title = QLabel(name, page)
        title.setStyleSheet(
            TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY) + " background: transparent;"
        )
        layout.addWidget(title)

        card = LLCard(parent=page)
        body = QLabel(message, card)
        body.setWordWrap(True)
        body.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        card.add_widget(body)
        layout.addWidget(card)

        layout.addStretch(1)
        return page

    def _on_tab_switched(self, key: str) -> None:
        page = self.tab_pages.get(key)
        if page is not None:
            self.tab_stack.setCurrentWidget(page)
            if self.config is not None:
                try:
                    self.config.set("qt_last_tab", key)
                except Exception:
                    pass

    def _on_phase_changed(self, phase: str) -> None:
        """Jump to Champ Select when the draft starts; never jump away."""
        from core.state import GameflowPhase

        if phase == GameflowPhase.CHAMP_SELECT.value and "champ_select" in self.tab_pages:
            self.sidebar.select_tab("champ_select")

    def _on_configure_automation(self, key: str) -> None:
        """Open specialized configuration dialogs from the automation tab."""
        if key == "auto_ban_enabled":
            assets = getattr(self.container, "assets", None) if self.container else None
            dlg = QtBanListDialog(config=self.config, assets=assets, parent=self)
            dlg.exec()
        elif key == "auto_lock_in":
            self.sidebar.select_tab("priority")

    # --------------------------------------------------- mode switching
    def _toggle_orb_mode(self) -> None:
        if self.isVisible():
            self.hide()
            self.orb_widget.show()
            self.orb_widget.raise_()
        else:
            self._on_restore_from_orb()

    def _on_restore_from_orb(self) -> None:
        self.orb_widget.hide()
        self._show_and_raise()

    def _show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _force_quit(self) -> None:
        if self.tray:
            self.tray.hide()
        self.close()

    # --------------------------------------------------- state persistence
    def _restore_window_state(self) -> None:
        width, height = DEFAULT_WIDTH, DEFAULT_HEIGHT
        pos_x = pos_y = None
        last_tab = None

        if self.config is not None:
            try:
                width = int(self.config.get("qt_window_width", DEFAULT_WIDTH))
                height = int(self.config.get("qt_window_height", DEFAULT_HEIGHT))
                pos_x = self.config.get("qt_window_x", None)
                pos_y = self.config.get("qt_window_y", None)
                last_tab = self.config.get("qt_last_tab", None)
            except Exception:
                width, height = DEFAULT_WIDTH, DEFAULT_HEIGHT

        self.resize(max(width, MIN_WIDTH), max(height, MIN_HEIGHT))

        if pos_x is not None and pos_y is not None:
            try:
                self.move(int(pos_x), int(pos_y))
            except Exception:
                pass

        if last_tab and last_tab in self.tab_pages:
            self.sidebar.select_tab(last_tab)

    def _save_window_state(self) -> None:
        if self.config is None:
            return
        try:
            self.config.set_batch(
                {
                    "qt_window_width": self.width(),
                    "qt_window_height": self.height(),
                    "qt_window_x": self.x(),
                    "qt_window_y": self.y(),
                }
            )
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        if self.config and self.config.get("run_in_tray", True) and self.tray.tray_icon.isVisible():
            self.hide()
            self.tray.show_message("LeagueLoop", "Running minimized in system tray.")
            event.ignore()
            return

        self._save_window_state()
        try:
            if self.orb_widget:
                self.orb_widget.close()
            if self.tray:
                self.tray.hide()
            self.view_model.dispose()
        except Exception:
            pass
        super().closeEvent(event)
