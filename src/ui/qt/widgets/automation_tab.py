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
    AUTO_HONOR_ENABLED,
    AUTO_HOVER,
    AUTO_JOIN_ENABLED,
    AUTO_LOCK_IN,
    AUTO_RANDOM_SKIN,
    AUTO_REQUEUE,
    AUTOMATION_MASTER,
    CHAT_WARDEN_ENABLED,
    DODGE_BLACKLIST_ENABLED,
    SKIP_STATS_ENABLED,
)
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.qt.components.button import ButtonVariant, LLButton
from utils.logger import Logger
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
    (AUTO_HONOR_ENABLED, "After the game", "Auto Honor",
     "Honors a teammate, preferring friends then top performers.", True, ""),
    (SKIP_STATS_ENABLED, "After the game", "Skip Stats Screen",
     "Closes the post-game stats screen automatically.", True, ""),
    (AUTO_JOIN_ENABLED, "Lobby", "Auto Join",
     "Accepts lobby invites from trusted friends.", False, ""),
    # Three behaviours the engine has always had and no screen ever admitted
    # to. Two of them read your data or close your client, so they are off by
    # default and now say plainly what they do.
    (CHAT_WARDEN_ENABLED, "Lobby", "Chat Warden",
     "Reads lobby chat and warns you if a teammate is being abusive.",
     False, ""),
    (DODGE_BLACKLIST_ENABLED, "Champion Select", "Dodge Blacklist",
     "Force-closes the League Client if someone on your blacklist is on "
     "your team. This costs you the queue timer.", False, "Blacklist"),
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
        #: True while `_load_state` is putting switches where config says.
        #: Guards the handlers so loading cannot write back.
        self._loading = False
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
            "Stop", variant=ButtonVariant.DANGER, parent=master_card
        )
        # Starts disabled. It was constructed enabled and only ever gated in
        # `_render_state`, which returns early without a view model — so the
        # emergency stop was permanently live and reached a controller that
        # might not exist.
        self.btn_stop.setEnabled(False)
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
        """Put every switch where config says it is, without side effects.

        `set_checked` re-emits `toggled`, which reached `_on_row_toggled` and
        wrote the value straight back — so merely *opening* this screen
        persisted every default as though the user had chosen it. The signals
        are blocked for the duration.
        """
        if not self.config:
            return
        self._loading = True
        try:
            for key, _grp, _name, _blurb, default, _action in AUTOMATION_CONTROLS:
                row = self.rows.get(key)
                if row is not None:
                    row.set_checked(bool(self.config.get(key, default)))

            master = bool(self.config.get(AUTOMATION_MASTER, True))
            self.master_toggle.set_checked(master)
        finally:
            self._loading = False

        # Called directly rather than left to the toggle's change signal.
        # `set_checked(False)` on a switch already at False emits nothing, so
        # with the master off at startup every row below stayed enabled and
        # interactive, contradicting the master state.
        self._apply_master(master)
        self._refresh_details()

    def _apply_master(self, checked: bool) -> None:
        for row in self.rows.values():
            row.set_enabled_state(
                checked, "" if checked else "Master switch is off"
            )

    def _refresh_details(self) -> None:
        """Show why a control matters, e.g. how many priorities are set (§7)."""
        if not self.config:
            return
        # Every list the engine might actually consult, not just the global
        # one. A user with only role-specific priorities was told "0
        # priorities configured" and had Auto Lock In greyed out, when it
        # would have worked perfectly.
        from core.config_keys import (
            ARAM_PRIORITY_LIST, PRIORITY_LIST, read_champion_ids,
            role_priority_key,
        )

        keys = [PRIORITY_LIST, ARAM_PRIORITY_LIST] + [
            role_priority_key(role)
            for role in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
        ]
        count = 0
        for key in keys:
            try:
                count += len(read_champion_ids(self.config, key))
            except Exception as exc:
                Logger.debug("AutomationTab", f"Could not read {key}", exc=exc)

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
        # The switches are re-read here too. The hotkey, the tray menu and
        # the local HTTP API all change automation behind this screen's back,
        # and it used to update only the status line — so the master switch
        # could sit showing the opposite of reality.
        self._load_state()
        if self.view_model is None:
            self.btn_stop.setEnabled(False)
            return
        text, tone, detail = self.view_model.automation_status()
        self.master_status.set_status(text, tone, detail)
        self.btn_stop.setEnabled(self.view_model.state.automation.running)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        """Re-read on every visit.

        Priorities are edited on another screen, and this one used to keep
        whatever counts it had at construction until the app restarted.
        """
        super().showEvent(event)
        self._load_state()
        self._render_state()

    # -------------------------------------------------------------- actions
    def _on_master_toggled(self, checked: bool) -> None:
        if getattr(self, "_loading", False):
            return

        # Turning it *on* used to write config and nothing else. The engine is
        # only started by `AutomationController.apply_config()` at launch, so
        # it stayed stopped until the next restart while this row read "on".
        controller = getattr(self.container, "automation_controller", None) \
            if self.container else None
        applied = False
        if controller is not None:
            try:
                controller.set_master(checked)
                applied = True
            except Exception as exc:
                Logger.error(
                    "AutomationTab", "Could not change the master switch.", exc=exc
                )
        if not applied and self.config:
            self.config.set(AUTOMATION_MASTER, checked)

        self._apply_master(checked)
        if not checked:
            self.stop_requested.emit()
        self._refresh_details()

    def _on_row_toggled(self, key: str, value: bool) -> None:
        if getattr(self, "_loading", False):
            return
        if self.config:
            self.config.set(key, value)
        Logger.info("AutomationTab", f"{key} set to {value}", key=key, value=value)
        if key == AUTO_LOCK_IN:
            self._refresh_details()

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        hint = super().minimumSizeHint()
        return QSize(500, hint.height())
