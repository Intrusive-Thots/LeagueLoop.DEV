"""
Automation — the control centre (UI/UX Master Plan §7).

The plan is blunt about this screen: "a control center, not a settings dump".
So it is organised by the moment each automation acts in a match, with a
master switch at the top, and every control states its name, its current
state, a one-sentence explanation, and where to configure it further.

Also carries the emergency stop (§17), which must be reachable without
hunting.
"""
from __future__ import annotations

from core.config_keys import (
    AUTO_ACCEPT,
    AUTO_BAN_ENABLED,
    AUTO_HOVER,
    AUTO_LOCK_IN,
    AUTO_RANDOM_SKIN,
    AUTO_REQUEUE,
    AUTOMATION_MASTER,
)
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.qt.components.button import ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSeparator
from ui.qt.components.setting_row import LLSettingRow
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import TEXT_MUTED, TEXT_SECONDARY
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import TEXT_BODY, TEXT_PAGE_TITLE

#: (config key, group, name, explanation, default, config-action label)
AUTOMATION_CONTROLS: List[Tuple[str, str, str, str, bool, str]] = [
    (AUTO_ACCEPT, "Ready Check", "Auto Accept",
     "Accepts the Ready Check as soon as a match is found.", False, ""),
    (AUTO_HOVER, "Champion Select", "Auto Hover",
     "Hovers your top available champion so your team can see it.", False, ""),
    (AUTO_LOCK_IN, "Champion Select", "Auto Lock In",
     "Locks in your champion once it is selected.", False, "Priorities"),
    (AUTO_BAN_ENABLED, "Champion Select", "Auto Ban",
     "Bans from your ban list, skipping champions teammates are hovering.",
     False, "Ban list"),
    # "Auto Set Roles" was removed. It advertised applying your preferred
    # role assignment, and there is no role-assignment code anywhere in the
    # engine — the switch wrote `auto_set_roles`, which nothing has ever read.
    # A control for a feature that does not exist is worse than a missing
    # feature: it makes the real ones look unreliable too.
    (AUTO_RANDOM_SKIN, "Champion Select", "Random Skin",
     "Picks a random owned skin after locking in.", True, ""),
    (AUTO_REQUEUE, "After the game", "Auto Requeue",
     "Starts a new queue after a dodge or a finished match.", False, ""),
    ("auto_honor_enabled", "After the game", "Auto Honor",
     "Honors a teammate, preferring friends then top performers.", False, ""),
    ("skip_stats_enabled", "After the game", "Skip Stats Screen",
     "Closes the post-game stats screen automatically.", True, ""),
    ("auto_join_enabled", "Lobby", "Auto Join",
     "Accepts lobby invites from trusted friends.", False, ""),
]


class QtAutomationTab(QWidget):
    """Master switch plus grouped automation controls."""

    stop_requested = Signal()
    configure_requested = Signal(str)   # config key

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.config = getattr(container, "config", None) if container else None
        self.automation = getattr(container, "automation", None) if container else None
        self.view_model = view_model

        self.rows: Dict[str, LLSettingRow] = {}
        self._setup_ui()
        self._load_state()

        if view_model is not None:
            view_model.state_changed.connect(self._render_state)
            self._render_state()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        title = QLabel("Automation", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        root.addWidget(title)

        # --- master switch + emergency stop (§7, §17) ---------------------
        master_card = LLCard(parent=self)
        master_row = QHBoxLayout()
        master_row.setSpacing(SPACE_MD)

        self.master_status = LLStatus(
            "Automation off", Tone.NEUTRAL, "Nothing will run automatically",
            parent=master_card,
        )
        master_row.addWidget(self.master_status)
        master_row.addStretch(1)

        self.btn_stop = LLButton(
            "Stop automation", variant=ButtonVariant.DANGER, parent=master_card
        )
        self.btn_stop.setToolTip("Emergency stop - halt all automated actions")
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        master_row.addWidget(self.btn_stop)

        self.master_toggle = LLSettingRow(
            "Master switch",
            "Turns every automation below on or off.",
            checked=False,
            parent=master_card,
        )
        self.master_toggle.toggled.connect(self._on_master_toggled)

        master_card.add_layout(master_row)
        master_card.add_widget(LLSeparator(parent=master_card))
        master_card.add_widget(self.master_toggle)
        root.addWidget(master_card)

        # --- grouped controls ---------------------------------------------
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(SPACE_MD)

        for group in dict.fromkeys(c[1] for c in AUTOMATION_CONTROLS):
            card = LLCard(title=group, parent=holder)
            first = True
            for key, grp, name, blurb, default, action in AUTOMATION_CONTROLS:
                if grp != group:
                    continue
                if not first:
                    card.add_widget(LLSeparator(parent=card))
                first = False

                row = LLSettingRow(name, blurb, checked=default,
                                   action_label=action, parent=card)
                row.toggled.connect(lambda v, k=key: self._on_row_toggled(k, v))
                if action:
                    row.action_clicked.connect(
                        lambda k=key: self.configure_requested.emit(k)
                    )
                card.add_widget(row)
                self.rows[key] = row

            holder_layout.addWidget(card)

        holder_layout.addStretch(1)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

    # --------------------------------------------------------------- state
    def _load_state(self) -> None:
        if not self.config:
            return
        for key, _grp, _name, _blurb, default, _action in AUTOMATION_CONTROLS:
            row = self.rows.get(key)
            if row is not None:
                row.set_checked(bool(self.config.get(key, default)))

        self.master_toggle.set_checked(bool(self.config.get(AUTOMATION_MASTER, True)))
        self._refresh_details()

    def _refresh_details(self) -> None:
        """Show why a control matters, e.g. how many priorities are set (§7)."""
        if not self.config:
            return
        count = len(self.config.get("priority_list", []) or [])
        row = self.rows.get(AUTO_LOCK_IN)
        if row is not None:
            row.set_detail(
                "{} priorit{} configured".format(count, "y" if count == 1 else "ies")
            )
            if count == 0:
                row.set_enabled_state(
                    False, "Add champions to your priority list first"
                )
            else:
                row.set_enabled_state(True)

    def _render_state(self, *_args) -> None:
        if self.view_model is None:
            return
        text, tone, detail = self.view_model.automation_status()
        self.master_status.set_status(text, tone, detail)
        self.btn_stop.setEnabled(self.view_model.state.automation.running)

    # -------------------------------------------------------------- actions
    def _on_master_toggled(self, checked: bool) -> None:
        if self.config:
            self.config.set(AUTOMATION_MASTER, checked)
        for row in self.rows.values():
            row.set_enabled_state(checked,
                                  "" if checked else "Master switch is off")
        if not checked:
            self.stop_requested.emit()
        self._refresh_details()

    def _on_row_toggled(self, key: str, value: bool) -> None:
        if self.config:
            self.config.set(key, value)
        if key == AUTO_LOCK_IN:
            self._refresh_details()
