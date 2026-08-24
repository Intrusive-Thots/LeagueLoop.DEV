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

from core.config_keys import (
    ARAM_AUTO_REROLL,
    ARAM_BENCH_SWAP,
    ARAM_PRIORITY_LIST,
    BAN_LIST,
    PRIORITY_LIST,
)
from typing import List, Optional

from PySide6.QtCore import QSize, Qt
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

from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.modal import LLConfirmModal
from ui.qt.components.card import LLCard, LLSection, LLSeparator
from ui.qt.components.flow_layout import LLFlowLayout
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
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD, SPACE_SM, SPACE_XS
from ui.qt.theme.typography import TEXT_BODY, TEXT_CAPTION, TEXT_PAGE_TITLE
from ui.qt.widgets.champion_grid import QtChampionGrid
from utils.logger import Logger


#: Portrait size in the priority list, and the row it sits in.
LIST_ICON_SIZE = 28
LIST_ROW_HEIGHT = 40


#: Portrait size in the priority list, and the row height it sits in.
LIST_ICON_SIZE = 28
LIST_ROW_HEIGHT = 40


class QtChampionListTab(QWidget):
    """Roster on the left, an ordered champion list on the right."""

    #: Subclasses override these.
    CONFIG_KEY = PRIORITY_LIST
    #: (config key, label) pairs offered as a mode switch, or () for none.
    MODES: tuple = ()
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
        self._sync_mode_buttons()
        self._sync_scraper_mode()
        self._sync_aram_rules()
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
        # Shares the roster grid's icon provider so portraits in the list come
        # from the same cache rather than a second set of downloads.
        from ui.qt.services.champion_icons import ChampionIconProvider

        self.icons = ChampionIconProvider(asset_manager=self.assets, parent=self)
        self.icons.icon_ready.connect(self._on_list_icon_ready)
        self._pending_icons = {}

        self.grid = QtChampionGrid(asset_manager=self.assets, scraper=self.scraper, config=self.config, parent=left)
        self.grid.champion_selected.connect(self._on_champion_clicked)
        self.grid.champion_activated.connect(self._on_champion_clicked)
        left.add_widget(self.grid, 1)
        columns.addWidget(left, 3)

        right = LLSection(self.LIST_TITLE, parent=self)

        # Summoner's Rift and ARAM were two separate navigation entries editing
        # two config keys through two near-identical screens — which is how one
        # of them ended up with a paste button that crashed on a method the
        # other had under a different name. One screen, one implementation, a
        # mode switch.
        if self.MODES:
            mode_row = QHBoxLayout()
            mode_row.setSpacing(SPACE_XS)
            self._mode_buttons = {}
            for key, label in self.MODES:
                btn = LLButton(
                    label, variant=ButtonVariant.GHOST, size=ButtonSize.SM, parent=right
                )
                btn.setCheckable(True)
                btn.clicked.connect(lambda _c, k=key: self.set_mode(k))
                mode_row.addWidget(btn)
                self._mode_buttons[key] = btn
            mode_row.addStretch(1)
            right.add_layout(mode_row)

        # The ARAM automation rules used to live on a separate screen that is
        # no longer reachable. `aram_bench_swap` and `aram_auto_reroll` were
        # therefore keys the engine read and nothing could write — and the
        # Automation screen's "configure" action for both sent you here, to a
        # screen that had no control for either.
        self.aram_rules = LLCard(title="ARAM automation", parent=right)
        self.row_bench_swap = LLSettingRow(
            "Auto Bench Sniper",
            "Takes a champion from the bench as soon as it is one you wanted.",
            checked=False,
            parent=self.aram_rules,
        )
        self.row_bench_swap.toggled.connect(
            lambda v: self._set_cfg(ARAM_BENCH_SWAP, v)
        )
        self.aram_rules.add_widget(self.row_bench_swap)
        self.aram_rules.add_widget(LLSeparator(parent=self.aram_rules))

        self.row_auto_reroll = LLSettingRow(
            "Reroll below your top 3",
            "Spends a reroll when the champion you were given is not in your "
            "first three choices.",
            checked=False,
            parent=self.aram_rules,
        )
        self.row_auto_reroll.toggled.connect(
            lambda v: self._set_cfg(ARAM_AUTO_REROLL, v)
        )
        self.aram_rules.add_widget(self.row_auto_reroll)
        self.aram_rules.setVisible(False)
        right.add_widget(self.aram_rules)

        self.list_widget = QListWidget(right)
        self.prio_list_widget = self.list_widget
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
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        right.add_widget(self.hint)

        # Four buttons that must never be squeezed into slivers: they wrap
        # onto a second line in a narrow panel instead.
        buttons = LLFlowLayout(spacing=SPACE_SM)
        self.btn_sort = LLButton("Sort by winrate", parent=right)
        self.btn_sort.setToolTip("Sort champions by Lolalytics win rate (highest first)")
        self.btn_sort.clicked.connect(self._on_sort_by_winrate)
        # Disabled is a designed state (§63). Win rates are only available
        # when they have actually been fetched; without them this button
        # would reorder your list by a constant.
        _live = self._can_sort()
        self.btn_sort.setEnabled(_live)
        self.btn_sort.setToolTip(
            "Order your list by community win rate" if _live
            else "Win rate data is not available, so there is nothing to sort by"
        )
        buttons.addWidget(self.btn_sort)

        # Most people already keep this list somewhere else — a Discord
        # message, a spreadsheet, a tier-list page. Retyping sixty champions
        # one click at a time is why a list like this goes stale.
        self.btn_paste = LLButton("Paste list", parent=right)
        self.btn_paste.setToolTip(
            "Import champion names from your clipboard, in the order pasted"
        )
        self.btn_paste.clicked.connect(self._on_paste_list)
        buttons.addWidget(self.btn_paste)

        self.btn_remove = LLButton("Remove", parent=right)
        self.btn_remove.clicked.connect(self._on_remove_selected)
        buttons.addWidget(self.btn_remove)

        self.btn_clear = LLButton("Clear all", variant=ButtonVariant.DANGER, parent=right)
        self.btn_clear.clicked.connect(self._on_clear_all)
        buttons.addWidget(self.btn_clear)
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
            except Exception as exc:
                Logger.debug("ChampionListTab", "_champ_name suppressed an error", exc=exc)
        if not name:
            tile = self.grid.tiles.get(int(champ_id)) if self.grid.tiles else None
            name = tile.model.name if tile is not None else str(champ_id)
        return name

    def _display_name(self, champ_id: int) -> str:
        name = self._champ_name(champ_id)
        if self.scraper and self.CONFIG_KEY != BAN_LIST:
            wr = self.scraper.get_winrate(name)
            # None means nobody measured it. Showing "50.0% WR" for every
            # champion — which is what the old fallback did — is worse than
            # showing nothing, because it looks like data.
            if wr is not None:
                return f"{name}  ({wr:.1f}% WR)"
        return name

    def _load_list(self) -> None:
        self._pending_icons = {}
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
        """
        One row: rank, champion portrait, name.

        A ranked list of bare names is the hardest possible way to recognise
        sixty champions. The portrait is how you actually know who is who, and
        the icon provider already holds the art the roster grid uses.
        """
        item = QListWidgetItem()
        item.setData(Qt.UserRole, champ_id)
        item.setSizeHint(QSize(0, LIST_ROW_HEIGHT))
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, self._make_row(champ_id))

    def _make_row(self, champ_id: int) -> QWidget:
        row = QWidget(self.list_widget)
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(SPACE_SM, 2, SPACE_SM, 2)
        layout.setSpacing(SPACE_SM)

        rank = QLabel("", row)
        rank.setFixedWidth(24)
        rank.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        rank.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        layout.addWidget(rank)

        icon = QLabel(row)
        icon.setFixedSize(LIST_ICON_SIZE, LIST_ICON_SIZE)
        icon.setScaledContents(True)
        icon.setStyleSheet(
            "background-color: {}; border-radius: {}px;".format(
                SURFACE_PANEL_HOVER, RADIUS_MD
            )
        )
        self._apply_icon(icon, champ_id)
        layout.addWidget(icon)

        name = QLabel(self._display_name(champ_id), row)
        name.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_PRIMARY) + " background: transparent;"
        )
        layout.addWidget(name, 1)

        row.rank_label = rank
        row.champ_id = champ_id
        return row

    def _apply_icon(self, label, champ_id: int) -> None:
        """Set the portrait now if cached, and register for the async result."""
        key = ""
        mapping = getattr(self.assets, "id_to_key", None)
        if isinstance(mapping, dict):
            key = str(mapping.get(int(champ_id), "") or "")
        if not key:
            return
        self._pending_icons.setdefault(key, []).append(label)
        pixmap = self.icons.pixmap(key, LIST_ICON_SIZE)
        if pixmap is not None and not pixmap.isNull():
            label.setPixmap(pixmap)

    def _on_list_icon_ready(self, key: str, size: int) -> None:
        if size != LIST_ICON_SIZE:
            return
        pixmap = self.icons.pixmap(key, LIST_ICON_SIZE)
        if pixmap is None or pixmap.isNull():
            return
        for label in list(self._pending_icons.get(key, [])):
            try:
                label.setPixmap(pixmap)
            except RuntimeError:
                # The row was rebuilt between the request and the reply.
                continue

    def current_ids(self) -> List[int]:
        return [
            self.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.list_widget.count())
        ]

    def _renumber_items(self) -> None:
        for i in range(self.list_widget.count()):
            widget = self.list_widget.itemWidget(self.list_widget.item(i))
            if widget is not None and hasattr(widget, "rank_label"):
                widget.rank_label.setText(str(i + 1))

    def _sync_grid_badges(self) -> None:
        ids = self.current_ids()
        self.grid.set_priority_ids(ids)
        self.list_stack.setCurrentIndex(1 if ids else 0)
        # Sorting needs both a list *and* something to sort it by. This used
        # to re-enable on list contents alone, undoing the data check.
        self.btn_sort.setEnabled(bool(ids) and self._can_sort())
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
        """Rebuild the list after an internal move.

        Rows are custom widgets installed with `setItemWidget`, and
        `QAbstractItemView.InternalMove` re-serialises the item on the way
        through — the index widget does not survive it. The moved champion
        became a permanently blank row (no rank, no portrait, no name) and
        `_renumber_items` then skipped it forever, because the widget it
        looks for is None. The saved order was always right; only the screen
        was wrong.

        Rebuilding from the ids is cheap — a priority list is tens of entries,
        not thousands — and leaves every row whole.
        """
        ids = self.current_ids()
        self._pending_icons = {}
        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            for champ_id in ids:
                self._append_item(champ_id)
        finally:
            self.list_widget.blockSignals(False)
        self._renumber_items()
        self._save()

    def _on_paste_list(self) -> None:
        """
        Replace or extend this list from the clipboard.

        Unresolved names are reported rather than dropped: a list that
        silently lost four entries is worse than one that tells you.
        """
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        text = clipboard.text() if clipboard is not None else ""
        if not text.strip():
            self.hint.setText("Clipboard is empty — copy a list of champions first.")
            self.hint.setVisible(True)
            return

        from services.champion_list_import import parse_champion_list

        result = parse_champion_list(text, assets=self.assets)
        if not result.ok:
            self.hint.setText(result.summary)
            self.hint.setVisible(True)
            return

        current = len(self.current_ids())
        message = "{}\n\nThis replaces the {} champion{} currently in the list.".format(
            result.summary, current, "" if current == 1 else "s"
        )
        if result.unknown:
            message += "\n\nNot recognised: {}".format(", ".join(result.unknown))

        dialog = LLConfirmModal(
            "Import {} champions?".format(len(result.champion_ids)),
            message, "Replace list", parent=self, destructive=bool(current),
        )
        if dialog.exec() != LLConfirmModal.Accepted:
            return

        self._pending_icons = {}
        self.list_widget.clear()
        for cid in result.champion_ids:
            self._append_item(cid)
        self._renumber_items()
        self._sync_grid_badges()
        self._save()
        self.hint.setText(result.summary)
        self.hint.setVisible(True)

    def set_mode(self, config_key: str) -> None:
        """Switch which list this screen edits, and reload it."""
        if config_key == self.CONFIG_KEY:
            self._sync_mode_buttons()
            return
        self.CONFIG_KEY = config_key
        for key, btn in getattr(self, "_mode_buttons", {}).items():
            btn.setChecked(key == config_key)
        self._sync_scraper_mode()
        self._sync_aram_rules()
        self._load_list()
        self._sync_mode_buttons()

    def _set_cfg(self, key: str, value) -> None:
        if self.config:
            self.config.set(key, value)

    def _sync_aram_rules(self) -> None:
        """Show the ARAM rules only while the ARAM list is being edited."""
        rules = getattr(self, "aram_rules", None)
        if rules is None:
            return
        aram = self.CONFIG_KEY == ARAM_PRIORITY_LIST
        rules.setVisible(aram)
        if not (aram and self.config):
            return
        for row, key in (
            (self.row_bench_swap, ARAM_BENCH_SWAP),
            (self.row_auto_reroll, ARAM_AUTO_REROLL),
        ):
            row.blockSignals(True)
            try:
                row.set_checked(bool(self.config.get(key, False)))
            finally:
                row.blockSignals(False)

    def _sync_scraper_mode(self) -> None:
        """Win rates must come from the queue the list is for.

        Switching to ARAM used to leave the scraper on Ranked, so every
        `(xx.x% WR)` beside an ARAM champion — and the winrate sort — used
        Summoner's Rift numbers.
        """
        if not self.scraper:
            return
        try:
            self.scraper.set_mode(
                "ARAM" if self.CONFIG_KEY == ARAM_PRIORITY_LIST else "Ranked"
            )
        except Exception as exc:
            Logger.debug("ChampionListTab", "_sync_scraper_mode suppressed an error", exc=exc)

    def _sync_mode_buttons(self) -> None:
        for key, btn in getattr(self, "_mode_buttons", {}).items():
            btn.setChecked(key == self.CONFIG_KEY)

    def _can_sort(self) -> bool:
        return bool(self.scraper and self.scraper.has_live_winrates())

    def _on_sort_by_winrate(self) -> None:
        ids = self.current_ids()
        if not ids:
            return
        if not (self.scraper and self.scraper.has_live_winrates()):
            # Refuse rather than silently reordering by a constant. The button
            # is disabled for this reason too; this is the belt-and-braces.
            return
        ids.sort(
            key=lambda cid: self.scraper.get_winrate(self._champ_name(cid)) or 0.0,
            reverse=True,
        )
        self._pending_icons = {}
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
        self._pending_icons = {}
        self.list_widget.clear()
        self._save()


