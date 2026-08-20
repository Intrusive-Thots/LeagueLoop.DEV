"""
ARAM Tab — ARAM Champion Priority & Bench Sniper (UI/UX Master Plan §8 & §10).

Provides:
- Dedicated ARAM Champion Priority list with drag-and-drop reordering
- Visual champion roster with search & filter
- Bench Sniper & Auto-Reroll automation configuration
- Synchronized rank badges on champion roster tiles
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSection, LLSeparator
from ui.qt.components.setting_row import LLSettingRow
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
from ui.qt.theme.typography import TEXT_BODY, TEXT_PAGE_TITLE
from ui.qt.widgets.champion_grid import QtChampionGrid


class QtAramTab(QWidget):
    """ARAM Champion Priority and Bench Sniper configuration surface."""

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.config = getattr(container, "config", None) if container else None
        self.assets = getattr(container, "assets", None) if container else None
        self.scraper = getattr(container, "scraper", None) if container else None
        if self.scraper:
            self.scraper.set_mode("ARAM")

        self._setup_ui()
        self._load_config_state()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        title = QLabel("ARAM Priority & Bench Sniper", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        root.addWidget(title)

        # Automation Options Row
        options_card = LLCard(title="ARAM Automation Rules", parent=self)
        self.row_bench_swap = LLSettingRow(
            "Auto Bench Sniper",
            "Instantly grabs preferred champions when teammates roll them to the bench.",
            checked=True,
            parent=options_card,
        )
        self.row_bench_swap.toggled.connect(lambda v: self._set_cfg("aram_bench_swap", v))
        options_card.add_widget(self.row_bench_swap)
        options_card.add_widget(LLSeparator(parent=options_card))

        self.row_auto_reroll = LLSettingRow(
            "Always Reroll Below Top 3",
            "Spends a dice roll if your current champion is not in your top 3 choices.",
            checked=False,
            parent=options_card,
        )
        self.row_auto_reroll.toggled.connect(lambda v: self._set_cfg("aram_auto_reroll", v))
        options_card.add_widget(self.row_auto_reroll)

        root.addWidget(options_card)

        # Main two-column editor
        columns = QHBoxLayout()
        columns.setSpacing(SPACE_LG)
        root.addLayout(columns, 1)

        # Left: Champion Roster
        left = LLSection("Champion roster", parent=self)
        self.grid = QtChampionGrid(asset_manager=self.assets, scraper=self.scraper, parent=left)
        self.grid.champion_selected.connect(self._on_champion_clicked)
        left.add_widget(self.grid, 1)
        columns.addWidget(left, 3)

        # Right: Ordered Priority List
        right = LLSection("ARAM Priority Order", parent=self)

        self.prio_list_widget = QListWidget(right)
        self.prio_list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.prio_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.prio_list_widget.model().rowsMoved.connect(self._on_rows_moved)
        self.prio_list_widget.setStyleSheet(f"""
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
            "No champions in your ARAM priority list.\n\n"
            "Select champions from the roster on the left to add them to your priority queue.",
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
        self.list_stack.addWidget(self.prio_list_widget)
        right.add_widget(self.list_stack, 1)

        self.hint = QLabel("Click roster to add. Drag to reorder ranking.", right)
        self.hint.setStyleSheet(TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;")
        right.add_widget(self.hint)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE_SM)
        self.btn_sort = LLButton("Sort by winrate", parent=right)
        self.btn_sort.setToolTip("Sort ARAM priorities by Lolalytics win rate (highest first)")
        self.btn_sort.clicked.connect(self._on_sort_by_winrate)
        buttons.addWidget(self.btn_sort)

        self.btn_remove = LLButton("Remove", parent=right)
        self.btn_remove.clicked.connect(self._on_remove_selected)
        buttons.addWidget(self.btn_remove)

        self.btn_clear = LLButton("Clear all", variant=ButtonVariant.DANGER, parent=right)
        self.btn_clear.clicked.connect(self._on_clear_all)
        buttons.addWidget(self.btn_clear)
        buttons.addStretch(1)
        right.add_layout(buttons)

        columns.addWidget(right, 2)

    def _champ_name(self, cid: int) -> str:
        getter = getattr(self.assets, "get_champ_name", None)
        if callable(getter):
            try:
                name = getter(cid)
                if name and name != str(cid):
                    return name
            except Exception:
                pass
        tile = self.grid.tiles.get(int(cid)) if self.grid.tiles else None
        return tile.model.name if tile is not None else str(cid)

    def _display_name(self, cid: int) -> str:
        name = self._champ_name(cid)
        if self.scraper:
            wr = self.scraper.get_winrate(name)
            return f"{name}  ({wr:.1f}% WR)"
        return name

    def _load_config_state(self) -> None:
        if not self.config:
            self._sync_grid_badges()
            return
        self.row_bench_swap.set_checked(bool(self.config.get("aram_bench_swap", True)))
        self.row_auto_reroll.set_checked(bool(self.config.get("aram_auto_reroll", False)))

        self.prio_list_widget.clear()
        for cid in self.config.get("aram_priority_list", []) or []:
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            self._append_item(cid_int)
        self._renumber_items()
        self._sync_grid_badges()

    def _append_item(self, champ_id: int) -> None:
        item = QListWidgetItem(self._champ_name(champ_id))
        item.setData(Qt.UserRole, champ_id)
        self.prio_list_widget.addItem(item)

    def _current_ids(self) -> List[int]:
        return [
            self.prio_list_widget.item(i).data(Qt.UserRole)
            for i in range(self.prio_list_widget.count())
        ]

    def _renumber_items(self) -> None:
        for i in range(self.prio_list_widget.count()):
            item = self.prio_list_widget.item(i)
            item.setText("#{}  {}".format(i + 1, self._display_name(item.data(Qt.UserRole))))

    def _sync_grid_badges(self) -> None:
        ids = self._current_ids()
        self.grid.set_priority_ids(ids)
        self.list_stack.setCurrentIndex(1 if ids else 0)
        self.btn_sort.setEnabled(bool(ids))
        self.btn_remove.setEnabled(bool(ids))
        self.btn_clear.setEnabled(bool(ids))
        self.hint.setVisible(bool(ids))

    def _save(self) -> None:
        if self.config:
            self.config.set("aram_priority_list", self._current_ids())
        self._sync_grid_badges()

    def _set_cfg(self, key: str, value) -> None:
        if self.config:
            self.config.set(key, value)

    def _on_champion_clicked(self, champ_id: int, name: str) -> None:
        if champ_id in self._current_ids():
            return
        self._append_item(champ_id)
        self._renumber_items()
        self._save()

    def _on_rows_moved(self, *_args) -> None:
        self._renumber_items()
        self._save()

    def _on_sort_by_winrate(self) -> None:
        ids = self._current_ids()
        if not ids:
            return
        if self.scraper:
            ids.sort(key=lambda cid: self.scraper.get_winrate(self._champ_name(cid)), reverse=True)
        self.prio_list_widget.clear()
        for cid in ids:
            self._append_item(cid)
        self._renumber_items()
        self._save()

    def _on_remove_selected(self) -> None:
        row = self.prio_list_widget.currentRow()
        if row >= 0:
            self.prio_list_widget.takeItem(row)
            self._renumber_items()
            self._save()

    def _on_clear_all(self) -> None:
        self.prio_list_widget.clear()
        self._save()
