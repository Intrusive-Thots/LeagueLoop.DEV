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

from PySide6.QtCore import Qt, QTimer, Signal
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
from ui.qt.components.status import Tone
from ui.qt.components.toast import QtToastManager
from ui.qt.widgets.app_header import LLAppHeader
from ui.qt.widgets.accounts_tab import QtAccountsTab
from ui.qt.widgets.automation_tab import QtAutomationTab
from ui.qt.widgets.champ_select_tab import QtChampSelectTab
from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab
from ui.qt.widgets.navigation.sidebar import QtNavigationSidebar
from ui.qt.widgets.play_tab import QtPlayTab
from ui.qt.widgets.champion_list_tab import (
    QtBanListTab,
    QtPriorityTab,
)
# The dedicated ARAM screen (bench sniper, auto-reroll, sort by win rate) was
# written but never imported, so the generic champion-list tab was standing in
# for it and none of those controls existed.
from ui.qt.widgets.loot_tab import QtLootTab
from ui.qt.widgets.profile_tab import QtProfileTab
from ui.qt.widgets.settings_tab import QtSettingsTab
from core.config_keys import ATTACH_TO_CLIENT, COMPANION_SIDE
from ui.qt.services.companion_anchor import CompanionAnchor
from ui.qt.services.companion_position import SIDE_LEFT, SIDE_RIGHT
from ui.qt.widgets.status_bar import LLStatusBar
from utils.logger import Logger

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

    toast_requested = Signal(str, str, object)  # message, title, Tone

    def __init__(self, container: Any = None):
        super().__init__()
        self.container = container
        self.config = getattr(container, "config", None) if container else None

        self.setWindowTitle("LeagueLoop")
        # Explicit rather than inherited from the QApplication: a frameless
        # window still contributes its own icon to the taskbar and to Alt-Tab,
        # and `check_scaling.py` builds this window without going through
        # `create_app`, so relying on inheritance meant the icon was missing
        # in exactly the runs that render it.
        from ui.qt.services.app_icon import apply_to as _apply_app_icon

        _apply_app_icon(self)
        # "Always on top" was a Settings toggle that wrote a config key nothing
        # read. The League Client raises itself when a lobby or a draft starts,
        # so without this the app disappears behind it at exactly the moment
        # you need it — and there was no way to get it back short of alt-tab.
        self._always_on_top = True
        if self.config is not None:
            try:
                self._always_on_top = bool(self.config.get("always_on_top", True))
            except Exception:
                self._always_on_top = True

        self.setWindowFlags(self._window_flags())
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.setStyleSheet(get_global_stylesheet())

        # Toast manager for non-blocking notifications
        self.toasts = QtToastManager(self)
        self.toast_requested.connect(
            lambda msg, title, tone: self.toasts.show(msg, title=title, tone=tone if isinstance(tone, Tone) else Tone.INFO)
        )
        self._subscribe_to_global_events()

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
        self.header.orb_requested.connect(self.toggle_orb_mode)
        root_layout.addWidget(self.header)

        # Floating Mini Orb Widget (§16 & §27)
        from ui.qt.widgets.orb_widget import QtOrbWidget
        self.orb = QtOrbWidget(container=self.container, view_model=self.view_model)
        self.orb.restore_requested.connect(self.toggle_orb_mode)

        # The main window is the companion panel, so it attaches to the League
        # Client exactly as the orb does. Previously only the orb did, which is
        # why the full window sat wherever it was last dragged while the orb
        # tracked the client correctly — two behaviours for one concept.
        self.anchor = CompanionAnchor(
            self,
            preferred_side=self._configured_side(),
            enabled=self._attach_enabled(),
        )
        self.view_model.state_changed.connect(self._follow_client)

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

        # Wire automation master toggle and emergency stop buttons (§17)
        self._wire_automation()
        self._wire_configure_actions()

        # Start focus on navigation rather than letting the first focusable
        # widget (a window control) claim the focus ring on launch.
        current = self.sidebar.buttons.get(self.sidebar.DEFAULT_TABS[0][0])
        if current is not None:
            current.setFocus()

        # System tray integration (§10, §72)
        from ui.qt.widgets.system_tray import QtSystemTray
        self.tray = QtSystemTray(self)
        if self.config and self.config.get("run_in_tray", True):
            self.tray.show()

        # Global hotkeys (§24)
        self._bind_hotkeys()

        # Auto-login default account on launch (§220)
        # `self` as the context object, not just the callable. Without it,
        # a window closed inside 2.5 seconds still gets this invocation, and
        # PySide6 calls a bound method whose C++ half has been deleted — a
        # segfault, not an exception. This is the same crash class as the two
        # access violations in crash.log, with a timer instead of a worker.
        QTimer.singleShot(2500, self, self._auto_load_default_account)

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
                except Exception as exc:
                    Logger.debug("MainWindow", "_wire_automation suppressed an error", exc=exc)

            # Any page may report a result. Without this a page's own
            # `toast_requested` is a signal into the void — which is how the
            # Play screen's Find Match button ended up silent on every failure.
            page_toast = getattr(page, "toast_requested", None)
            if page_toast is not None:
                try:
                    page_toast.connect(self.toast_requested)
                except Exception as exc:
                    Logger.debug(
                        "MainWindow", "Could not wire a page's toasts", exc=exc
                    )

        # Play reports automation state and hands off to the screen that
        # owns it; that hand-off has to actually go somewhere.
        play_page = self.tab_pages.get("play")
        jump = getattr(play_page, "automation_requested", None)
        if jump is not None:
            try:
                jump.connect(lambda: self.sidebar.select_tab("automation"))
            except Exception as exc:
                Logger.debug("MainWindow", "_wire_automation suppressed an error", exc=exc)

        # Settings changes that need the window, not just a config write.
        settings_page = self.tab_pages.get("settings")
        for signal_name, handler in (
            ("tray_preference_changed", self.set_run_in_tray),
            ("hotkeys_changed", self.rebind_hotkeys),
        ):
            signal = getattr(settings_page, signal_name, None)
            if signal is not None:
                try:
                    signal.connect(handler)
                except Exception as exc:
                    Logger.debug(
                        "MainWindow", f"Could not wire {signal_name}", exc=exc
                    )

        row = getattr(settings_page, "row_ontop", None)
        if row is not None:
            try:
                row.toggled.connect(self.set_always_on_top)
            except Exception as exc:
                Logger.debug("MainWindow", "_wire_automation suppressed an error", exc=exc)

        # Developer Mode has to reach the Diagnostics screen, not just config.
        dev_row = getattr(settings_page, "row_devmode", None)
        diagnostics_page = self.tab_pages.get("diagnostics")
        setter = getattr(diagnostics_page, "set_developer_mode", None)
        if dev_row is not None and callable(setter):
            try:
                dev_row.toggled.connect(setter)
            except Exception as exc:
                Logger.debug("MainWindow", "_wire_automation suppressed an error", exc=exc)

        automation_page = self.tab_pages.get("automation")
        if automation_page is not None:
            toggle = getattr(automation_page, "master_toggle", None)
            if toggle is not None and controller is not None:
                try:
                    toggle.toggled.connect(controller.set_master)
                except Exception as exc:
                    Logger.debug("MainWindow", "_wire_automation suppressed an error", exc=exc)

        settings_page = self.tab_pages.get("settings")
        if settings_page is not None:
            status_sig = getattr(settings_page, "status_saved", None)
            if status_sig is not None:
                try:
                    status_sig.connect(self._on_status_saved)
                except Exception as exc:
                    Logger.debug("MainWindow", "_wire_automation suppressed an error", exc=exc)

        if controller is not None:
            try:
                controller.publish()
            except Exception as exc:
                Logger.debug("MainWindow", "_wire_automation suppressed an error", exc=exc)

    def _on_status_saved(self, status_text: str) -> None:
        """Push custom status message to LCU via chat API."""
        lcu = getattr(self.container, "lcu", None) if self.container else None
        if lcu is None or not getattr(lcu, "is_connected", False):
            self.toast_requested.emit(
                "Saved. It will be applied the next time the League Client connects.",
                "Status Saved", Tone.NEUTRAL,
            )
            return
        try:
            # ApiHandler.request(method, endpoint, data) — there is no `json`
            # keyword. Passing one raised TypeError on every save.
            resp = lcu.request("PUT", "/lol-chat/v1/me", {"statusMessage": status_text})
        except Exception as exc:
            self.toast_requested.emit(
                f"Could not update status: {exc}", "Status Error", Tone.WARNING)
            return
        code = getattr(resp, "status_code", None)
        if resp is None or (code is not None and not 200 <= code < 300):
            self.toast_requested.emit(
                "The League Client refused the status change."
                + (f" (HTTP {code})" if code else ""),
                "Status Error", Tone.WARNING,
            )
        else:
            self.toast_requested.emit(
                "Status updated on League Client.", "Status Saved", Tone.SUCCESS)


    def _subscribe_to_global_events(self) -> None:
        """Subscribe to background bus events and surface as user-facing toasts."""
        try:
            from core.events import EventBus
            from services.accounts.results import EVENT_SWITCH_FINISHED, SwitchResult

            def _on_switch_finished(result):
                if not isinstance(result, SwitchResult):
                    return
                username = getattr(result, "account_label", None) or "Account"
                if result.ok:
                    self.toast_requested.emit(f"Signed in as {username}", "Account Switched", Tone.SUCCESS)
                else:
                    detail = result.detail or result.outcome.value
                    self.toast_requested.emit(f"Switch to {username} failed: {detail}", "Switch Failed", Tone.DANGER)

            def _on_toast_event(msg, title="LeagueLoop", tone=Tone.INFO):
                if isinstance(tone, str):
                    tone_map = {
                        "success": Tone.SUCCESS,
                        "warning": Tone.WARNING,
                        "danger": Tone.DANGER,
                        "error": Tone.DANGER,
                        "info": Tone.INFO,
                    }
                    tone = tone_map.get(tone.lower(), Tone.INFO)
                self.toast_requested.emit(str(msg), str(title), tone)

            EventBus.on(EVENT_SWITCH_FINISHED, _on_switch_finished)
            EventBus.on("toast_requested", _on_toast_event)
        except Exception as exc:
            Logger.debug("MainWindow", "_subscribe_to_global_events suppressed an error", exc=exc)

    def _wire_configure_actions(self) -> None:
        """
        Hook up the per-automation "configure" affordances.

        `configure_requested` carried a config key and was connected to
        nothing, so "Ban list" and "Priorities" on the Automation screen were
        decorative.
        """
        page = self.tab_pages.get("automation")
        signal = getattr(page, "configure_requested", None)
        if signal is not None:
            try:
                signal.connect(self._on_configure_requested)
            except Exception as exc:
                Logger.debug("MainWindow", "_wire_configure_actions suppressed an error", exc=exc)

    def _on_configure_requested(self, key: str) -> None:
        """Open the right editor for an automation, or jump to its screen.

        This is the only handler for `configure_requested`. There used to be
        two connected to it, so "Ban list" navigated to the Bans tab *and*
        opened a modal on top of it.
        """
        from core.config_keys import (
            ARAM_AUTO_REROLL, ARAM_BENCH_SWAP, ARAM_PRIORITY_LIST,
            AUTO_BAN_ENABLED, AUTO_LOCK_IN, DODGE_BLACKLIST_ENABLED,
        )

        if key == AUTO_BAN_ENABLED:
            # The Bans screen, not the drifted dialog. `QtBanListDialog` was
            # a second implementation with no paste, no portrait rows and no
            # import confirmation, so which editor you got depended on how
            # you had arrived at it.
            self.sidebar.select_tab("bans")
            return

        if key == AUTO_LOCK_IN:
            self.sidebar.select_tab("priority")
            return

        if key in (ARAM_BENCH_SWAP, ARAM_AUTO_REROLL):
            # ARAM is a mode on the Priority screen, and the two ARAM rules
            # now live there — this used to land on a screen with neither.
            self.sidebar.select_tab("priority")
            setter = getattr(self.tab_pages.get("priority"), "set_mode", None)
            if callable(setter):
                setter(ARAM_PRIORITY_LIST)
            return

        if key == DODGE_BLACKLIST_ENABLED:
            from ui.qt.widgets.blacklist_dialog import QtBlacklistDialog

            QtBlacklistDialog(config=self.config, parent=self).exec()
            return

        # Anything else: the screen that owns it is the honest fallback.
        self.sidebar.select_tab("automation")

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
                if key == "priority":
                    self.container.scraper.set_mode("Ranked")
            if self.container and getattr(self.container, "state_manager", None):
                try:
                    self.container.state_manager.update_ui(current_tab=key)
                except Exception as exc:
                    Logger.debug("MainWindow", "_on_tab_switched suppressed an error", exc=exc)
            if self.config is not None:
                try:
                    self.config.set("qt_last_tab", key)
                except Exception as exc:
                    Logger.debug("MainWindow", "_on_tab_switched suppressed an error", exc=exc)

    # ------------------------------------------------------- window layer
    def _window_flags(self):
        flags = Qt.FramelessWindowHint | Qt.Window
        if getattr(self, "_always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        return flags

    def set_always_on_top(self, enabled: bool) -> None:
        """
        Apply the Always-on-top setting immediately.

        Changing window flags on a visible window hides it in Qt, so the
        re-show is not optional — without it, toggling the setting makes the
        window vanish.
        """
        enabled = bool(enabled)
        if enabled == getattr(self, "_always_on_top", None):
            return
        self._always_on_top = enabled

        was_visible = self.isVisible()
        geometry = self.geometry()
        self.setWindowFlags(self._window_flags())
        self.setGeometry(geometry)
        if was_visible:
            self.show()

    def _surface(self, take_focus: bool = False) -> None:
        """
        Bring the window back in front of the client.

        Deliberately does not steal the keyboard by default: raising a window
        over the game while you are typing is worse than being behind it.
        Stealth mode suppresses this entirely.
        """
        if self.config is not None:
            try:
                if self.config.get("stealth_mode", False):
                    return
            except Exception as exc:
                Logger.debug("MainWindow", "_surface suppressed an error", exc=exc)

        if self.isMinimized():
            self.showNormal()
        elif not self.isVisible():
            self.show()
        self.raise_()
        if take_focus:
            self.activateWindow()

    def surface_now(self) -> None:
        """Come to the front because the user asked for the app again.

        Distinct from `_surface()`: that one is the app deciding to interrupt,
        so it respects stealth mode and does not steal the keyboard. This is a
        direct request — someone double-clicked the shortcut — and the honest
        answer to it is the window, in front, focused. Refusing here is what
        made a second launch look like nothing happened, which is how four
        copies ended up running.
        """
        if self.compact_mode:
            self.set_compact_mode(False)
            return
        if self.isMinimized():
            self.showNormal()
        elif not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    def _on_phase_changed(self, phase: str) -> None:
        """Jump to Champ Select when the draft starts; cleanly recover on dodge."""
        from core.state import GameflowPhase

        last_phase = getattr(self, "_last_seen_phase", None)
        self._last_seen_phase = phase

        if phase == GameflowPhase.CHAMP_SELECT.value:
            curr = getattr(self.sidebar, "current_tab", "")
            if curr and curr != "champ_select":
                self._tab_before_champ_select = curr
            if self.container and getattr(self.container, "scraper", None):
                queue_id = getattr(self.view_model.state.client, "queue_id", None)
                if queue_id:
                    self.container.scraper.set_mode_by_queue_id(queue_id)
            if "champ_select" in self.tab_pages:
                self.sidebar.select_tab("champ_select")
            # The draft is the one moment the app is time-critical (§80), and
            # the client has just raised itself over us.
            self._surface()
        elif phase == GameflowPhase.READY_CHECK.value:
            # A match was found and you have seconds to accept.
            self._surface()
        elif last_phase == GameflowPhase.CHAMP_SELECT.value and phase in (
            GameflowPhase.LOBBY.value,
            GameflowPhase.MATCHMAKING.value,
            GameflowPhase.READY_CHECK.value,
            GameflowPhase.NONE.value,
        ):
            # A dodge occurred during champ select
            self.toast_requested.emit(
                "Dodge detected — returned to queue/lobby.",
                "Dodge Recovered",
                Tone.INFO,
            )
            # If user was viewing champ select, switch back to previous tab or play tab
            if getattr(self.sidebar, "current_tab", "") == "champ_select":
                fallback = getattr(self, "_tab_before_champ_select", "play") or "play"
                if fallback == "champ_select":
                    fallback = "play"
                self.sidebar.select_tab(fallback)

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
            except Exception as exc:
                Logger.debug("MainWindow", "_restore_window_state suppressed an error", exc=exc)

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
        except Exception as exc:
            Logger.debug("MainWindow", "_save_window_state suppressed an error", exc=exc)

    def set_run_in_tray(self, enabled: bool) -> None:
        """Show or hide the tray icon straight away."""
        tray = getattr(self, "tray", None)
        if tray is None:
            return
        try:
            tray.show() if enabled else tray.hide()
        except Exception as exc:
            Logger.error("MainWindow", "Could not change the tray icon.", exc=exc)
            return
        Logger.info("MainWindow", f"Tray icon {'shown' if enabled else 'hidden'}.")

    def rebind_hotkeys(self) -> None:
        """Re-register the global shortcuts from config.

        Rebinding used to require a restart, and the previous shortcut stayed
        registered in the meantime.
        """
        try:
            import keyboard

            keyboard.remove_all_hotkeys()
        except Exception as exc:
            Logger.debug("Hotkeys", "Nothing to unbind", exc=exc)
        self._bind_hotkeys()

    def _bind_hotkeys(self) -> None:
        """Bind global keyboard shortcuts, and say so when they do not bind.

        Every failure here used to be swallowed, so an app with no working
        hotkeys was indistinguishable from one where the user had pressed the
        wrong keys.
        """
        try:
            import keyboard
        except Exception as exc:
            Logger.warning(
                "Hotkeys",
                "Global hotkeys are unavailable — the `keyboard` package is "
                "not installed, so none of the shortcuts will work.",
                exc=exc,
            )
            return

        if not self.config:
            Logger.warning("Hotkeys", "No config; hotkeys were not bound.")
            return

        bindings = (
            ("hotkey_launch_client", "ctrl+shift+l", self._hotkey_launch_client,
             "Launch Client"),
            ("hotkey_toggle_automation", "ctrl+shift+a",
             self._hotkey_toggle_automation, "Toggle Automation"),
            ("hotkey_compact_mode", "ctrl+shift+m", self.toggle_orb_mode,
             "Compact Mode"),
            ("hotkey_find_match", "ctrl+shift+f", self._hotkey_find_match,
             "Find Match"),
        )

        bound, failed = [], []
        for key, default, handler, label in bindings:
            sequence = self.config.get(key, default)
            if not sequence:
                continue
            try:
                keyboard.add_hotkey(sequence, handler, suppress=False)
                bound.append(f"{label}={sequence}")
            except Exception as exc:
                failed.append(label)
                Logger.error(
                    "Hotkeys",
                    f"'{sequence}' could not be bound to {label} — that "
                    f"shortcut will do nothing.",
                    exc=exc, action=label, sequence=sequence,
                )

        if bound:
            Logger.info("Hotkeys", "Bound: " + ", ".join(bound), bound=bound)
        if failed:
            Logger.warning(
                "Hotkeys",
                "These shortcuts are not active: " + ", ".join(failed),
                failed=failed,
            )

    # --------------------------------------------------- attach to client
    def _config_flag(self, key: str, default):
        if self.config is None:
            return default
        try:
            return self.config.get(key, default)
        except Exception as exc:
            Logger.debug("MainWindow", f"Could not read {key}", exc=exc)
            return default

    def _attach_enabled(self) -> bool:
        return bool(self._config_flag(ATTACH_TO_CLIENT, True))

    def _configured_side(self) -> str:
        side = str(self._config_flag(COMPANION_SIDE, SIDE_RIGHT)).lower()
        return side if side in (SIDE_LEFT, SIDE_RIGHT) else SIDE_RIGHT

    def set_attached_to_client(self, enabled: bool) -> None:
        """Turn following on or off at runtime.

        Turning it off leaves the window exactly where it is rather than
        snapping it somewhere — the user just said they want to place it
        themselves.
        """
        enabled = bool(enabled)
        self.anchor.enabled = enabled
        if self.config is not None:
            try:
                self.config.set(ATTACH_TO_CLIENT, enabled)
            except Exception as exc:
                Logger.debug("MainWindow", "Could not save attach setting", exc=exc)
        if enabled:
            self._follow_client()

    def _follow_client(self, *_args) -> None:
        """Move with the League Client's window.

        In orb mode the orb is the visible surface and owns its own anchor;
        moving a hidden main window would fight the user's next restore.
        """
        if self.compact_mode or not self.anchor.enabled:
            return
        window = getattr(self.view_model.state, "client_window", None)
        if window is None:
            return
        try:
            self.anchor.apply(window)
        except Exception as exc:
            Logger.error("MainWindow", "Could not reposition the window.", exc=exc)

    # -------------------------------------------------------- window mode
    @property
    def compact_mode(self) -> bool:
        """True when the orb is the visible surface."""
        return bool(getattr(self, "_compact_mode", False))

    def set_compact_mode(self, compact: bool) -> None:
        """Switch between the full window and the orb, in one direction only.

        This used to branch on `self.isVisible()`, which is not the question
        being asked: a *minimised* window is still visible in Qt, so pressing
        the compact hotkey while minimised swapped in the orb, and pressing it
        again brought back a window that had never really gone away — two
        surfaces on screen, or none.
        """
        compact = bool(compact)
        if compact == self.compact_mode:
            return
        self._compact_mode = compact

        if self.orb is None:
            return
        if compact:
            self.hide()
            self.orb.show()
            self.orb.reposition()
        else:
            self.orb.hide()
            self.showNormal()
            self._follow_client()
            self.raise_()
            self.activateWindow()

        state_manager = getattr(self.container, "state_manager", None) if self.container else None
        if state_manager is not None:
            try:
                state_manager.update_ui(compact_mode=compact)
            except Exception as exc:
                Logger.debug("MainWindow", "Could not publish compact mode", exc=exc)

    def toggle_orb_mode(self) -> None:
        """Toggle between full main window and floating mini orb mode (§16 & §27)."""
        self.set_compact_mode(not self.compact_mode)

    def _hotkey_launch_client(self) -> None:
        """Launch the Riot Client / League Client via shortcut."""
        try:
            from ui.qt.app.application import launch_riot_client

            launch_riot_client()
            self.toast_requested.emit("Launching Riot Client...", "Client Launch", Tone.INFO)
        except Exception as exc:
            self.toast_requested.emit(f"Could not launch client: {exc}", "Launch Failed", Tone.WARNING)

    def _hotkey_toggle_automation(self) -> None:
        """Toggle automation master power via shortcut."""
        ctrl = self._automation_controller()
        if ctrl is not None:
            new_state = not ctrl.master_enabled()
            ctrl.set_master(new_state)
            self.toast_requested.emit(
                f"Automation {'enabled' if new_state else 'disabled'}",
                "Automation",
                Tone.SUCCESS if new_state else Tone.NEUTRAL,
            )

    def _hotkey_find_match(self) -> None:
        """Start matchmaking search via shortcut."""
        lcu = getattr(self.container, "lcu", None) if self.container else None
        if lcu is None or not getattr(lcu, "is_connected", False):
            self.toast_requested.emit("Client not connected.", "Find Match", Tone.WARNING)
            return
        try:
            resp = lcu.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
            if resp and getattr(resp, "status_code", 0) in (200, 204):
                self.toast_requested.emit("Searching for match...", "Find Match", Tone.SUCCESS)
            else:
                code = getattr(resp, "status_code", "?")
                self.toast_requested.emit(f"Could not start search (HTTP {code})", "Find Match", Tone.WARNING)
        except Exception as exc:
            self.toast_requested.emit(f"Queue error: {exc}", "Find Match", Tone.WARNING)

    def _auto_load_default_account(self) -> None:
        """Auto-login to default stored account if client is not connected (§220)."""
        mgr = getattr(self.container, "account_manager", None) if self.container else None
        lcu = getattr(self.container, "lcu", None) if self.container else None
        if mgr is not None and lcu is not None and not getattr(lcu, "is_connected", False):
            default_idx = mgr.get_default_account_index()
            if default_idx >= 0:
                import threading
                self.toast_requested.emit("Auto-signing into default account...", "Auto-Login", Tone.INFO)
                threading.Thread(target=mgr.switch_to, args=(default_idx,), daemon=True).start()

    def closeEvent(self, event) -> None:
        self._save_window_state()
        # Not gated on `tray.isVisible()`. With the setting on but the icon
        # not yet shown, closing the window exited the app instead of
        # minimising — the opposite of what the setting says.
        tray = getattr(self, "tray", None)
        if self.config and self.config.get("run_in_tray", True) and tray is not None:
            if not tray.isVisible():
                self.set_run_in_tray(True)
            self.hide()
            self.tray.showMessage(
                "LeagueLoop",
                "LeagueLoop minimized to system tray.",
                self.tray.icon(),
                2000,
            )
            event.ignore()
            return

        try:
            self.view_model.dispose()
        except Exception as exc:
            Logger.debug("MainWindow", "closeEvent suppressed an error", exc=exc)
        super().closeEvent(event)
