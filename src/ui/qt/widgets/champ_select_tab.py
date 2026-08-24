"""
Champ Select — the flagship surface (UI/UX Master Plan §11-§17, §80).

The plan says this screen must answer, immediately:

    What phase am I in?      -> draft timeline (§12)
    What role do I have?     -> role badge
    What is my pick?         -> recommendation card (§14)
    What will automation do? -> action preview (§15)
    How long do I have?      -> semantic timer (§13)

and must never leave the user trapped: manual override (§16) and a clearly
reachable emergency stop (§17) are always present.
"""
from __future__ import annotations

import time
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.badge import LLBadge
from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSection
from ui.qt.components.champion_tile import (
    ChampionTileModel,
    LLChampionTile,
    TileSize,
)
from ui.qt.components.draft_timeline import LLDraftTimeline
from ui.qt.components.status import LLStatus, Tone
from ui.qt.components.timer import LLTimer
from ui.qt.services.champion_icons import ChampionIconProvider
from ui.qt.widgets.champion_grid import QtChampionGrid
from ui.qt.theme.colors import TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import (
    TEXT_BODY,
    TEXT_CAPTION,
    TEXT_PAGE_TITLE,
    TEXT_SECTION_TITLE,
)
from ui.qt.viewmodels.champ_select_viewmodel import (
    ChampSelectViewModel,
    Confidence,
    TIMELINE_PHASES,
)
from utils.logger import Logger

_CONFIDENCE_TONE = {
    Confidence.HIGH: Tone.SUCCESS,
    Confidence.MEDIUM: Tone.WARNING,
    Confidence.LOW: Tone.NEUTRAL,
    Confidence.BLOCKED: Tone.DANGER,
}


