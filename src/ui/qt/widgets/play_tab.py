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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.card import LLCard
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import TEXT_SECONDARY
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD
from ui.qt.theme.typography import TEXT_PAGE_TITLE


class QtPlayTab(QWidget):
    """Primary lobby and matchmaking control surface."""

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

        # --- Automation toggles ------------------------------------------
        toggles_card = LLCard(title="Automation", parent=self)

        grid = QGridLayout()
        grid.setSpacing(SPACE_MD)

        self.chk_auto_accept = QCheckBox("Auto Accept Ready Check", toggles_card)
        self.chk_auto_accept.toggled.connect(lambda v: self._set_cfg("auto_accept", v))
        grid.addWidget(self.chk_auto_accept, 0, 0)

        self.chk_auto_lock = QCheckBox("Auto Lock-In Champion", toggles_card)
        self.chk_auto_lock.toggled.connect(lambda v: self._set_cfg("auto_lock_in", v))
        grid.addWidget(self.chk_auto_lock, 0, 1)

        self.chk_auto_requeue = QCheckBox("Auto Requeue on Dodge", toggles_card)
        self.chk_auto_requeue.toggled.connect(lambda v: self._set_cfg("auto_requeue", v))
        grid.addWidget(self.chk_auto_requeue, 1, 0)

        self.chk_auto_skin = QCheckBox("Auto Random Skin", toggles_card)
        self.chk_auto_skin.toggled.connect(lambda v: self._set_cfg("auto_random_skin", v))
        grid.addWidget(self.chk_auto_skin, 1, 1)

        toggles_card.add_layout(grid)
        layout.addWidget(toggles_card)

        layout.addStretch(1)

    # -------------------------------------------------------------- state
    def _render_state(self, *_args) -> None:
        """Render live phase from ApplicationState (§2.1)."""
        if self.view_model is None:
            return

        text, tone, detail = self.view_model.phase_status()
        self.phase_status.set_status(text, tone, detail)

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
        if not self.config:
            return
        self.chk_auto_accept.setChecked(bool(self.config.get("auto_accept", False)))
        self.chk_auto_lock.setChecked(bool(self.config.get("auto_lock_in", False)))
        self.chk_auto_requeue.setChecked(bool(self.config.get("auto_requeue", False)))
        self.chk_auto_skin.setChecked(bool(self.config.get("auto_random_skin", True)))

    def _set_cfg(self, key: str, val: bool) -> None:
        if self.config:
            self.config.set(key, val)

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
            return
        try:
            self.lcu.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
        except Exception:
            # Errors surface through state/activity rather than crashing the view.
            pass

    def update_phase(self, phase: str) -> None:
        """Legacy push-style entry point, retained for callers that use it."""
        self.phase_status.set_status(phase, Tone.NEUTRAL)

    @property
    def phase_indicator(self):
        """Compatibility accessor for test suites and callers expecting phase_indicator widget."""
        return self.phase_status

