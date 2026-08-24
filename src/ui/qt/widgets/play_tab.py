"""
Play — the application's home screen (UI/UX Master Plan §6).

Shows, at a glance: what the client is doing, what LeagueLoop will do, and
one obvious primary action (§2.2). Live phase is rendered from
`ApplicationState` via the ShellViewModel rather than being pushed in by
whoever happens to know (§2.1).

Still to come (see the migration audit): account card, queue selector,
recent-activity feed (§6, §18), and the automation control centre (§7) that
will replace the flat checkbox grid below.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.activity import ActivityKind, LLActivityFeed
from ui.qt.components.card import LLCard, LLSection
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import TEXT_SECONDARY
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD
from ui.qt.theme.typography import TEXT_PAGE_TITLE
from ui.qt.viewmodels.activity_viewmodel import ActivityViewModel
from utils.logger import Logger


class QtPlayTab(QWidget):
    """Primary lobby and matchmaking control surface."""

    #: Asks the shell to open the Automation screen.
    automation_requested = Signal()
    #: (message, title, tone) — surfaced by the window as a toast.
    toast_requested = Signal(str, str, object)

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.config = getattr(container, "config", None) if container else None
        self.lcu = getattr(container, "lcu", None) if container else None
        self.automation = getattr(container, "automation", None) if container else None
        self.view_model = view_model

        self.activity_vm = None
        self._setup_ui()
        self._load_config_state()

        if view_model is not None:
            view_model.state_changed.connect(self._render_state)
            self._render_state()

    # ----------------------------------------------------------------- UI
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG
        )
        layout.setSpacing(SPACE_LG)

        title = QLabel("Play", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        layout.addWidget(title)

        # --- Current state + primary action (§2.2: one primary action) ---
        status_card = LLCard(parent=self)
        status_row = QHBoxLayout()
        status_row.setSpacing(SPACE_MD)

        self.phase_status = LLStatus("Idle", Tone.NEUTRAL, "Nothing in progress", parent=status_card)
        status_row.addWidget(self.phase_status)
        # Backwards-compatible alias: earlier code and tests refer to the
        # phase readout as `phase_indicator`. LLStatus exposes .text() too.
        self.phase_indicator = self.phase_status
        status_row.addStretch(1)

        self.btn_find_match = LLButton(
            "Find Match",
            variant=ButtonVariant.PRIMARY,
            size=ButtonSize.LG,
            parent=status_card,
        )
        self.btn_find_match.clicked.connect(self._on_find_match)
        status_row.addWidget(self.btn_find_match)

        status_card.add_layout(status_row)
        layout.addWidget(status_card)

        # --- what automation will do (§6) ---------------------------------
        # These were four raw QCheckBoxes duplicating the Automation screen,
        # rendered as checkboxes while every other surface uses the painted
        # switch — and they showed their config values regardless of whether
        # the engine was running, so the card could read "off" while the
        # header read "Automation on". Play should say what will happen and
        # send you to the one place that changes it (§2.2: one primary action
        # per screen).
        self.automation_card = LLCard(title="Automation", parent=self)

        auto_row = QHBoxLayout()
        auto_row.setSpacing(SPACE_MD)
        self.automation_status = LLStatus(
            "Automation off", Tone.NEUTRAL, "", parent=self.automation_card
        )
        auto_row.addWidget(self.automation_status)
        auto_row.addStretch(1)

        self.btn_automation = LLButton(
            "Automation settings",
            variant=ButtonVariant.SECONDARY,
            size=ButtonSize.SM,
            parent=self.automation_card,
        )
        self.btn_automation.setToolTip("Open the automation control centre")
        self.btn_automation.clicked.connect(self.automation_requested.emit)
        auto_row.addWidget(self.btn_automation)

        self.automation_card.add_layout(auto_row)
        layout.addWidget(self.automation_card)

        # --- recent activity (§6, §18) ------------------------------------
        activity_section = LLSection("Recent activity", parent=self)
        self.activity = LLActivityFeed(parent=activity_section)
        activity_section.add_widget(self.activity, 1)
        layout.addWidget(activity_section, 1)

        # Events -> readable sentences, never raw protocol text.
        self.activity_vm = ActivityViewModel(parent=self)
        self.activity_vm.entry_added.connect(self.activity.add)

    # -------------------------------------------------------------- state
    def _render_state(self, *_args) -> None:
        """Render live phase from ApplicationState (§2.1)."""
        if self.view_model is None:
            return

        text, tone, detail = self.view_model.phase_status()
        self.phase_status.set_status(text, tone, detail)
        self._render_automation()

        # The primary action only makes sense while the client is reachable
        # and not already in a match (§63: disabled is a designed state).
        connected = self.view_model.state.client.connected
        searching = self.view_model.state.queue.is_searching
        self.btn_find_match.setEnabled(connected and not searching)
        self.btn_find_match.setText("Searching…" if searching else "Find Match")
        self.btn_find_match.setToolTip(
            "" if connected else "Connect to the League Client to start a match"
        )

    def _load_config_state(self) -> None:
        """Nothing to load: this screen reports, it does not configure."""
        self._render_automation()

    def _render_automation(self) -> None:
        """
        Say what automation will actually do, from live state.

        Reads `AutomationState` — the engine's real running/paused flags — not
        the config keys, so this cannot disagree with the header.
        """
        from core.config_keys import (
            AUTO_ACCEPT, AUTO_BAN_ENABLED, AUTO_HOVER, AUTO_LOCK_IN,
            AUTO_RANDOM_SKIN, AUTO_REQUEUE,
        )

        auto = self.view_model.state.automation if self.view_model else None
        if auto is None or not auto.running:
            self.automation_status.set_status(
                "Automation off", Tone.NEUTRAL,
                "Nothing will run automatically.",
            )
            return
        if auto.paused:
            self.automation_status.set_status(
                "Automation paused", Tone.WARNING,
                "Automations are on but held until you resume.",
            )
            return

        enabled = []
        if self.config is not None:
            labels = [
                (AUTO_ACCEPT, "accept ready checks"),
                (AUTO_HOVER, "hover a champion"),
                (AUTO_LOCK_IN, "lock in"),
                (AUTO_BAN_ENABLED, "ban"),
                (AUTO_REQUEUE, "requeue on dodge"),
                (AUTO_RANDOM_SKIN, "pick a random skin"),
            ]
            for key, label in labels:
                try:
                    if self.config.get(key, False):
                        enabled.append(label)
                except Exception:
                    continue

        if not enabled:
            # Running with nothing switched on is a real state and a confusing
            # one — say so rather than implying something will happen.
            self.automation_status.set_status(
                "Automation on", Tone.WARNING,
                "No automations are switched on, so nothing will happen.",
            )
            return

        if len(enabled) > 3:
            detail = "Will {}, {} and {} more.".format(
                ", ".join(enabled[:2]), enabled[2], len(enabled) - 3
            )
        else:
            detail = "Will {}.".format(
                " and ".join([", ".join(enabled[:-1]), enabled[-1]]).strip(", ")
                if len(enabled) > 1 else enabled[0]
            )
        self.automation_status.set_status("Automation on", Tone.SUCCESS, detail)

    # ------------------------------------------------------------- actions
    def _on_find_match(self) -> None:
        """
        Start matchmaking.

        NOTE: this still calls the LCU directly because there is no
        start-matchmaking method on any service yet (QueueManager only
        resolves queue ids/names). A `QueueService.start_search()` seam
        should own this so the view stops knowing LCU endpoints.
        """
        if not (self.lcu and getattr(self.lcu, "is_connected", False)):
            self._report(
                "The League Client is not connected.", "Cannot search", Tone.WARNING
            )
            return

        Logger.info("PlayTab", "Find Match pressed.")
        try:
            resp = self.lcu.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
        except Exception as exc:
            Logger.error("PlayTab", "Starting matchmaking failed.", exc=exc)
            self._report(f"Could not start the search: {exc}", "Search failed",
                         Tone.DANGER)
            return

        code = getattr(resp, "status_code", None)
        if resp is None or (code is not None and not 200 <= code < 300):
            # A non-2xx here is the normal way the client says "no lobby",
            # "queue is locked" or "you are on a dodge timer". Swallowing it
            # made the screen's only primary action a visible no-op.
            detail = ""
            try:
                detail = (resp.text or "")[:160] if resp is not None else ""
            except Exception as exc:
                Logger.debug("PlayTab", "Response body unreadable", exc=exc)
            Logger.warning(
                "PlayTab",
                f"The client refused to start matchmaking (HTTP {code}). {detail}".strip(),
                status=code,
            )
            self._report(
                "The League Client would not start the search."
                + (f" (HTTP {code})" if code else "")
                + "\n\nMake sure a lobby is open and you are not on a dodge timer.",
                "Search not started", Tone.WARNING,
            )
            return

        Logger.action("PlayTab", "Started matchmaking")

    def _report(self, message: str, title: str, tone) -> None:
        """Say what happened. Silence is what made this button feel broken."""
        try:
            self.toast_requested.emit(message, title, tone)
        except Exception as exc:
            Logger.debug("PlayTab", "Could not emit the toast", exc=exc)

    def update_phase(self, phase: str) -> None:
        """Legacy push-style entry point, retained for callers that use it."""
        self.phase_status.set_status(phase, Tone.NEUTRAL)
