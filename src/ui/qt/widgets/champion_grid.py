"""
PySide6 Champion Grid Widget.
Renders filterable, searchable champion tiles with Riot Hextech styling and selection signals.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.qt.theme.colors import (
    BORDER_ACTIVE,
    BORDER_DEFAULT,
    GOLD_LIGHT,
    GOLD_PRIMARY,
    SURFACE_APP_BACKGROUND,
    SURFACE_PANEL,
    SURFACE_PANEL_HOVER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.spacing import SPACE_MD, SPACE_SM, SPACE_XS


class QtChampionTile(QFrame):
    """Single champion selection tile."""

    clicked = Signal(int, str)

    def __init__(self, champ_id: int, name: str, key: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.champ_id = champ_id
        self.champ_name = name
        self.champ_key = key
        self.is_selected = False

        self.setFixedSize(76, 88)
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()
        self._update_style()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        # Champion Icon / Placeholder
        self.icon_box = QLabel(self)
        self.icon_box.setFixedSize(52, 52)
        self.icon_box.setAlignment(Qt.AlignCenter)
        self.icon_box.setText(self.champ_name[:2].upper())
        self.icon_box.setStyleSheet(f"""
            QLabel {{
                background-color: {SURFACE_APP_BACKGROUND};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 4px;
                color: {GOLD_PRIMARY};
                font-weight: bold;
                font-size: 14px;
            }}
        """)
        layout.addWidget(self.icon_box)

        # Champion Name
        self.name_label = QLabel(self.champ_name, self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 10px; font-weight: 500;")
        layout.addWidget(self.name_label)

    def _update_style(self) -> None:
        if self.is_selected:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {SURFACE_PANEL_HOVER};
                    border: 2px solid {BORDER_ACTIVE};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {SURFACE_PANEL};
                    border: 1px solid {BORDER_DEFAULT};
                    border-radius: 6px;
                }}
                QFrame:hover {{
                    background-color: {SURFACE_PANEL_HOVER};
                    border: 1px solid {BORDER_ACTIVE};
                }}
            """)

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected
        self._update_style()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.champ_id, self.champ_name)


class QtChampionGrid(QWidget):
    """
    Searchable, role-filterable Champion Grid with responsive tile placement.
    """

    champion_selected = Signal(int, str)

    ROLES = [("ALL", "All"), ("TOP", "Top"), ("JUNGLE", "Jungle"), ("MIDDLE", "Mid"), ("BOTTOM", "Bot"), ("UTILITY", "Support")]

    def __init__(self, asset_manager=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.assets = asset_manager
        self.current_role = "ALL"
        self.search_query = ""
        self.tiles: Dict[int, QtChampionTile] = {}
        self.selected_champ_id: Optional[int] = None

        self._setup_ui()
        self.load_champions()

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(SPACE_SM)

        # Filter Bar: Role Buttons + Search Bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(SPACE_SM)

        # Role Buttons
        self.role_btn_group = QButtonGroup(self)
        self.role_btn_group.setExclusive(True)

        for role_key, role_label in self.ROLES:
            btn = QPushButton(role_label, self)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            if role_key == "ALL":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, r=role_key: self._on_role_selected(r))
            self.role_btn_group.addButton(btn)
            filter_bar.addWidget(btn)

        filter_bar.addStretch()

        # Search Bar
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("🔍 Search champions...")
        self.search_input.setFixedWidth(180)
        self.search_input.setFixedHeight(28)
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_bar.addWidget(self.search_input)

        root_layout.addLayout(filter_bar)

        # Scroll Area for Grid
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 6px;
            }}
        """)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(SPACE_SM, SPACE_SM, SPACE_SM, SPACE_SM)
        self.grid_layout.setSpacing(SPACE_SM)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll_area.setWidget(self.grid_container)
        root_layout.addWidget(self.scroll_area)

    def load_champions(self) -> None:
        """Populate champion tiles from AssetManager or built-in fallback."""
        self.tiles.clear()
        # Clear existing widgets from layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        champs_list = []
        if self.assets and hasattr(self.assets, "champ_data") and self.assets.champ_data:
            for key, info in self.assets.champ_data.items():
                try:
                    cid = int(info.get("key", 0))
                    name = info.get("name", key)
                    if cid > 0:
                        champs_list.append((cid, name, key))
                except (ValueError, TypeError):
                    continue
        else:
            # Baseline popular champions fallback
            champs_list = [
                (103, "Ahri", "Ahri"),
                (266, "Aatrox", "Aatrox"),
                (1, "Annie", "Annie"),
                (222, "Jinx", "Jinx"),
                (81, "Ezreal", "Ezreal"),
                (67, "Vayne", "Vayne"),
                (86, "Garen", "Garen"),
                (64, "Lee Sin", "LeeSin"),
                (157, "Yasuo", "Yasuo"),
                (777, "Yone", "Yone"),
                (412, "Thresh", "Thresh"),
                (89, "Leona", "Leona"),
            ]

        # Sort alphabetically
        champs_list.sort(key=lambda x: x[1])

        cols = 6
        for idx, (cid, name, key) in enumerate(champs_list):
            tile = QtChampionTile(cid, name, key, self.grid_container)
            tile.clicked.connect(self._on_tile_clicked)
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(tile, row, col)
            self.tiles[cid] = tile

    def _on_tile_clicked(self, champ_id: int, name: str) -> None:
        if self.selected_champ_id and self.selected_champ_id in self.tiles:
            self.tiles[self.selected_champ_id].set_selected(False)

        self.selected_champ_id = champ_id
        if champ_id in self.tiles:
            self.tiles[champ_id].set_selected(True)

        self.champion_selected.emit(champ_id, name)

    def _on_role_selected(self, role: str) -> None:
        self.current_role = role
        self._filter_tiles()

    def _on_search_changed(self, text: str) -> None:
        self.search_query = text.strip().lower()
        self._filter_tiles()

    def _filter_tiles(self) -> None:
        """Filter visible tiles based on role and search query."""
        for cid, tile in self.tiles.items():
            matches_search = (
                not self.search_query
                or self.search_query in tile.champ_name.lower()
                or self.search_query in tile.champ_key.lower()
            )
            matches_role = True
            if self.current_role != "ALL" and self.assets and hasattr(self.assets, "get_champ_roles"):
                roles = self.assets.get_champ_roles(cid)
                matches_role = self.current_role.upper() in [r.upper() for r in roles] if roles else True

            tile.setVisible(matches_search and matches_role)