class QtChampSelectTab(QWidget):
    """Draft screen driven by ChampSelectViewModel."""

    override_requested = Signal()
    stop_requested = Signal()
    pick_requested = Signal(int)

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.shell_view_model = view_model
        self.vm = ChampSelectViewModel(container=container, parent=self)

        self.icons = ChampionIconProvider(
            asset_manager=getattr(container, "assets", None), parent=self
        )
        self.icons.icon_ready.connect(self._on_icon_ready)

        self._backup_tiles: List[LLChampionTile] = []
        self._recommended_tile: Optional[LLChampionTile] = None

        # Picking used to be impossible from here: `pick_requested` was
        # emitted and connected to nothing.
        self._actions = None
        lcu = getattr(container, "lcu", None)
        if lcu is not None:
            try:
                from services.draft_actions import DraftActions  # type: ignore

                self._actions = DraftActions(lcu)
            except Exception:
                self._actions = None
        self._selected_id: int = 0

        self._setup_ui()

        self.vm.changed.connect(self._render)
        if view_model is not None:
            view_model.state_changed.connect(self.vm.apply)
            self.vm.apply(view_model.state)
        else:
            self._render()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        # --- header: title + role + timer ---------------------------------
        header = QHBoxLayout()
        header.setSpacing(SPACE_MD)

        title_box = QVBoxLayout()
        title_box.setSpacing(SPACE_SM // 2)
        self.title = QLabel("Champ Select", self)
        self.title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        title_box.addWidget(self.title)

        role_row = QHBoxLayout()
        role_row.setSpacing(SPACE_SM)
        role_caption = QLabel("ROLE", self)
        role_caption.setStyleSheet(
            TEXT_SECTION_TITLE.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        role_row.addWidget(role_caption)
        self.role_badge = LLBadge("Unassigned", Tone.ACCENT, parent=self)
        role_row.addWidget(self.role_badge)
        role_row.addStretch(1)
        title_box.addLayout(role_row)

        header.addLayout(title_box)
        header.addStretch(1)

        self.timer = LLTimer("Waiting", 0.0, parent=self)
        header.addWidget(self.timer)
        root.addLayout(header)

        # --- draft timeline (§12) -----------------------------------------
        self.timeline = LLDraftTimeline(TIMELINE_PHASES, parent=self)
        root.addWidget(self.timeline)

        # --- recommendation (§14) -----------------------------------------
        self.rec_card = LLCard(title="Recommended", parent=self)
        rec_row = QHBoxLayout()
        rec_row.setSpacing(SPACE_LG)

        self.rec_tile_holder = QVBoxLayout()
        self.rec_tile_holder.setAlignment(Qt.AlignTop)
        rec_row.addLayout(self.rec_tile_holder)

        rec_detail = QVBoxLayout()
        rec_detail.setSpacing(SPACE_SM)

        name_row = QHBoxLayout()
        name_row.setSpacing(SPACE_SM)
        self.rec_name = QLabel("No recommendation", self.rec_card)
        self.rec_name.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_PRIMARY))
        name_row.addWidget(self.rec_name)
        self.rec_confidence = LLBadge("Blocked", Tone.DANGER, parent=self.rec_card)
        name_row.addWidget(self.rec_confidence)
        name_row.addStretch(1)
        rec_detail.addLayout(name_row)

        self.rec_reasons = QLabel("", self.rec_card)
        self.rec_reasons.setWordWrap(True)
        self.rec_reasons.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        rec_detail.addWidget(self.rec_reasons)
        rec_detail.addStretch(1)

        rec_row.addLayout(rec_detail, 1)
        self.rec_card.add_layout(rec_row)
        # Must not be squeezed below its content: the LG tile would clip.
        self.rec_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        root.addWidget(self.rec_card)

        # --- backups (§14) -------------------------------------------------
        self.backup_section = LLSection("Backups", parent=self)
        self.backup_row = QHBoxLayout()
        self.backup_row.setSpacing(SPACE_SM)
        self.backup_row.setAlignment(Qt.AlignLeft)
        self.backup_section.add_layout(self.backup_row)

        self.backup_empty = QLabel("No backups available.", self.backup_section)
        self.backup_empty.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.backup_section.add_widget(self.backup_empty)
        self.backup_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        root.addWidget(self.backup_section)

        # --- available champions (§11) --------------------------------------
        self.available_section = LLSection("Available champions", parent=self)
        self.grid = QtChampionGrid(
            asset_manager=getattr(self.container, "assets", None),
            config=getattr(self.container, "config", None),
            tile_size=TileSize.SM,
            parent=self.available_section,
        )
        self.grid.champion_selected.connect(self.pick_requested.emit)
        self.grid.champion_selected.connect(
            lambda cid, _key: self._on_select(cid)
        )
        # Double-click selects. It used to go straight to `_on_lock_in`,
        # which commits the draft action — one accidental double-click ended
        # your pick, with no confirmation and no undo.
        self.grid.champion_activated.connect(
            lambda cid, _key: self._on_select(cid)
        )
        self.available_section.add_widget(self.grid, 1)
        # The roster absorbs whatever vertical space is left over.
        self.available_section.setMinimumHeight(180)
        self.available_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        root.addWidget(self.available_section, 1)

        # --- action bar: preview + override + stop (§15, §16, §17) ---------
        action_card = LLCard(parent=self)
        action_row = QHBoxLayout()
        action_row.setSpacing(SPACE_MD)

        self.automation_status = LLStatus(
            "Automation off", Tone.NEUTRAL, parent=action_card
        )
        action_row.addWidget(self.automation_status)
        action_row.addStretch(1)

        self.btn_override = LLButton(
            "Pick manually", variant=ButtonVariant.SECONDARY, parent=action_card
        )
        self.btn_override.setToolTip(
            "Stop automation choosing for you and pick yourself"
        )
        self.btn_override.clicked.connect(self.override_requested.emit)
        self.btn_override.clicked.connect(self._on_override)
        action_row.addWidget(self.btn_override)

        # Selecting a champion hovers it; committing is a separate, explicit
        # act. Hover and lock are the same LCU call with `completed` flipped,
        # but conflating them in the UI means one stray click ends your draft.
        self.btn_lock = LLButton(
            "Lock in", variant=ButtonVariant.PRIMARY, parent=action_card
        )
        self.btn_lock.setEnabled(False)
        self.btn_lock.clicked.connect(self._on_lock_in)
        action_row.addWidget(self.btn_lock)

        self.btn_stop = LLButton(
            "Stop automation",
            variant=ButtonVariant.DANGER,
            size=ButtonSize.MD,
            parent=action_card,
        )
        self.btn_stop.setToolTip("Emergency stop - halt all automated actions")
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        action_row.addWidget(self.btn_stop)

        action_card.add_layout(action_row)
        action_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        root.addWidget(action_card)

        # --- not-in-a-draft state (§54) -----------------------------------
        self.idle_notice = LLCard(title="Champion select", parent=self)
        idle_body = QLabel(
            "You are not in champion select.\n\n"
            "When a draft starts this screen fills in with your "
            "recommendation, your backups and the live roster.",
            self.idle_notice,
        )
        idle_body.setWordWrap(True)
        idle_body.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.idle_notice.add_widget(idle_body)
        self.idle_notice.setVisible(False)
        root.addWidget(self.idle_notice)
        root.addStretch(1)

        #: Everything that only makes sense inside a draft.
        self._draft_widgets = (
            self.timeline, self.rec_card, self.backup_section,
            self.available_section, action_card,
        )

    def _set_draft_visible(self, visible: bool) -> None:
        for widget in getattr(self, "_draft_widgets", ()):
            widget.setVisible(visible)
        self.idle_notice.setVisible(not visible)

    def _render_idle(self) -> None:
        """What the screen shows when there is no draft.

        The timer is the important part: with `remaining_s == 0` the timer
        component classifies as EXPIRED and reads "TIME UP 00:00" — which,
        with no draft running, is alarming and wrong.
        """
        self._set_draft_visible(False)
        self.role_badge.set_badge("Not in a draft", Tone.NEUTRAL)
        self.timer.set_remaining(0.0, "Waiting")
        self._selected_id = 0
        if not self._flashing():
            auto = self.vm._app_state.automation
            self.automation_status.set_status(
                "Automation on" if auto.running else "Automation off",
                Tone.SUCCESS if auto.running else Tone.NEUTRAL,
                "Nothing to do until a draft starts.",
            )
        self.btn_stop.setEnabled(bool(self.vm._app_state.automation.running))

    # ------------------------------------------------------------ actions
    #: How long a result message holds the status line against the next
    #: state push. `_render` runs on every publish — once a second during the
    #: draft — and used to overwrite "Hovering", "Locked in" and
    #: "Could not do that: <reason>" before they could be read, so a failed
    #: action looked exactly like a silent no-op.
    FLASH_SECONDS = 6.0

    def _flash(self, title: str, tone, detail: str = "") -> None:
        """Show a result, and hold it briefly against the render loop."""
        self._flash_until = time.monotonic() + self.FLASH_SECONDS
        self.automation_status.set_status(title, tone, detail)

    def _flashing(self) -> bool:
        return time.monotonic() < getattr(self, "_flash_until", 0.0)

    def _report(self, result, champion_id: int = 0) -> None:
        """Say what happened, in the status line the user is already reading."""
        if result.ok:
            return
        self._flash("Could not do that", Tone.WARNING, result.message)

    def _on_select(self, champion_id: int) -> None:
        """
        Selecting hovers the champion so your team can see it.

        A hover is reversible and is what the client itself does on a single
        click, so this is safe to fire on selection. Committing needs the
        Lock in button.
        """
        self._selected_id = int(champion_id or 0)
        self._sync_lock_button()

        if self._actions is None or not self._selected_id:
            return
        result = self._actions.hover(self._selected_id)
        if result.ok:
            self.automation_status.set_status(
                "Hovering", Tone.INFO, "Your team can see this pick."
            )
        else:
            self._report(result, self._selected_id)

    def _on_lock_in(self, *_args, champion_id: int = 0) -> None:
        champ = int(champion_id or self._selected_id or 0)
        if not champ:
            self.automation_status.set_status(
                "Nothing selected", Tone.NEUTRAL,
                "Choose a champion first, then lock in.",
            )
            return
        if self._actions is None:
            self._report(
                type("R", (), {"ok": False, "message":
                               "The League Client is not connected."})()
            )
            return

        banning = self._pending_type() == "ban"
        result = self._actions.lock_in(champ)
        if result.ok:
            self._flash(
                "Banned" if banning else "Locked in", Tone.SUCCESS,
                "{} is out of the draft.".format(self._champ_label(champ))
                if banning else "",
            )
        else:
            self._report(result, champ)
        self._sync_lock_button()

    def _champ_label(self, champ_id: int) -> str:
        tile = self.grid.tiles.get(int(champ_id)) if self.grid.tiles else None
        return tile.model.name if tile is not None else str(champ_id)

    def _on_override(self) -> None:
        """
        Manual pick: stop automation choosing for you, keep the draft going.

        Pausing rather than stopping - a full stop would also disable the
        post-draft automations you probably still want.
        """
        controller = getattr(self.container, "automation_controller", None)
        if controller is None:
            self._flash(
                "Automation is not running", Tone.NEUTRAL,
                "There is nothing to take over from.",
            )
            self._sync_lock_button()
            return

        paused = bool(getattr(self.vm._app_state.automation, "paused", False))
        try:
            # Nothing in the Qt shell ever called resume, so one press of this
            # button paused champ-select automation for the rest of the
            # session with no way back.
            controller.pause(not paused)
        except Exception as exc:
            Logger.error("ChampSelectTab", "Could not change the pause state.", exc=exc)
            self._flash(
                "Could not pause automation", Tone.DANGER, str(exc),
            )
            self._sync_lock_button()
            return

        if paused:
            self._flash(
                "Automation resumed", Tone.SUCCESS,
                "It will choose and lock for you again.",
            )
        else:
            self._flash(
                "Manual", Tone.NEUTRAL,
                "Automation is paused - select a champion and lock in yourself.",
            )
        self._sync_override_button()
        self._sync_lock_button()

    def _sync_override_button(self) -> None:
        paused = bool(getattr(self.vm._app_state.automation, "paused", False))
        self.btn_override.setText("Resume automation" if paused else "Pick manually")
        self.btn_override.setToolTip(
            "Let automation choose again" if paused
            else "Stop automation choosing for you, and pick yourself"
        )

    def _pending_type(self) -> str:
        """"pick", "ban" or "" — read from state, never over the network."""
        try:
            return self.vm.pending_action_type
        except Exception as exc:
            Logger.debug("ChampSelectTab", "pending type unavailable", exc=exc)
            return ""

    def _sync_lock_button(self) -> None:
        """Disabled is a designed state (§63): say why it is unavailable.

        The label follows the pending action. It was hardcoded "Lock in"
        while `DraftActions.lock_in` commits whatever action is in progress —
        so on your ban turn the button said "Lock in", banned the champion,
        and then reported "Locked in".
        """
        state = self.vm.state
        pending = self._pending_type()
        banning = pending == "ban"
        self.btn_lock.setText("Ban" if banning else "Lock in")

        if not state.active:
            self.btn_lock.setEnabled(False)
            self.btn_lock.setToolTip("You are not in champion select")
            return
        if state.locked_in and not banning:
            self.btn_lock.setEnabled(False)
            self.btn_lock.setToolTip("You have already locked in")
            return
        if not self._selected_id:
            self.btn_lock.setEnabled(False)
            self.btn_lock.setToolTip(
                "Select a champion to ban" if banning
                else "Select a champion first"
            )
            return

        can = bool(pending)
        self.btn_lock.setEnabled(can)
        if not can:
            self.btn_lock.setToolTip("It is not your turn yet")
        else:
            self.btn_lock.setToolTip(
                "Ban this champion - this cannot be undone" if banning
                else "Lock in your selection"
            )

    # ------------------------------------------------------------- render
    def _make_tile(self, rec, size: TileSize, priority=None) -> LLChampionTile:
        model = ChampionTileModel(
            champ_id=rec.champion_id,
            name=rec.name or "Unknown",
            key=rec.key or "",
            priority=priority,
        )
        tile = LLChampionTile(model, size=size, icon_provider=self.icons, parent=self)
        tile.clicked.connect(lambda cid, _n: self.pick_requested.emit(cid))
        tile.clicked.connect(lambda cid, _n: self._on_select(cid))
        return tile

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _render(self) -> None:
        vm = self.vm

        # Not in a draft is a real state and the screen had none: it kept the
        # full roster, enabled Pick/Stop buttons, "No recommendation" (which
        # looks exactly like a genuinely blocked draft) and a timer stuck on
        # "TIME UP 00:00".
        if not vm.state.active:
            self._render_idle()
            return
        self._set_draft_visible(True)

        self.role_badge.set_badge(vm.role_label, Tone.ACCENT)
        self.timer.set_remaining(vm.remaining_s, vm.timer_label())
        self.timeline.set_current(vm.timeline_index())

        # Whose turn it is changes as the draft moves, so the lock button has
        # to be re-evaluated on every state push, not only when you click.
        self._sync_lock_button()

        rec = vm.recommendation
        self._clear_layout(self.rec_tile_holder)
        self._recommended_tile = None

        if rec.valid:
            self._recommended_tile = self._make_tile(
                rec, TileSize.LG, priority=rec.rank + 1
            )
            self.rec_tile_holder.addWidget(self._recommended_tile)
            self.rec_name.setText(rec.name)
            self.rec_confidence.set_badge(
                rec.confidence.value, _CONFIDENCE_TONE[rec.confidence]
            )
            self.rec_reasons.setText(
                "\n".join("- {}".format(r) for r in rec.reasons if r)
            )
        else:
            self.rec_name.setText("No recommendation")
            self.rec_confidence.set_badge(
                Confidence.BLOCKED.value, Tone.DANGER
            )
            self.rec_reasons.setText(
                "\n".join("- {}".format(r) for r in rec.reasons)
                or "Add champions to your priority list to get a recommendation."
            )

        # backups
        self._clear_layout(self.backup_row)
        self._backup_tiles = []
        backups = vm.backups
        for backup in backups:
            # The badge is the champion's real position in the user's list,
            # not its index in this filtered row.
            tile = self._make_tile(backup, TileSize.SM, priority=backup.rank + 1)
            self._backup_tiles.append(tile)
            self.backup_row.addWidget(tile)
        self.backup_row.addStretch(1)
        self.backup_empty.setVisible(not backups)

        # reflect live draft state onto the roster
        self._sync_grid_state()

        # automation line
        summary = vm.automation_summary()
        auto = vm._app_state.automation
        if not auto.running:
            tone, label = Tone.NEUTRAL, "Automation off"
        elif auto.paused:
            tone, label = Tone.WARNING, "Automation paused"
        elif vm.locked_in:
            tone, label = Tone.SUCCESS, "Locked in"
        else:
            tone, label = Tone.SUCCESS, "Automation ready"
        if not self._flashing():
            self.automation_status.set_status(label, tone, summary)
        self.btn_stop.setEnabled(auto.running)
        self._sync_override_button()

    def _sync_grid_state(self) -> None:
        """Mirror bans and taken picks onto the roster tiles (§9)."""
        state = self.vm.state
        try:
            from services.draft import ActionValidator  # type: ignore
        except Exception as exc:
            # Leaving the previous draft's markings on the tiles is worse than
            # showing none: the roster silently lies about what is available.
            Logger.error("ChampSelectTab", "Draft validator unavailable.", exc=exc)
            self.grid.set_banned([])
            self.grid.set_disabled([])
            return

        session = self.vm._session_dict()
        try:
            banned_ids = ActionValidator.get_banned_champion_ids(session)
            picked_ids = ActionValidator.get_picked_champion_ids(session)
        except Exception as exc:
            Logger.error("ChampSelectTab", "Could not read the draft state.", exc=exc)
            self.grid.set_banned([])
            self.grid.set_disabled([])
            return

        def to_keys(ids):
            keys = []
            for cid in ids:
                tile = self.grid.tiles.get(int(cid))
                if tile is not None:
                    keys.append(tile.model.key)
            return keys

        # Owned/pickable. `set_owned` had no caller anywhere, so every tile
        # was built owned=True and the grid's OWNED filter did nothing.
        pickable = state.pickable_champion_ids or ()
        self.grid.set_owned(to_keys(pickable) if pickable else None)

        self.grid.set_banned(to_keys(banned_ids))
        self.grid.set_disabled(to_keys(picked_ids - {state.selected_champion_id}))

    def _on_icon_ready(self, key: str, size: int) -> None:
        for tile in [self._recommended_tile] + self._backup_tiles:
            if tile is not None:
                tile.on_icon_ready(key, size)
