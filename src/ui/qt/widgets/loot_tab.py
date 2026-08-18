"""
Loot Tab — Bulk Hextech Chest & Capsule Opener (UI/UX Master Plan §10).

Provides:
- Inventory list of chests, capsules, orbs, and loot containers
- Key forge automation (convert fragments into whole keys)
- One-click bulk open execution with real-time status and logs
- Safe, non-blocking LCU operations via LootService
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.loot_service import LootItem, LootService
from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSection, LLSeparator
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    BLUE_ACCENT,
    COLOR_DANGER,
    GOLD_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    SURFACE_PANEL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.radii import RADIUS_MD
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import TEXT_BODY, TEXT_CAPTION, TEXT_PAGE_TITLE


class QtLootTab(QWidget):
    """Hextech Loot management and bulk container opener tab."""

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.lcu = getattr(container, "lcu", None) if container else None
        self.loot_service: Optional[LootService] = None

        self._is_busy = False
        self._items: List[LootItem] = []
        self._setup_ui()

        if self.lcu is not None:
            self.loot_service = LootService(self.lcu, log=self._on_log)
            # Fetch loot once initialized
            QTimer.singleShot(200, self.refresh_inventory)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        # Header Title and Actions
        header = QHBoxLayout()
        title = QLabel("Hextech Loot & Inventory", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        header.addWidget(title)
        header.addStretch(1)

        self.btn_refresh = LLButton("Refresh", variant=ButtonVariant.SECONDARY, parent=self)
        self.btn_refresh.clicked.connect(self.refresh_inventory)
        header.addWidget(self.btn_refresh)

        self.btn_forge_keys = LLButton("Forge Keys", variant=ButtonVariant.SECONDARY, parent=self)
        self.btn_forge_keys.clicked.connect(self._on_forge_keys)
        header.addWidget(self.btn_forge_keys)

        self.btn_open_all = LLButton("Open All Available", variant=ButtonVariant.PRIMARY, size=ButtonSize.MD, parent=self)
        self.btn_open_all.clicked.connect(self._on_open_all)
        header.addWidget(self.btn_open_all)

        root.addLayout(header)

        # Overview / Status Card
        status_card = LLCard(parent=self)
        status_layout = QHBoxLayout()
        status_layout.setSpacing(SPACE_MD)

        self.status_readout = LLStatus("Ready", Tone.NEUTRAL, "Ready to inspect loot inventory", parent=status_card)
        status_layout.addWidget(self.status_readout)
        status_layout.addStretch(1)

        self.chk_auto_forge = QCheckBox("Forge keys from fragments first", status_card)
        self.chk_auto_forge.setChecked(True)
        status_layout.addWidget(self.chk_auto_forge)

        status_card.add_layout(status_layout)

        # Progress bar (hidden unless crafting)
        self.progress_bar = QProgressBar(status_card)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        status_card.add_widget(self.progress_bar)

        root.addWidget(status_card)

        # Inventory Table Section
        table_section = LLSection("Openable Loot Containers", parent=self)
        self.table = QTableWidget(table_section)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Item Name", "Type", "Quantity", "Key Required", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {SURFACE_PANEL};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD}px;
                color: {TEXT_PRIMARY};
                gridline-color: {BORDER_DEFAULT};
            }}
            QHeaderView::section {{
                background-color: #0A1428;
                color: {GOLD_PRIMARY};
                font-weight: bold;
                border: 1px solid {BORDER_DEFAULT};
                padding: 6px;
            }}
        """)
        table_section.add_widget(self.table, 1)
        root.addWidget(table_section, 1)

        # Status Log Footer
        self.lbl_log = QLabel("", self)
        self.lbl_log.setStyleSheet(TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;")
        root.addWidget(self.lbl_log)

    def _on_log(self, msg: str) -> None:
        self.lbl_log.setText(f"[Loot] {msg}")

    def refresh_inventory(self) -> None:
        """Fetch loot inventory from LCU asynchronously."""
        if not self.loot_service or self._is_busy:
            return

        self.status_readout.set_status("Scanning", Tone.WARNING, "Fetching loot inventory from LCU...")
        self.btn_refresh.setEnabled(False)

        def worker():
            try:
                items = self.loot_service.fetch_loot()
                plans = self.loot_service.plan_opens(items)
                openable_map = {p.loot_id: p for p in plans}
            except Exception as e:
                items, openable_map = [], {}
            QTimer.singleShot(0, lambda: self._update_table_ui(items, openable_map))

        threading.Thread(target=worker, daemon=True).start()

    def _update_table_ui(self, items: List[LootItem], openable_map: Dict[str, Any]) -> None:
        self._items = items
        self.btn_refresh.setEnabled(True)
        self.table.setRowCount(0)

        openables = [it for it in items if it.count > 0 and (it.loot_id in openable_map or "CHEST" in it.loot_id or "CAPSULE" in it.loot_id or "ORB" in it.loot_id or "KEY" in it.loot_id)]
        self.table.setRowCount(len(openables))

        for row, item in enumerate(openables):
            plan = openable_map.get(item.loot_id)
            needs_key = plan.needs_key if plan else False
            can_open = plan.times > 0 if plan else False

            name_item = QTableWidgetItem(item.name or item.loot_id)
            type_item = QTableWidgetItem(item.type)
            qty_item = QTableWidgetItem(str(item.count))
            key_item = QTableWidgetItem("Yes" if needs_key else "No")

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, type_item)
            self.table.setItem(row, 2, qty_item)
            self.table.setItem(row, 3, key_item)

            btn_open = QPushButton("Open" if can_open else "Inspect")
            btn_open.setEnabled(can_open)
            btn_open.clicked.connect(lambda _, it=item: self._on_open_single(it))
            self.table.setCellWidget(row, 4, btn_open)

        total_openable = sum(p.times for p in openable_map.values())
        self.status_readout.set_status(
            "Ready",
            Tone.SUCCESS if total_openable > 0 else Tone.NEUTRAL,
            f"{len(openables)} items found ({total_openable} containers ready to open)",
        )

    def _on_forge_keys(self) -> None:
        if not self.loot_service or self._is_busy:
            return
        self._is_busy = True
        self.status_readout.set_status("Forging", Tone.WARNING, "Forging keys from fragments...")

        def worker():
            try:
                forged = self.loot_service.forge_keys_if_needed()
                msg = f"Forged {forged} keys." if forged > 0 else "No key fragments ready to forge."
            except Exception as e:
                msg = f"Error forging keys: {e}"
            QTimer.singleShot(0, lambda: self._on_finish_op(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_open_single(self, item: LootItem) -> None:
        if not self.loot_service or self._is_busy:
            return
        self._is_busy = True
        self.status_readout.set_status("Opening", Tone.WARNING, f"Opening {item.name}...")

        def worker():
            try:
                plans = self.loot_service.plan_opens([item])
                total = 0
                for plan in plans:
                    if plan.times > 0:
                        total += self.loot_service.execute_plan(plan, max_times=1)
                msg = f"Opened 1 {item.name}." if total > 0 else f"Could not open {item.name}."
            except Exception as e:
                msg = f"Error opening: {e}"
            QTimer.singleShot(0, lambda: self._on_finish_op(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_open_all(self) -> None:
        if not self.loot_service or self._is_busy:
            return
        self._is_busy = True
        self.status_readout.set_status("Bulk Opening", Tone.WARNING, "Opening all available containers...")
        self.progress_bar.show()
        self.progress_bar.setValue(10)

        def worker():
            try:
                if self.chk_auto_forge.isChecked():
                    self.loot_service.forge_keys_if_needed()
                opened = self.loot_service.open_all(forge_keys=self.chk_auto_forge.isChecked())
                msg = f"Successfully opened {opened} containers."
            except Exception as e:
                msg = f"Error during bulk opening: {e}"
            QTimer.singleShot(0, lambda: self._on_finish_op(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_finish_op(self, msg: str) -> None:
        self._is_busy = False
        self.progress_bar.setValue(100)
        QTimer.singleShot(1000, self.progress_bar.hide)
        self.lbl_log.setText(msg)
        self.refresh_inventory()
