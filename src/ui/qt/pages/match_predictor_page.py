"""
PySide6 Match Predictor Page Component
Calculates and displays live team composition win probabilities, lane matchup metrics, and late-game scaling predictions.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, Slot
from ui.qt.widgets import ScrollableList, make_card, make_button
from services.league_service import get_league_service
from services.draft_service import get_draft_service
from core.events import EventBus

class MatchPredictorPage(QWidget):
    """Live match prediction and team comp synergy analysis page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.league_service = get_league_service()
        self.draft_service = get_draft_service()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(10)

        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)

        # ── 1. MATCH PREDICTION OVERVIEW CARD ──
        self.overview_card = make_card(title="TEAM COMPOSITION WIN PROBABILITY")

        self.lbl_predict_status = QLabel("Awaiting Champ Select / Active Match...", self)
        self.lbl_predict_status.setStyleSheet("color: #C8AA6E; font-weight: bold; font-size: 13px;")
        self.overview_card.add_widget(self.lbl_predict_status)

        self.row_prob = QWidget(self)
        self.row_prob_layout = QHBoxLayout(self.row_prob)
        self.row_prob_layout.setContentsMargins(0, 6, 0, 6)

        self.lbl_blue_winrate = QLabel("Blue Team: 50.0%", self)
        self.lbl_blue_winrate.setStyleSheet("color: #2080F0; font-size: 12px; font-weight: bold;")
        self.row_prob_layout.addWidget(self.lbl_blue_winrate)

        self.row_prob_layout.addStretch()

        self.lbl_red_winrate = QLabel("Red Team: 50.0%", self)
        self.lbl_red_winrate.setStyleSheet("color: #E74C3C; font-size: 12px; font-weight: bold;")
        self.row_prob_layout.addWidget(self.lbl_red_winrate)

        self.overview_card.add_widget(self.row_prob)

        self.progress_win_ratio = QProgressBar(self)
        self.progress_win_ratio.setFixedHeight(8)
        self.progress_win_ratio.setRange(0, 100)
        self.progress_win_ratio.setValue(50)
        self.progress_win_ratio.setTextVisible(False)
        self.progress_win_ratio.setStyleSheet("""
            QProgressBar {
                background-color: #E74C3C;
                border: 1px solid #1A2B3E;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #2080F0;
                border-radius: 3px;
            }
        """)
        self.overview_card.add_widget(self.progress_win_ratio)
        self.scroll.add_widget(self.overview_card)

        # ── 2. COMPOSITION SYNERGY & POWER CURVE CARD ──
        self.synergy_card = make_card(title="COMPOSITION POWER SPIKES & SCALING")

        self.lbl_early_game = QLabel("⚡ Early Game Spikes: Neutral (50/50)", self)
        self.lbl_early_game.setStyleSheet("color: #F8F6F0; font-size: 11px;")
        self.synergy_card.add_widget(self.lbl_early_game)

        self.lbl_mid_game = QLabel("🛡️ Mid Game Teamfight: Balanced Matchup", self)
        self.lbl_mid_game.setStyleSheet("color: #2ECC71; font-size: 11px;")
        self.synergy_card.add_widget(self.lbl_mid_game)

        self.lbl_late_game = QLabel("🔥 Late Game Scaling: Even Matchup", self)
        self.lbl_late_game.setStyleSheet("color: #A8B8CC; font-size: 11px;")
        self.synergy_card.add_widget(self.lbl_late_game)

        self.scroll.add_widget(self.synergy_card)

        # ── 3. RECOMMENDED WIN CONDITIONS ──
        self.wincon_card = make_card(title="RECOMMENDED WIN CONDITIONS")

        self.lbl_wincon1 = QLabel("🎯 Connect to League Client and enter Champ Select for live match predictions.", self)
        self.lbl_wincon1.setStyleSheet("color: #F8F6F0; font-size: 11px;")
        self.wincon_card.add_widget(self.lbl_wincon1)

        self.lbl_wincon2 = QLabel("⚔️ Win predictions automatically analyze pick synergies and power curves in real time.", self)
        self.lbl_wincon2.setStyleSheet("color: #A8B8CC; font-size: 11px;")
        self.wincon_card.add_widget(self.lbl_wincon2)

        self.scroll.add_widget(self.wincon_card)

        # Event Listeners
        EventBus.on("draft_state_changed", self._on_draft_changed)
        self._refresh()

    def _on_draft_changed(self, session_data):
        self._refresh()

    def _refresh(self):
        pred = self.draft_service.get_match_prediction()
        if not pred.get("active"):
            self.lbl_predict_status.setText("Awaiting Champ Select / Active Match...")
            self.lbl_predict_status.setStyleSheet("color: #C8AA6E; font-weight: bold; font-size: 13px;")
        else:
            self.lbl_predict_status.setText("🟢 LIVE CHAMP SELECT MATCH PREDICTION")
            self.lbl_predict_status.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 13px;")

        blue_pct = pred.get("blue_winrate", 50.0)
        red_pct = pred.get("red_winrate", 50.0)
        self.lbl_blue_winrate.setText(f"Blue Team: {blue_pct}%")
        self.lbl_red_winrate.setText(f"Red Team: {red_pct}%")
        self.progress_win_ratio.setValue(int(blue_pct))

        self.lbl_early_game.setText(pred.get("early_spike", "⚡ Early Game Spikes: Neutral"))
        self.lbl_mid_game.setText(pred.get("mid_spike", "🛡️ Mid Game Teamfight: Balanced"))
        self.lbl_late_game.setText(pred.get("late_spike", "🔥 Late Game Scaling: Even"))

        self.lbl_wincon1.setText(pred.get("wincon_1", ""))
        self.lbl_wincon2.setText(pred.get("wincon_2", ""))
