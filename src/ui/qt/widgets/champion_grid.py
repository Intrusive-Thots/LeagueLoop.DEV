"""
Champion grid (UI/UX Master Plan §9, §10, §47, §66).

The plan's flagship component. Compared to the first prototype this adds:

  * real champion art, loaded asynchronously and memory-cached (§67)
  * responsive columns - narrow ~3, normal ~5, wide 6-8 (§9)
  * the full tile state set: priority, favourite, banned, unowned,
    disabled, loading, error (§9)
  * keyboard use: type to filter, arrows to move, Enter to pick, Esc to
    clear (§10)
  * quick filters: All / Favourites / Priority / Owned, plus role (§47)

Public API is unchanged from the prototype (`champion_selected`,
`load_champions`), so existing callers keep working.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.champion_tile import (
    ChampionTileModel,
    LLChampionTile,
    TileSize,
)
from ui.qt.services.champion_icons import ChampionIconProvider
from ui.qt.theme.colors import (
    BORDER_ACCENT,
    BORDER_DEFAULT,
    FOCUS_RING,
    FOCUS_RING_WIDTH,
    GOLD_LIGHT,
    GOLD_PRIMARY,
    SURFACE_PANEL,
    SURFACE_PANEL_HOVER,
    SURFACE_SUNKEN,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.radii import RADIUS_MD, RADIUS_SM
from ui.qt.theme.spacing import (
    CHAMPION_TILE_MD,
    CONTROL_HEIGHT_SM,
    SPACE_MD,
    SPACE_SM,
)
from ui.qt.theme.typography import FONT_FAMILY, TEXT_BODY, WEIGHT_MEDIUM

from ui.qt.theme.spacing import CHAMPION_TILE_LG, CHAMPION_TILE_SM

_TILE_WIDTHS = {
    TileSize.SM: CHAMPION_TILE_SM[0],
    TileSize.MD: CHAMPION_TILE_MD[0],
    TileSize.LG: CHAMPION_TILE_LG[0],
}

MIN_COLUMNS = 3
MAX_COLUMNS = 8

#: Popular-champion fallback used when no AssetManager data is available.
#: Set when `_champion_rows()` found no champion data. The grid renders an
#: honest empty state instead of inventing a roster - there used to be a
#: hardcoded list of twelve champions here, which meant a machine whose
#: assets had not downloaded showed a plausible-looking roster that was not
#: yours. Fake data that looks real is worse than no data (§22, §54).
_NO_CHAMPION_DATA = "no_champion_data"


def _fuzzy_match(query: str, *fields: str) -> bool:
    """
    Forgiving match so "kai sa", "kaisa" and "kai" all find Kai'Sa (§10).

    Punctuation and spaces are ignored, then it is a simple substring test
    plus a subsequence test for skipped characters.
    """
    if not query:
        return True
    q = "".join(ch for ch in query.lower() if ch.isalnum())
    if not q:
        return True

    for field in fields:
        if not field:
            continue
        f = "".join(ch for ch in field.lower() if ch.isalnum())
        if q in f:
            return True
        # subsequence fallback
        it = iter(f)
        if all(ch in it for ch in q):
            return True
    return False


class QtChampionGrid(QWidget):
    """Searchable, filterable, responsive champion grid."""

    champion_selected = Signal(int, str)
    champion_activated = Signal(int, str)          # double-click / Enter
    champion_context_menu = Signal(int, object)

    ROLES = [
        ("ALL", "All"), ("TOP", "Top"), ("JUNGLE", "Jungle"),
        ("MIDDLE", "Mid"), ("BOTTOM", "Bot"), ("UTILITY", "Support"),
    ]
    QUICK_FILTERS = [
        ("ALL", "All"), ("FAVORITES", "Favourites"),
        ("PRIORITY", "Priority"), ("OWNED", "Owned"),
    ]

    def __init__(
        self,
        asset_manager=None,
        scraper=None,
        tile_size: TileSize = TileSize.MD,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.assets = asset_manager
        self.scraper = scraper
        self.tile_size = tile_size

        self.current_role = "ALL"
        self.quick_filter = "ALL"
        self.search_query = ""
        self.selected_champ_id: Optional[int] = None

        self.tiles: Dict[int, LLChampionTile] = {}
        self._visible_ids: List[int] = []
        self._columns = 5

        self._priority: Dict[str, int] = {}   # champion key -> rank
        self._favorites: Set[str] = set()
        self._owned: Optional[Set[str]] = None   # None = assume all owned
        self._banned: Set[str] = set()
        self._disabled: Set[str] = set()

        self.icons = ChampionIconProvider(asset_manager=asset_manager, parent=self)
        self.icons.icon_ready.connect(self._on_icon_ready)
        self.champion_context_menu.connect(self._show_champion_context_menu)

        self._setup_ui()
        self.load_champions()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACE_SM)

        # --- search ------------------------------------------------------
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search champions...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(CONTROL_HEIGHT_SM + 4)
        self.search_input.textChanged.connect(self._on_search_changed)
        self.search_input.returnPressed.connect(self._activate_first_visible)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SURFACE_SUNKEN};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_SM}px;
                padding: 0px {SPACE_SM}px;
                color: {TEXT_PRIMARY};
                font-family: {FONT_FAMILY};
                font-size: 13px;
            }}
            QLineEdit:focus {{ border: {FOCUS_RING_WIDTH}px solid {FOCUS_RING}; }}
        """)
        root.addWidget(self.search_input)

        # --- filter rows -------------------------------------------------
        self.quick_group = QButtonGroup(self)
        self.quick_group.setExclusive(True)
        quick_row = QHBoxLayout()
        quick_row.setSpacing(SPACE_SM)
        for key, label in self.QUICK_FILTERS:
            btn = self._make_filter_button(label, key == "ALL")
            btn.clicked.connect(lambda _c, k=key: self._on_quick_filter(k))
            self.quick_group.addButton(btn)
            quick_row.addWidget(btn)
        quick_row.addStretch(1)

        self.count_label = QLabel("", self)
        self.count_label.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        quick_row.addWidget(self.count_label)
        root.addLayout(quick_row)

        self.role_group = QButtonGroup(self)
        self.role_group.setExclusive(True)
        role_row = QHBoxLayout()
        role_row.setSpacing(SPACE_SM)
        for key, label in self.ROLES:
            btn = self._make_filter_button(label, key == "ALL")
            btn.clicked.connect(lambda _c, r=key: self._on_role_selected(r))
            self.role_group.addButton(btn)
            role_row.addWidget(btn)
        role_row.addStretch(1)
        root.addLayout(role_row)

        # --- scrollable grid ---------------------------------------------
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD}px;
            }}
        """)

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(SPACE_MD, SPACE_MD, SPACE_MD, SPACE_MD)
        self.grid_layout.setSpacing(SPACE_SM)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll_area.setWidget(self.grid_container)
        root.addWidget(self.scroll_area, 1)

        # --- empty state (§54) -------------------------------------------
        self._has_champion_data = True
        self.empty_label = QLabel("No champions match your search.", self)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.empty_label.setVisible(False)
        root.addWidget(self.empty_label)

    def _make_filter_button(self, label: str, checked: bool) -> QPushButton:
        btn = QPushButton(label, self)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(CONTROL_HEIGHT_SM)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                border: 1px solid transparent;
                border-radius: {RADIUS_SM}px;
                padding: 0px {SPACE_MD}px;
                font-family: {FONT_FAMILY};
                font-size: 12px;
                font-weight: {WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: {SURFACE_PANEL_HOVER};
                color: {TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: {SURFACE_PANEL};
                color: {GOLD_LIGHT};
                border: 1px solid {BORDER_ACCENT};
            }}
            QPushButton[keyboardFocus="true"] {{
                border: {FOCUS_RING_WIDTH}px solid {FOCUS_RING};
            }}
        """)
        return btn

    # ---------------------------------------------------------------- data
    def _champion_rows(self):
        """(id, name, key) for every champion, from AssetManager or fallback."""
        rows = []
        data = getattr(self.assets, "champ_data", None)
        if data:
            for key, info in data.items():
                try:
                    cid = int(info.get("key", 0))
                except (TypeError, ValueError):
                    continue
                if cid > 0:
                    rows.append((cid, info.get("name", key), key))
        rows.sort(key=lambda r: r[1].lower())
        self._has_champion_data = bool(rows)
        return rows

    def load_champions(self) -> None:
        """(Re)build every tile from the current champion source."""
        for tile in self.tiles.values():
            self.grid_layout.removeWidget(tile)
            tile.setParent(None)
            tile.deleteLater()
        self.tiles.clear()

        for cid, name, key in self._champion_rows():
            winrate = self.scraper.get_winrate(name) if self.scraper else None
            model = ChampionTileModel(
                champ_id=cid,
                name=name,
                key=key,
                priority=self._priority.get(key),
                favorite=key in self._favorites,
                owned=self._owned is None or key in self._owned,
                banned=key in self._banned,
                disabled=key in self._disabled,
                winrate=winrate,
            )
            tile = LLChampionTile(
                model, size=self.tile_size,
                icon_provider=self.icons, parent=self.grid_container,
            )
            tile.clicked.connect(self._on_tile_clicked)
            tile.double_clicked.connect(self.champion_activated.emit)
            tile.context_menu_requested.connect(self.champion_context_menu.emit)
            self.tiles[cid] = tile

        self._apply_filters()

    # ------------------------------------------------- external state setters
    def set_scraper(self, scraper) -> None:
        """Update the StatsScraper reference and refresh win rates."""
        self.scraper = scraper
        self._refresh_models()

    def set_priority(self, keys: Iterable[str]) -> None:
        """Mark champions as prioritised, in order (rank 1 first)."""
        self._priority = {k: i + 1 for i, k in enumerate(keys) if k}
        self._refresh_models()

    def set_priority_ids(self, champ_ids: Iterable[int]) -> None:
        """
        Mark priorities by champion id, in rank order.

        Config stores ids while tiles are keyed by DDragon key, so translate
        through the tiles we already built rather than requiring callers to
        know the mapping.
        """
        keys = []
        for cid in champ_ids:
            try:
                tile = self.tiles.get(int(cid))
            except (TypeError, ValueError):
                tile = None
            if tile is not None:
                keys.append(tile.model.key)
        self.set_priority(keys)

    def set_favorites(self, keys: Iterable[str]) -> None:
        self._favorites = set(keys)
        self._refresh_models()

    def set_owned(self, keys: Optional[Iterable[str]]) -> None:
        self._owned = None if keys is None else set(keys)
        self._refresh_models()

    def set_banned(self, keys: Iterable[str]) -> None:
        self._banned = set(keys)
        self._refresh_models()

    def set_disabled(self, keys: Iterable[str]) -> None:
        self._disabled = set(keys)
        self._refresh_models()

    def _refresh_models(self) -> None:
        for tile in self.tiles.values():
            m = tile.model
            winrate = self.scraper.get_winrate(m.name) if self.scraper else m.winrate
            tile.set_model(
                ChampionTileModel(
                    champ_id=m.champ_id, name=m.name, key=m.key,
                    priority=self._priority.get(m.key),
                    favorite=m.key in self._favorites,
                    owned=self._owned is None or m.key in self._owned,
                    banned=m.key in self._banned,
                    disabled=m.key in self._disabled,
                    winrate=winrate,
                )
            )
        self._apply_filters()

    # ------------------------------------------------------------- filtering
    def _matches(self, tile: LLChampionTile) -> bool:
        m = tile.model
        if not _fuzzy_match(self.search_query, m.name, m.key):
            return False

        if self.quick_filter == "FAVORITES" and not m.favorite:
            return False
        if self.quick_filter == "PRIORITY" and not m.priority:
            return False
        if self.quick_filter == "OWNED" and not m.owned:
            return False

        if self.current_role != "ALL":
            getter = getattr(self.assets, "get_champ_roles", None)
            if callable(getter):
                try:
                    roles = getter(m.champ_id) or []
                except Exception:
                    roles = []
                if roles and self.current_role.upper() not in [
                    str(r).upper() for r in roles
                ]:
                    return False
        return True

    def _apply_filters(self) -> None:
        self._visible_ids = [
            cid for cid, tile in self.tiles.items() if self._matches(tile)
        ]
        # Preserve the source ordering (alphabetical).
        order = {cid: i for i, (cid, _, _) in enumerate(self._champion_rows())}
        self._visible_ids.sort(key=lambda c: order.get(c, 0))
        self._relayout()

        total = len(self.tiles)
        shown = len(self._visible_ids)
        self.count_label.setText(
            "{} champions".format(total) if shown == total
            else "{} of {}".format(shown, total)
        )
        if shown == 0 and not self._has_champion_data:
            # Distinguish "your search matched nothing" from "we have no
            # champion data at all" - they need completely different actions.
            self.empty_label.setText(
                "Champion data has not loaded yet.\n\n"
                "LeagueLoop downloads the champion list from Riot's Data "
                "Dragon on first run. Check your connection, or open the "
                "League Client once so it can be fetched."
            )
        elif shown == 0:
            self.empty_label.setText("No champions match your search.")
        self.empty_label.setVisible(shown == 0)
        self.scroll_area.setVisible(shown > 0)

    def _column_count(self) -> int:
        tile_w = _TILE_WIDTHS.get(self.tile_size, CHAMPION_TILE_MD[0])
        available = max(0, self.scroll_area.viewport().width() - 2 * SPACE_MD)
        cols = max(MIN_COLUMNS, (available + SPACE_SM) // (tile_w + SPACE_SM))
        return int(min(MAX_COLUMNS, cols))

    def _relayout(self) -> None:
        """
        Place visible tiles on the responsive grid; hide the rest.

        Uses removeWidget rather than takeAt(): in PySide6 takeAt() hands
        ownership of the returned item to Python, and when that item is
        garbage collected it destroys the underlying widget - which segfaults
        the next time the grid repaints.
        """
        for tile in self.tiles.values():
            self.grid_layout.removeWidget(tile)
            tile.hide()

        self._columns = self._column_count()
        for index, cid in enumerate(self._visible_ids):
            tile = self.tiles.get(cid)
            if tile is None:
                continue
            self.grid_layout.addWidget(
                tile, index // self._columns, index % self._columns
            )
            tile.show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.tiles and self._column_count() != self._columns:
            self._relayout()

    # --------------------------------------------------------------- events
    def _on_icon_ready(self, key: str, size: int) -> None:
        for tile in self.tiles.values():
            if tile.model.key == key:
                tile.on_icon_ready(key, size)

    def _on_search_changed(self, text: str) -> None:
        self.search_query = text.strip().lower()
        self._apply_filters()

    def _on_role_selected(self, role: str) -> None:
        self.current_role = role
        self._apply_filters()

    def _on_quick_filter(self, key: str) -> None:
        self.quick_filter = key
        self._apply_filters()

    def _on_tile_clicked(self, champ_id: int, name: str) -> None:
        self.select_champion(champ_id)
        self.champion_selected.emit(champ_id, name)

    def select_champion(self, champ_id: Optional[int]) -> None:
        if self.selected_champ_id in self.tiles:
            self.tiles[self.selected_champ_id].set_selected(False)
        self.selected_champ_id = champ_id
        if champ_id in self.tiles:
            self.tiles[champ_id].set_selected(True)

    def _activate_first_visible(self) -> None:
        """Enter in the search box picks the first result (§10)."""
        for cid in self._visible_ids:
            tile = self.tiles.get(cid)
            if tile is not None and tile.model.selectable:
                self._on_tile_clicked(cid, tile.model.name)
                tile.setFocus(Qt.ShortcutFocusReason)
                return

    def keyPressEvent(self, event) -> None:
        key = event.key()

        if key == Qt.Key_Escape:
            if self.search_input.text():
                self.search_input.clear()
                event.accept()
                return

        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            if self._move_selection(key):
                event.accept()
                return

        super().keyPressEvent(event)

    def _move_selection(self, key) -> bool:
        if not self._visible_ids:
            return False
        try:
            index = self._visible_ids.index(self.selected_champ_id)
        except ValueError:
            index = -1

        step = {
            Qt.Key_Left: -1, Qt.Key_Right: 1,
            Qt.Key_Up: -self._columns, Qt.Key_Down: self._columns,
        }[key]

        new_index = max(0, min(len(self._visible_ids) - 1, index + step))
        cid = self._visible_ids[new_index]
        self.select_champion(cid)
        tile = self.tiles.get(cid)
        if tile is not None:
            tile.setFocus(Qt.TabFocusReason)
            self.scroll_area.ensureWidgetVisible(tile)
        return True

    def _show_champion_context_menu(self, champ_id: int, pos) -> None:
        """Right-click context menu on champion tiles."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtCore import QPoint

        tile = self.tiles.get(champ_id)
        if tile is None:
            return

        menu = QMenu(self)
        name = tile.model.name

        act_select = menu.addAction(f"Select {name}")
        act_select.triggered.connect(lambda: self.champion_selected.emit(champ_id, name))

        act_act = menu.addAction(f"Lock in / Activate {name}")
        act_act.triggered.connect(lambda: self.champion_activated.emit(champ_id, name))

        menu.addSeparator()

        is_fav = tile.model.favorite
        fav_label = "★ Remove from Favourites" if is_fav else "☆ Add to Favourites"
        act_fav = menu.addAction(fav_label)
        act_fav.triggered.connect(lambda: self._toggle_favorite(tile.model.key))

        global_pos = pos if isinstance(pos, QPoint) else tile.mapToGlobal(QPoint(0, 0))
        menu.exec(global_pos)

    def _toggle_favorite(self, key: str) -> None:
        if key in self._favorites:
            self._favorites.remove(key)
        else:
            self._favorites.add(key)
        self._refresh_models()
