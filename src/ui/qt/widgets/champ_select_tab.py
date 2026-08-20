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
            scraper=getattr(self.container, "scraper", None),
            tile_size=TileSize.SM,
            parent=self.available_section,
        )
        self.grid.champion_selected.connect(self.pick_requested.emit)
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
        action_row.addWidget(self.btn_override)

        self.btn_stop = LLButton(
            "Stop",
            variant=ButtonVariant.DANGER,
            parent=action_card,
        )
        self.btn_stop.setToolTip("Emergency stop - pauses all automation immediately")
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        action_row.addWidget(self.btn_stop)

        action_card.add_layout(action_row)
        action_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        root.addWidget(action_card)

    # ------------------------------------------------------------- render
    def _make_tile(self, rec, size: TileSize, priority=None) -> LLChampionTile:
        model = ChampionTileModel(
            champ_id=rec.champion_id,
            name=rec.name or "Unknown",
            key=rec.key or "",
            priority=priority,
            winrate=getattr(rec, "winrate", None),
        )
        tile = LLChampionTile(model, size=size, icon_provider=self.icons, parent=self)
        tile.clicked.connect(lambda cid, _n: self.pick_requested.emit(cid))
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

        self.role_badge.set_badge(vm.role_label, Tone.ACCENT)
        self.timer.set_remaining(vm.remaining_s, vm.timer_label())
        self.timeline.set_current(vm.timeline_index())

        rec = vm.recommendation
        self._clear_layout(self.rec_tile_holder)
        self._recommended_tile = None

        if rec.valid:
            self._recommended_tile = self._make_tile(rec, TileSize.LG, priority=1)
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
        for index, backup in enumerate(backups):
            tile = self._make_tile(backup, TileSize.SM, priority=index + 2)
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
        self.automation_status.set_status(label, tone, summary)
        self.btn_stop.setEnabled(auto.running)

    def _sync_grid_state(self) -> None:
        """Mirror bans and taken picks onto the roster tiles (§9)."""
        state = self.vm.state
        try:
            from services.draft import ActionValidator  # type: ignore
        except Exception:
            return

        session = self.vm._session_dict()
        try:
            banned_ids = ActionValidator.get_banned_champion_ids(session)
            picked_ids = ActionValidator.get_picked_champion_ids(session)
        except Exception:
            return

        def to_keys(ids):
            keys = []
            for cid in ids:
                tile = self.grid.tiles.get(int(cid))
                if tile is not None:
                    keys.append(tile.model.key)
            return keys

        self.grid.set_banned(to_keys(banned_ids))
        self.grid.set_disabled(to_keys(picked_ids - {state.selected_champion_id}))

    def _on_icon_ready(self, key: str, size: int) -> None:
        for tile in [self._recommended_tile] + self._backup_tiles:
            if tile is not None:
                tile.on_icon_ready(key, size)
