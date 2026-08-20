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
from typing import Any, Optional

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
from ui.qt.theme import get_global_stylesheet
from ui.qt.theme.colors import TEXT_MUTED, TEXT_SECONDARY
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import TEXT_BODY, TEXT_PAGE_TITLE
from ui.qt.viewmodels.shell_viewmodel import ShellViewModel
from ui.qt.widgets.app_header import LLAppHeader
from ui.qt.widgets.accounts_tab import QtAccountsTab
from ui.qt.widgets.automation_tab import QtAutomationTab
from ui.qt.widgets.champ_select_tab import QtChampSelectTab
from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab
from ui.qt.widgets.navigation.sidebar import QtNavigationSidebar
from ui.qt.widgets.play_tab import QtPlayTab
from ui.qt.widgets.champion_list_tab import (
    QtAramTab,
    QtBanListTab,
    QtPriorityTab,
)
from ui.qt.widgets.loot_tab import QtLootTab
from ui.qt.widgets.profile_tab import QtProfileTab
from ui.qt.widgets.settings_tab import QtSettingsTab
from ui.qt.widgets.status_bar import LLStatusBar

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

        # Presentation state for header/footer and future mode switching.
        self.view_model = ShellViewModel(container=container, parent=self)

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

        self.tab_pages = {}
        for key, name, _icon in self.sidebar.DEFAULT_TABS:
            self.tab_stack.addWidget(self._build_page(key, name))

        # --- Footer (fixed) ----------------------------------------------
        self.status_bar = LLStatusBar(version=_app_version(), parent=self)
        # Frameless windows have no native resize border; a grip in the footer
        # keeps resizing available without custom hit-testing (§27).
        grip = QSizeGrip(self.status_bar)
        self.status_bar.layout().addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)
        root_layout.addWidget(self.status_bar)

        # --- Bind state ---------------------------------------------------
        self.header.bind(self.view_model)
        self.status_bar.bind(self.view_model)

        self._restore_window_state()

        # Mode-based UX (§5): follow the client into the draft automatically,
        # since Champ Select is the most time-critical surface (§80).
        self.view_model.phase_changed.connect(self._on_phase_changed)

        # Both the Automation screen and the draft screen expose an emergency
        # stop (§17). Their `stop_requested` signals were connected to nothing,
        # so the button was decorative.
        self._wire_automation()

        # Start focus on navigation rather than letting the first focusable
        # widget (a window control) claim the focus ring on launch.
        current = self.sidebar.buttons.get(self.sidebar.DEFAULT_TABS[0][0])
        if current is not None:
            current.setFocus()

    # -------------------------------------------------------- automation
    def _automation_controller(self):
        return getattr(self.container, "automation_controller", None)

    def _wire_automation(self) -> None:
        controller = self._automation_controller()
        for page in self.tab_pages.values():
            signal = getattr(page, "stop_requested", None)
            if signal is not None:
                try:
                    signal.connect(self._on_stop_automation)
                except Exception:
                    pass

        automation_page = self.tab_pages.get("automation")
        toggle = getattr(automation_page, "master_toggle", None)
        if toggle is not None and controller is not None:
            try:
                toggle.toggled.connect(controller.set_master)
            except Exception:
                pass

        if controller is not None:
            try:
                controller.publish()
            except Exception:
                pass

    def _on_stop_automation(self) -> None:
        """Emergency stop. Must work from any screen that offers it (§17)."""
        controller = self._automation_controller()
        if controller is not None:
            controller.stop()

    # ------------------------------------------------------------- pages
    def _build_page(self, key: str, name: str) -> QWidget:
        """Construct the page for a nav key, falling back to an empty state."""
        builders = {
            "play": QtPlayTab,
            "champ_select": QtChampSelectTab,
            "automation": QtAutomationTab,
            "priority": QtPriorityTab,
            "aram": QtAramTab,
            "bans": QtBanListTab,
            "profile": QtProfileTab,
            "accounts": QtAccountsTab,
            "loot": QtLootTab,
            "diagnostics": QtDiagnosticsTab,
            "settings": QtSettingsTab,
        }
        builder = builders.get(key)

        page: QWidget
        if builder is not None:
            try:
                kwargs = {"container": self.container, "parent": self}
                # Pages opt into live state by declaring a `view_model` param.
                if "view_model" in inspect.signature(builder.__init__).parameters:
                    kwargs["view_model"] = self.view_model
                page = builder(**kwargs)
            except Exception as exc:  # a broken page must not take down the shell
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
        """
        Intentional empty state (§54) — never a blank panel, never fake data.
        """
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
            if self.container and getattr(self.container, "scraper", None):
                if key == "aram":
                    self.container.scraper.set_mode("ARAM")
                elif key == "priority":
                    self.container.scraper.set_mode("Ranked")
            if self.config is not None:
                try:
                    self.config.set("qt_last_tab", key)
                except Exception:
                    pass

    def _on_phase_changed(self, phase: str) -> None:
        """Jump to Champ Select when the draft starts; never jump away."""
        from core.state import GameflowPhase

        if phase == GameflowPhase.CHAMP_SELECT.value:
            if self.container and getattr(self.container, "scraper", None):
                queue_id = getattr(self.view_model.state.client, "queue_id", None)
                if queue_id:
                    self.container.scraper.set_mode_by_queue_id(queue_id)
            if "champ_select" in self.tab_pages:
                self.sidebar.select_tab("champ_select")

    # --------------------------------------------------- state persistence
    def _restore_window_state(self) -> None:
        """Restore size, position and last page (§52)."""
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
        self._save_window_state()
        try:
            self.view_model.dispose()
        except Exception:
            pass
        super().closeEvent(event)
