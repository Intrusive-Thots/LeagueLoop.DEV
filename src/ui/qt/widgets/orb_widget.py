"""
QtOrbWidget — Compact, Draggable Floating Draft & In-Game Overlay (UI/UX Master Plan §16 & §27).

Provides:
- Ultra-low-profile draggable floating widget
- Live gameflow phase and semantic draft timer
- Recommended champion icon and instant lock-in button
- One-click restore to the full LeagueLoop window shell
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.qt.components.badge import LLBadge
from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.status import LLStatus, Tone
from ui.qt.components.timer import LLTimer
from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    GOLD_LIGHT,
    GOLD_PRIMARY,
    SURFACE_APP_BACKGROUND,
    SURFACE_PANEL_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from ui.qt.theme.radii import RADIUS_MD
from ui.qt.theme.spacing import SPACE_MD, SPACE_SM, SPACE_XS


class QtOrbWidget(QWidget):
    """Minimalist draggable floating overlay for LeagueLoop."""

    restore_requested = Signal()
    lock_in_requested = Signal()

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.view_model = view_model
        self._drag_pos: Optional[QPoint] = None

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(280, 72)

        self._setup_ui()

        if view_model is not None:
            view_model.state_changed.connect(self._render_state)
            self._render_state()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE_PANEL_ELEVATED};
                border: 2px solid {GOLD_PRIMARY};
                border-radius: {RADIUS_MD}px;
            }}
        """)

        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        card_layout.setSpacing(SPACE_SM)

        # Status & Phase Left
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(2)

        self.lbl_phase = QLabel("LeagueLoop Orb", self.card)
        self.lbl_phase.setStyleSheet(f"color: {GOLD_LIGHT}; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        info_col.addWidget(self.lbl_phase)

        self.lbl_rec = QLabel("Idle", self.card)
        self.lbl_rec.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
        info_col.addWidget(self.lbl_rec)

        card_layout.addLayout(info_col, 1)

        # Action Buttons Right
        btn_box = QHBoxLayout()
        btn_box.setSpacing(SPACE_XS)

        self.btn_lock = LLButton("Lock", variant=ButtonVariant.PRIMARY, size=ButtonSize.SM, parent=self.card)
        self.btn_lock.clicked.connect(self.lock_in_requested.emit)
        btn_box.addWidget(self.btn_lock)

        self.btn_restore = QPushButton("⛶", self.card)
        self.btn_restore.setToolTip("Restore full LeagueLoop window")
        self.btn_restore.setCursor(Qt.PointingHandCursor)
        self.btn_restore.setFixedSize(24, 24)
        self.btn_restore.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_MUTED};
                background: transparent;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {GOLD_LIGHT};
                border-color: {GOLD_PRIMARY};
            }}
        """)
        self.btn_restore.clicked.connect(self.restore_requested.emit)
        btn_box.addWidget(self.btn_restore)

        card_layout.addLayout(btn_box)
        root.addWidget(self.card)

    def _render_state(self, *_args) -> None:
        if self.view_model is None:
            return
        state = self.view_model.state
        phase_str = state.client.phase.value if hasattr(state.client.phase, "value") else str(state.client.phase)
        self.lbl_phase.setText(f"● {phase_str}")

        if phase_str == "ChampSelect":
            champ = state.draft.selected_champion_id
            self.lbl_rec.setText(f"Pick ID: {champ}" if champ else "Drafting...")
            self.btn_lock.setEnabled(True)
        else:
            self.lbl_rec.setText("Connected" if state.client.connected else "Offline")
            self.btn_lock.setEnabled(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
