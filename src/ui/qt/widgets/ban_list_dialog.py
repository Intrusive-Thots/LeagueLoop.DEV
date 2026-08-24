"""
Ban List Dialog — Custom Champion Ban Configuration Modal (UI/UX Master Plan §8 & §15).

Provides:
- Searchable champion roster to select preferred bans
- Drag-and-drop ordered ban priority list
- Teammate hover respect rule configuration
- Direct integration with ConfigManager
"""
from __future__ import annotations

from core.config_keys import AUTO_BAN_RESPECT_HOVERS, BAN_LIST
from ui.qt.services.popup_size import size_to_content
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSection, LLSeparator
from ui.qt.theme.colors import (
    BORDER_ACCENT,
    BORDER_DEFAULT,
    GOLD_LIGHT,
    SURFACE_PANEL,
    SURFACE_PANEL_HOVER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.radii import RADIUS_MD
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import TEXT_BODY, TEXT_CAPTION, TEXT_PAGE_TITLE
from ui.qt.widgets.champion_grid import QtChampionGrid
from utils.logger import Logger


class QtBanListDialog(QDialog):
    """Modal dialog for editing custom champion ban priorities."""

    def __init__(
        self,
        config=None,
        assets=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.config = config
        self.assets = assets

        self.setWindowTitle("Ban List Preferences")
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #010A13;
                border: 1px solid {BORDER_DEFAULT};
            }}
        """)

        self._setup_ui()
        # Was a flat resize(780, 520): an empty ban list opened as a large
        # window of nothing, and a full one still had to scroll.
        size_to_content(self, min_size=(520, 380), max_size=(880, 640))
        self._load_config_state()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        title = QLabel("Champion Ban List Preferences", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        root.addWidget(title)

        # Options Row
        options_card = LLCard(parent=self)
        self.chk_respect = QCheckBox("Respect teammate hovers (never ban what a teammate intends to play)", options_card)
        self.chk_respect.setChecked(True)
        # Without this the checkbox only reached config if the user also
        # happened to edit the list; pressing Done discarded the change.
        self.chk_respect.toggled.connect(lambda _v: self._save())
        options_card.add_widget(self.chk_respect)
        root.addWidget(options_card)

        # Two-column selector
        columns = QHBoxLayout()
        columns.setSpacing(SPACE_LG)
        root.addLayout(columns, 1)

        # Left: Champion Roster
        left = LLSection("Champion roster", parent=self)
        self.grid = QtChampionGrid(asset_manager=self.assets, config=self.config, parent=left)
        self.grid.champion_selected.connect(self._on_champion_clicked)
        left.add_widget(self.grid, 1)
        columns.addWidget(left, 3)

        # Right: Ban Priority List
        right = LLSection("Ban priority order", parent=self)

        self.ban_list_widget = QListWidget(right)
        self.ban_list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.ban_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ban_list_widget.model().rowsMoved.connect(self._on_rows_moved)
        self.ban_list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {SURFACE_PANEL};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD}px;
                color: {TEXT_PRIMARY};
                font-size: 13px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 7px 6px;
                border-radius: 4px;
            }}
            QListWidget::item:hover {{ background-color: {SURFACE_PANEL_HOVER}; }}
            QListWidget::item:selected {{
                background-color: {SURFACE_PANEL_HOVER};
                color: {GOLD_LIGHT};
                border: 1px solid {BORDER_ACCENT};
            }}
        """)

        self.empty_state = QLabel(
            "No champions in your ban list.\n\nSelect a champion from the left to add it to your auto-ban queue.",
            right,
        )
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.setWordWrap(True)
        self.empty_state.setStyleSheet(f"""
            QLabel {{
                background-color: {SURFACE_PANEL};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD}px;
                color: {TEXT_MUTED};
                padding: {SPACE_LG}px;
            }}
        """)

        self.list_stack = QStackedWidget(right)
        self.list_stack.addWidget(self.empty_state)
        self.list_stack.addWidget(self.ban_list_widget)
        right.add_widget(self.list_stack, 1)

        self.hint = QLabel("Click to add ban. Drag to reorder priority.", right)
        self.hint.setStyleSheet(TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;")
        right.add_widget(self.hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACE_SM)

        self.btn_remove = LLButton("Remove", parent=right)
        self.btn_remove.clicked.connect(self._on_remove_selected)
        btn_row.addWidget(self.btn_remove)

        self.btn_clear = LLButton("Clear all", variant=ButtonVariant.DANGER, parent=right)
        self.btn_clear.clicked.connect(self._on_clear_all)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch(1)
        right.add_layout(btn_row)

        columns.addWidget(right, 2)

        # Footer Dialog Action
        footer = QHBoxLayout()
        footer.addStretch(1)
        btn_close = LLButton("Done", variant=ButtonVariant.PRIMARY, parent=self)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        root.addLayout(footer)

    def _champ_name(self, cid: int) -> str:
        getter = getattr(self.assets, "get_champ_name", None)
        if callable(getter):
            try:
                name = getter(cid)
                if name and str(name) != str(cid):
                    return str(name)
            except Exception as exc:
                Logger.debug("BanListDialog", "_champ_name suppressed an error", exc=exc)
        tile = self.grid.tiles.get(int(cid)) if self.grid.tiles else None
        return tile.model.name if tile is not None else str(cid)

    def _load_config_state(self) -> None:
        if not self.config:
            self._sync_badges()
            return

        self.chk_respect.setChecked(bool(self.config.get(AUTO_BAN_RESPECT_HOVERS, True)))

        self.ban_list_widget.clear()
        for cid in self.config.get(BAN_LIST, []) or []:
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            self._append_item(cid_int)
        self._renumber_items()
        self._sync_badges()

    def _append_item(self, champ_id: int) -> None:
        item = QListWidgetItem(self._champ_name(champ_id))
        item.setData(Qt.UserRole, champ_id)
        self.ban_list_widget.addItem(item)

    def _current_ids(self) -> List[int]:
        return [
            self.ban_list_widget.item(i).data(Qt.UserRole)
            for i in range(self.ban_list_widget.count())
        ]

    def _renumber_items(self) -> None:
        for i in range(self.ban_list_widget.count()):
            item = self.ban_list_widget.item(i)
            item.setText("#{}  {}".format(i + 1, self._champ_name(item.data(Qt.UserRole))))

    def _sync_badges(self) -> None:
        ids = self._current_ids()
        self.grid.set_priority_ids(ids)
        self.list_stack.setCurrentIndex(1 if ids else 0)
        self.btn_remove.setEnabled(bool(ids))
        self.btn_clear.setEnabled(bool(ids))
        self.hint.setVisible(bool(ids))

    def _save(self) -> None:
        if self.config:
            self.config.set(BAN_LIST, self._current_ids())
            # The engine reads AUTO_BAN_RESPECT_HOVERS. This wrote
            # "auto_ban_respect_teammates", a key nothing has ever read, so the
            # checkbox never affected whether a teammate's hover was skipped.
            self.config.set(AUTO_BAN_RESPECT_HOVERS, self.chk_respect.isChecked())
        self._sync_badges()

    def _on_champion_clicked(self, champ_id: int, name: str) -> None:
        if champ_id in self._current_ids():
            return
        self._append_item(champ_id)
        self._renumber_items()
        self._save()

    def _on_rows_moved(self, *_args) -> None:
        self._renumber_items()
        self._save()

    def _on_remove_selected(self) -> None:
        row = self.ban_list_widget.currentRow()
        if row >= 0:
            self.ban_list_widget.takeItem(row)
            self._renumber_items()
            self._save()

    def _on_clear_all(self) -> None:
        self.ban_list_widget.clear()
        self._save()
