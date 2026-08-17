"""
PySide6 Priority and Draft Configuration Tab Widget.
Allows visual prioritization and ban ordering with live champion grid selection.
"""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    GOLD_PRIMARY,
    SURFACE_PANEL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.spacing import SPACE_MD, SPACE_SM
from ui.qt.widgets.champion_grid import QtChampionGrid


class QtPriorityTab(QWidget):
    """Champion priority and ban preference configuration tab."""

    def __init__(self, container=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.container = container
        self.config = container.config if container else None
        self.assets = container.assets if container else None

        self._setup_ui()
        self._load_priority_list()

    def _setup_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(SPACE_MD)

        # Left Column: Champion Selection Grid
        left_col = QVBoxLayout()
        left_col.setSpacing(SPACE_SM)

        lbl_grid = QLabel("CHAMPION ROSTER", self)
        lbl_grid.setStyleSheet(f"color: {GOLD_PRIMARY}; font-size: 14px; font-weight: bold;")
        left_col.addWidget(lbl_grid)

        self.grid = QtChampionGrid(asset_manager=self.assets, parent=self)
        self.grid.champion_selected.connect(self._on_champion_clicked)
        left_col.addWidget(self.grid)

        root_layout.addLayout(left_col, stretch=3)

        # Right Column: Configured Priority Order
        right_col = QVBoxLayout()
        right_col.setSpacing(SPACE_SM)

        lbl_prio = QLabel("PICK PRIORITY ORDER", self)
        lbl_prio.setStyleSheet(f"color: {GOLD_PRIMARY}; font-size: 14px; font-weight: bold;")
        right_col.addWidget(lbl_prio)

        self.prio_list_widget = QListWidget(self)
        self.prio_list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {SURFACE_PANEL};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 6px;
                color: {TEXT_PRIMARY};
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 6px;
                border-bottom: 1px solid {BORDER_DEFAULT};
            }}
            QListWidget::item:selected {{
                background-color: #1E282D;
                color: {GOLD_PRIMARY};
            }}
        """)
        right_col.addWidget(self.prio_list_widget)

        # List Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_remove = QPushButton("❌ Remove", self)
        self.btn_remove.clicked.connect(self._on_remove_selected)
        btn_layout.addWidget(self.btn_remove)

        self.btn_clear = QPushButton("🗑️ Clear All", self)
        self.btn_clear.clicked.connect(self._on_clear_all)
        btn_layout.addWidget(self.btn_clear)

        right_col.addLayout(btn_layout)
        root_layout.addLayout(right_col, stretch=2)

    def _load_priority_list(self) -> None:
        if not self.config:
            return
        prio_ids = self.config.get("priority_list", [])
        self.prio_list_widget.clear()
        for cid in prio_ids:
            name = (
                self.assets.get_champ_name(cid)
                if self.assets and hasattr(self.assets, "get_champ_name")
                else str(cid)
            )
            item = QListWidgetItem(f"#{self.prio_list_widget.count() + 1}  {name}")
            item.setData(Qt.UserRole, int(cid))
            self.prio_list_widget.addItem(item)

    def _on_champion_clicked(self, champ_id: int, name: str) -> None:
        """Add clicked champion to priority list if not already present."""
        # Check duplicate
        for idx in range(self.prio_list_widget.count()):
            item = self.prio_list_widget.item(idx)
            if item.data(Qt.UserRole) == champ_id:
                return

        item = QListWidgetItem(f"#{self.prio_list_widget.count() + 1}  {name}")
        item.setData(Qt.UserRole, champ_id)
        self.prio_list_widget.addItem(item)
        self._save_priority_list()

    def _on_remove_selected(self) -> None:
        row = self.prio_list_widget.currentRow()
        if row >= 0:
            self.prio_list_widget.takeItem(row)
            self._renumber_items()
            self._save_priority_list()

    def _on_clear_all(self) -> None:
        self.prio_list_widget.clear()
        self._save_priority_list()

    def _renumber_items(self) -> None:
        for idx in range(self.prio_list_widget.count()):
            item = self.prio_list_widget.item(idx)
            cid = item.data(Qt.UserRole)
            name = (
                self.assets.get_champ_name(cid)
                if self.assets and hasattr(self.assets, "get_champ_name")
                else str(cid)
            )
            item.setText(f"#{idx + 1}  {name}")

    def _save_priority_list(self) -> None:
        if not self.config:
            return
        prio_ids = []
        for idx in range(self.prio_list_widget.count()):
            item = self.prio_list_widget.item(idx)
            prio_ids.append(item.data(Qt.UserRole))
        self.config.set("priority_list", prio_ids)
