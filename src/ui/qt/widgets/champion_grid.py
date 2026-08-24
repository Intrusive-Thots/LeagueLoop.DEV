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

from ui.qt.components.flow_layout import LLFlowLayout
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
from utils.logger import Logger

_TILE_WIDTHS = {
    TileSize.SM: CHAMPION_TILE_SM[0],
    TileSize.MD: CHAMPION_TILE_MD[0],
    TileSize.LG: CHAMPION_TILE_LG[0],
}

#: One column is a legitimate answer. It used to be three, which meant a
#: panel narrower than 3 tiles + spacing + margins (about 280px) grew a
#: horizontal scrollbar and pushed the right-hand column off the edge — the
#: grid insisting on a density the panel could not hold. Tiles are never
#: shrunk to fit; the column count gives way instead.
MIN_COLUMNS = 1
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
    #: Emitted with the favourite champion keys after any change.
    favorites_changed = Signal(list)

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
        config=None,
        tile_size: TileSize = TileSize.MD,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.assets = asset_manager
        self.scraper = scraper
        #: Needed to persist favourites. Optional, so the grid still builds
        #: standalone in tests and screenshot tooling.
        self.config = config
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
        # Flow, not QHBox: ten chips in a fixed row made the grid demand
        # ~500px before a single champion was drawn, and in a narrower panel
        # Qt answered by shrinking each chip until its label was three dots.
        quick_row = LLFlowLayout(spacing=SPACE_SM)
        for key, label in self.QUICK_FILTERS:
            btn = self._make_filter_button(label, key == "ALL")
            btn.clicked.connect(lambda _c, k=key: self._on_quick_filter(k))
            self.quick_group.addButton(btn)
            quick_row.addWidget(btn)

        self.count_label = QLabel("", self)
        self.count_label.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        quick_row.addWidget(self.count_label)
        root.addLayout(quick_row)

        self.role_group = QButtonGroup(self)
        self.role_group.setExclusive(True)
        role_row = LLFlowLayout(spacing=SPACE_SM)
        for key, label in self.ROLES:
            btn = self._make_filter_button(label, key == "ALL")
            btn.clicked.connect(lambda _c, r=key: self._on_role_selected(r))
            self.role_group.addButton(btn)
            role_row.addWidget(btn)
        root.addLayout(role_row)

        # --- scrollable grid ---------------------------------------------
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        # The column count already adapts to the width, so a horizontal
        # scrollbar here can only mean the grid got the count wrong. Turning
        # it off makes that a visible layout bug rather than a silent one the
        # user has to scroll sideways around.
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
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
        # See eventFilter(): the viewport resizes independently of this widget.
        self.scroll_area.viewport().installEventFilter(self)
        root.addWidget(self.scroll_area, 1)

        # --- empty state (§54) -------------------------------------------
        self._has_champion_data = True
        self._retrying = False
        self.empty_label = QLabel("No champions match your search.", self)
        self.empty_label.setAlignment(Qt.AlignCenter)
        # Without wrapping, the longest empty-state sentence ("Champion data
        # has not loaded...") becomes the grid's minimum width — 672px — and
        # every parent inherits it. That is how a panel the user wanted at
        # 480px ended up demanding 1162px and squeezing every layout inside
        # it below its own minimum.
        self.empty_label.setWordWrap(True)
        self.empty_label.setMinimumWidth(0)
        self.empty_label.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.empty_label.setVisible(False)
        # Stretch 1, because it stands in for the scroll area: when the grid
        # is empty the scroll area is hidden, and whatever is left holding the
        # stretch is where the spare vertical space goes.
        root.addWidget(self.empty_label, 1)

        # A failed download used to be terminal for the whole session: the
        # only way to get champions back was to restart the app.
        from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton

        self.btn_retry = LLButton(
            "Try again", variant=ButtonVariant.SECONDARY,
            size=ButtonSize.SM, parent=self,
        )
        self.btn_retry.setVisible(False)
        self.btn_retry.clicked.connect(self._on_retry)
        root.addWidget(self.btn_retry, 0, Qt.AlignCenter)

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
            wr_source = self.scraper.winrate_source() if self.scraper else ""
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
                winrate_source=wr_source,
            )
            tile = LLChampionTile(
                model, size=self.tile_size,
                icon_provider=self.icons, parent=self.grid_container,
            )
            tile.clicked.connect(self._on_tile_clicked)
            tile.double_clicked.connect(self.champion_activated.emit)
            tile.context_menu_requested.connect(self.champion_context_menu.emit)
            # ...and to our own menu. The signal was only ever re-emitted for
            # callers that never existed, so right-clicking a champion did
            # nothing at all — which is why "Favourites" was a filter with no
            # way to put anything in it.
            tile.context_menu_requested.connect(self._show_champion_context_menu)
            self.tiles[cid] = tile

        self.load_favorites()
        self._apply_filters()

    def _can_retry(self) -> bool:
        return callable(getattr(self.assets, "retry_champion_data", None))

    def _on_retry(self) -> None:
        """
        Re-download champion data off the GUI thread, then rebuild.

        The download is network-bound; doing it inline freezes the window for
        as long as the CDN takes to answer or time out.
        """
        if self._retrying or not self._can_retry():
            return
        self._retrying = True
        self.btn_retry.setEnabled(False)
        self.btn_retry.setText("Trying…")

        from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

        grid = self

        class _Signals(QObject):
            done = Signal()

        class _Task(QRunnable):
            def __init__(self, signals):
                super().__init__()
                self._signals = signals

            def run(self):
                try:
                    grid.assets.retry_champion_data()
                except Exception as exc:
                    Logger.debug("ChampionGrid", "run suppressed an error", exc=exc)
                finally:
                    try:
                        self._signals.done.emit()
                    except RuntimeError:
                        pass

        self._retry_signals = _Signals(self)
        self._retry_signals.done.connect(self._on_retry_finished)
        QThreadPool.globalInstance().start(_Task(self._retry_signals))

    def _on_retry_finished(self) -> None:
        self._retrying = False
        self.btn_retry.setEnabled(True)
        self.btn_retry.setText("Try again")
        self.load_champions()

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
            wr_source = self.scraper.winrate_source() if self.scraper else ""
            tile.set_model(
                ChampionTileModel(
                    champ_id=m.champ_id, name=m.name, key=m.key,
                    priority=self._priority.get(m.key),
                    favorite=m.key in self._favorites,
                    owned=self._owned is None or m.key in self._owned,
                    banned=m.key in self._banned,
                    disabled=m.key in self._disabled,
                    winrate=winrate,
                    winrate_source=wr_source,
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
                if self.current_role.upper() not in [
                    str(r).upper() for r in roles
                ]:
                    # An unknown role is not a match. Treating it as one is
                    # what made every role chip a no-op.
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
            reason = getattr(self.assets, "champion_data_error", "") or ""
            self.empty_label.setText(
                "Champion data has not loaded.\n\n"
                "LeagueLoop downloads the champion list from Riot's Data "
                "Dragon. " + (
                    "The last attempt failed: {}".format(reason) if reason
                    else "It has not finished downloading yet."
                )
            )
            self.btn_retry.setVisible(bool(reason) and self._can_retry())
        elif shown == 0 and self.quick_filter == "FAVORITES" and not self._favorites:
            # A filter with nothing behind it and no way to fill it is the
            # worst kind of empty state: it reads as a broken feature.
            self.empty_label.setText(
                "No favourites yet.\n\n"
                "Right-click any champion and choose Add to Favourites."
            )
            self.btn_retry.setVisible(False)
        elif shown == 0:
            self.empty_label.setText("No champions match your search.")
            self.btn_retry.setVisible(False)
        else:
            self.btn_retry.setVisible(False)
        self.empty_label.setVisible(shown == 0)
        self.scroll_area.setVisible(shown > 0)
        self._maybe_relayout()

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
        self._maybe_relayout()

    def eventFilter(self, watched, event) -> bool:
        """
        Recount columns when the *viewport* resizes, not just this widget.

        Column count is derived from `scroll_area.viewport().width()`, but the
        viewport is resized by the scroll area independently of this widget —
        when a scrollbar appears, when a splitter moves, or simply later in
        the layout pass. Watching only our own resizeEvent meant the grid kept
        whatever column count it happened to compute first, which is why a
        540px panel rendered three columns in space that fits five.
        """
        from PySide6.QtCore import QEvent

        if watched is self.scroll_area.viewport() and event.type() == QEvent.Resize:
            self._maybe_relayout()
        return super().eventFilter(watched, event)

    def _maybe_relayout(self) -> None:
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
        """
        Mark or unmark a favourite, and remember it.

        This used to mutate an in-memory set and nothing else, so even when
        the menu was reachable your favourites were gone on the next launch.
        """
        if key in self._favorites:
            self._favorites.remove(key)
        else:
            self._favorites.add(key)
        self._save_favorites()
        self._refresh_models()
        self.favorites_changed.emit(sorted(self._favorites))

    # ------------------------------------------------------------ storage
    def _favorite_ids(self):
        """Favourites as champion ids. Keys are a rendering detail."""
        ids = []
        for tile in self.tiles.values():
            if tile.model.key in self._favorites:
                ids.append(int(tile.model.champ_id))
        return sorted(ids)

    def _save_favorites(self) -> None:
        if self.config is None:
            return
        try:
            from core.config_keys import FAVORITE_CHAMPIONS

            self.config.set(FAVORITE_CHAMPIONS, self._favorite_ids())
        except Exception as exc:
            Logger.debug("ChampionGrid", "_save_favorites suppressed an error", exc=exc)

    def load_favorites(self) -> None:
        """
        Restore favourites from config.

        Ids on disk, keys in the grid: an id survives a Data Dragon rename,
        and a key that no longer exists is simply dropped.
        """
        if self.config is None:
            return
        try:
            from core.config_keys import FAVORITE_CHAMPIONS, read_champion_ids

            ids = set(read_champion_ids(self.config, FAVORITE_CHAMPIONS))
        except Exception:
            return

        keys = set()
        for cid in ids:
            tile = self.tiles.get(int(cid))
            if tile is not None:
                keys.add(tile.model.key)
        if keys != self._favorites:
            self._favorites = keys
            self._refresh_models()
