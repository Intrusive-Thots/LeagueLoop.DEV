"""
PySide6 Patch Notes Page Component
Displays current League of Legends patch highlights, champion buffs/nerfs, meta shifts, and LeagueLoop engine updates.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt
from ui.qt.widgets import ScrollableList, make_card, make_button
from core.events import EventBus

class PatchNotesPage(QWidget):
    """Patch notes, champion balancing, and engine update release notes page."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(10)

        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)

        # ── 1. PATCH BANNER CARD ──
        self.banner_card = make_card(title="LEAGUE OF LEGENDS PATCH 14.15 — HIGHLIGHTS")

        self.lbl_patch_ver = QLabel("Current Game Client Patch: v14.15.1", self)
        self.lbl_patch_ver.setStyleSheet("color: #C8AA6E; font-weight: bold; font-size: 13px;")
        self.banner_card.add_widget(self.lbl_patch_ver)

        self.lbl_patch_desc = QLabel(
            "Major balance updates targeting Arena mode synergies, ARAM snowball CD adjustments, and jungle objective timers.",
            self
        )
        self.lbl_patch_desc.setWordWrap(True)
        self.lbl_patch_desc.setStyleSheet("color: #A8B8CC; font-size: 11px;")
        self.banner_card.add_widget(self.lbl_patch_desc)

        self.scroll.add_widget(self.banner_card)

        # ── 2. CHAMPION BALANCE SHIFTS ──
        self.balance_card = make_card(title="META CHAMPION ADJUSTMENTS")

        self.lbl_buffs = QLabel("🟢 BUFFS: Ahri, Jinx, Ornn, Sylas, Hecarim", self)
        self.lbl_buffs.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 11px;")
        self.balance_card.add_widget(self.lbl_buffs)

        self.lbl_nerfs = QLabel("🔴 NERFS: Caitlyn, Brand, Yone, Skarner, Maokai", self)
        self.lbl_nerfs.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 11px;")
        self.balance_card.add_widget(self.lbl_nerfs)

        self.lbl_adjustments = QLabel("🟡 ADJUSTMENTS: Aurelion Sol, Smolder, K'Sante", self)
        self.lbl_adjustments.setStyleSheet("color: #F39C12; font-weight: bold; font-size: 11px;")
        self.balance_card.add_widget(self.lbl_adjustments)

        self.scroll.add_widget(self.balance_card)

        # ── 3. LEAGUELOOP ENGINE RELEASE NOTES ──
        self.engine_card = make_card(title="LEAGUELOOP ENGINE RELEASE NOTES")

        self.lbl_v1 = QLabel("✨ v2.4.0 — PySide6 Frameless Architecture & Real-Time In-Game Objective HUD.", self)
        self.lbl_v1.setStyleSheet("color: #F8F6F0; font-size: 11px; font-weight: bold;")
        self.engine_card.add_widget(self.lbl_v1)

        self.lbl_v2 = QLabel("🛡️ Hardened LCU Transport layer with exponential backoff & instant reconnects.", self)
        self.lbl_v2.setStyleSheet("color: #A8B8CC; font-size: 11px;")
        self.engine_card.add_widget(self.lbl_v2)

        self.scroll.add_widget(self.engine_card)