class QtPriorityTab(QtChampionListTab):
    """
    Pick priority, for both Summoner's Rift and ARAM (§8).

    These were two navigation entries and two screens. The lists genuinely are
    different — Summoner's Rift priorities are role-aware picks, ARAM
    priorities drive bench sniping — but they are the same interaction, so
    they are one screen with a mode switch. If you only play ARAM you now only
    see one place to configure it.
    """

    CONFIG_KEY = PRIORITY_LIST
    TITLE = "Priority"
    LIST_TITLE = "Pick priority order"
    MODES = (
        (PRIORITY_LIST, "Summoner's Rift"),
        (ARAM_PRIORITY_LIST, "ARAM"),
    )

    def __init__(self, container=None, view_model=None, parent=None):
        super().__init__(container=container, view_model=view_model, parent=parent)
        # Name kept from the first Qt prototype; some callers/tests use it.
        self.prio_list_widget = self.list_widget
        if self.scraper:
            self._sync_scraper_mode()
            self.grid.set_scraper(self.scraper)
            self._renumber_items()

    # Retained for callers written against the earlier implementation.
    def _current_ids(self) -> List[int]:
        return self.current_ids()


class QtAramTab(QtChampionListTab):
    """ARAM champion priorities used by Priority Sniper in ARAM queues."""

    CONFIG_KEY = ARAM_PRIORITY_LIST
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

    CONFIG_KEY = BAN_LIST
    TITLE = "Bans"
    LIST_TITLE = "Ban order"
    EMPTY_TEXT = (
        "No champions in your ban list.\n\n"
        "Pick the champions you most want banned, in order."
    )
    HINT = "Teammate-hovered champions are skipped automatically."
