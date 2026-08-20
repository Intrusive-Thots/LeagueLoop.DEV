"""
Generic champion-list screen (UI/UX Master Plan §8, §33, §45).

Priority picks, ARAM priorities and the ban list are the same interaction:
choose champions from the roster, order them, save the ordered ids to a
config key. So they are one screen parameterised by that key, rather than
three near-identical files that drift apart.

    QtPriorityTab   -> priority_list
    QtAramTab       -> aram_priority_list
    QtBanListTab    -> ban_list
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import ButtonVariant, LLButton
from ui.qt.components.card import LLSection
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


class QtChampionListTab(QWidget):
    """Roster on the left, an ordered champion list on the right."""

    #: Subclasses override these.
    CONFIG_KEY = "priority_list"
    TITLE = "Priority"
    LIST_TITLE = "Pick priority order"
    EMPTY_TEXT = (
        "No champions in your priority list.\n\n"
        "Pick one from the roster to make it your first choice."
    )
    HINT = "Click a champion to add. Drag to reorder."

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

        self._setup_ui()
        self._load_list()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        title = QLabel(self.TITLE, self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        root.addWidget(title)

        columns = QHBoxLayout()
        columns.setSpacing(SPACE_LG)
        root.addLayout(columns, 1)

        left = LLSection("Champion roster", parent=self)
        self.grid = QtChampionGrid(asset_manager=self.assets, scraper=self.scraper, parent=left)
        self.grid.champion_selected.connect(self._on_champion_clicked)
        self.grid.champion_activated.connect(self._on_champion_clicked)
        left.add_widget(self.grid, 1)
        columns.addWidget(left, 3)

        right = LLSection(self.LIST_TITLE, parent=self)

        self.list_widget = QListWidget(right)
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {SURFACE_PANEL};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD}px;
                color: {TEXT_PRIMARY};
                font-size: 13px;
                padding: 4px;
            }}
            QListWidget::item {{ padding: 7px 6px; border-radius: 4px; }}
            QListWidget::item:hover {{ background-color: {SURFACE_PANEL_HOVER}; }}
            QListWidget::item:selected {{
                background-color: {SURFACE_PANEL_HOVER};
                color: {GOLD_LIGHT};
                border: 1px solid {BORDER_ACCENT};
            }}
        """)

        self.empty_state = QLabel(self.EMPTY_TEXT, right)
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
        self.list_stack.addWidget(self.empty_state)    # 0
        self.list_stack.addWidget(self.list_widget)    # 1
        right.add_widget(self.list_stack, 1)

        self.hint = QLabel(self.HINT, right)
        self.hint.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        right.add_widget(self.hint)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE_SM)
        self.btn_sort = LLButton("Sort by winrate", parent=right)
        self.btn_sort.setToolTip("Sort champions by Lolalytics win rate (highest first)")
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

    # ---------------------------------------------------------------- data
    def _champ_name(self, champ_id: int) -> str:
        name = ""
        getter = getattr(self.assets, "get_champ_name", None)
        if callable(getter):
            try:
                val = getter(champ_id)
                if val and val != str(champ_id):
                    name = val
            except Exception:
                pass
        if not name:
            tile = self.grid.tiles.get(int(champ_id)) if self.grid.tiles else None
            name = tile.model.name if tile is not None else str(champ_id)
        return name

    def _display_name(self, champ_id: int) -> str:
        name = self._champ_name(champ_id)
        if self.scraper and self.CONFIG_KEY != "ban_list":
            wr = self.scraper.get_winrate(name)
            return f"{name}  ({wr:.1f}% WR)"
        return name

    def _load_list(self) -> None:
        self.list_widget.clear()
        if self.config:
            for cid in self.config.get(self.CONFIG_KEY, []) or []:
                try:
                    self._append_item(int(cid))
                except (TypeError, ValueError):
                    continue
        self._renumber_items()
        self._sync_grid_badges()

    def _append_item(self, champ_id: int) -> None:
        item = QListWidgetItem(self._champ_name(champ_id))
        item.setData(Qt.UserRole, champ_id)
        self.list_widget.addItem(item)

    def current_ids(self) -> List[int]:
        return [
            self.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.list_widget.count())
        ]

    def _renumber_items(self) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            cid = item.data(Qt.UserRole)
            item.setText("#{}  {}".format(i + 1, self._display_name(cid)))

    def _sync_grid_badges(self) -> None:
        ids = self.current_ids()
        self.grid.set_priority_ids(ids)
        self.list_stack.setCurrentIndex(1 if ids else 0)
        self.btn_sort.setEnabled(bool(ids))
        self.btn_remove.setEnabled(bool(ids))
        self.btn_clear.setEnabled(bool(ids))
        self.hint.setVisible(bool(ids))

    def _save(self) -> None:
        if self.config:
            self.config.set(self.CONFIG_KEY, self.current_ids())
        self._sync_grid_badges()

    # -------------------------------------------------------------- actions
    def _on_champion_clicked(self, champ_id: int, name: str) -> None:
        if champ_id in self.current_ids():
            return
        self._append_item(champ_id)
        self._renumber_items()
        self._save()

    def _on_rows_moved(self, *_args) -> None:
        self._renumber_items()
        self._save()

    def _on_sort_by_winrate(self) -> None:
        ids = self.current_ids()
        if not ids:
            return
        if self.scraper:
            ids.sort(key=lambda cid: self.scraper.get_winrate(self._champ_name(cid)), reverse=True)
        self.list_widget.clear()
        for cid in ids:
            self._append_item(cid)
        self._renumber_items()
        self._save()

    def _on_remove_selected(self) -> None:
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)
            self._renumber_items()
            self._save()

    def _on_clear_all(self) -> None:
        self.list_widget.clear()
        self._save()


class QtPriorityTab(QtChampionListTab):
    """Ranked pick priorities used by the Draft Assistant (§8)."""

    CONFIG_KEY = "priority_list"
    TITLE = "Priority"
    LIST_TITLE = "Pick priority order"

    def __init__(self, container=None, view_model=None, parent=None):
        super().__init__(container=container, view_model=view_model, parent=parent)
        # Name kept from the first Qt prototype; some callers/tests use it.
        self.prio_list_widget = self.list_widget
        if self.scraper:
            self.scraper.set_mode("Ranked")
            self.grid.set_scraper(self.scraper)
            self._renumber_items()

    # Retained for callers written against the earlier implementation.
    def _current_ids(self) -> List[int]:
        return self.current_ids()


class QtAramTab(QtChampionListTab):
    """ARAM champion priorities used by Priority Sniper in ARAM queues."""

    CONFIG_KEY = "aram_priority_list"
    TITLE = "ARAM"
    LIST_TITLE = "ARAM priority order"
    EMPTY_TEXT = (
        "No ARAM priorities set.\n\n"
        "Pick champions you want to roll or trade for in ARAM."
    )

    def __init__(self, container=None, view_model=None, parent=None):
        super().__init__(container=container, view_model=view_model, parent=parent)
        if self.scraper:
            self.scraper.set_mode("ARAM")
            self.grid.set_scraper(self.scraper)
            self._renumber_items()


class QtBanListTab(QtChampionListTab):
    """Ordered ban list (§8)."""

    CONFIG_KEY = "ban_list"
    TITLE = "Bans"
    LIST_TITLE = "Ban order"
    EMPTY_TEXT = (
        "No champions in your ban list.\n\n"
        "Pick the champions you most want banned, in order."
    )
    HINT = "Teammate-hovered champions are skipped automatically."
