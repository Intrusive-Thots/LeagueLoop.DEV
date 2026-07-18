"""
PySide6 AI Coach & Draft Advisor Page Component
Provides draft profile management and live champion select recommendations using Lolalytics win rates.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QTabWidget, QGridLayout, QCompleter, QSizePolicy
)
from PySide6.QtCore import Qt, QMetaObject, Slot, Q_ARG, QStringListModel
from PySide6.QtGui import QColor, QFont

from ui.qt.widgets import ScrollableList, make_card, make_button
from ui.qt.theme import get_theme_color, get_theme_radius, get_theme_spacing
from services.settings_service import get_settings_service
from services.league_service import get_league_service
from services.draft_service import get_draft_service
from services.stats_scraper import get_stats_scraper
from core.events import EventBus
from utils.logger import Logger


class CoachPage(QWidget):
    """Modular AI Coach workspace with draft profile planner and real-time pick/ban recommender."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        self.draft_service = get_draft_service()
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)
        
        # Scrollable area
        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)
        
        # Load known champion names for autocomplete
        self.known_names = []
        self._entries = {}  # { "pick_TOP_1": QLineEdit, ... }
        
        # ── 1. DRAFT PROFILES CARD ──
        self.profiles_card = make_card(self)
        self.profiles_layout = QVBoxLayout(self.profiles_card)
        self.profiles_layout.setSpacing(8)
        
        self.lbl_editor_title = QLabel("DRAFT PRIORITY PLANNER", self)
        self.lbl_editor_title.setStyleSheet("font-weight: bold; color: #C8AA6E; font-size: 11px; margin-bottom: 2px;")
        self.profiles_layout.addWidget(self.lbl_editor_title)
        
        # Tabs for Roles
        self.tabs = QTabWidget(self.profiles_card)
        self.tabs.setStyleSheet("""
            QTabWidget::panel {
                border: 1px solid #1A2332;
                background-color: #141E28;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #0A1428;
                color: #6C757D;
                padding: 4px 10px;
                font-size: 10px;
                font-weight: bold;
                border: 1px solid #1A2332;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #141E28;
                color: #C8AA6E;
                border-bottom: 1px solid #141E28;
            }
            QTabBar::tab:hover {
                color: #F0E6D2;
            }
        """)
        self.profiles_layout.addWidget(self.tabs)
        
        # Build individual tab content
        roles = [("TOP", "Top"), ("JUNGLE", "Jungle"), ("MIDDLE", "Mid"), ("BOTTOM", "Adc"), ("UTILITY", "Support")]
        for key, label in roles:
            tab_widget = QWidget(self.tabs)
            tab_layout = QHBoxLayout(tab_widget)
            tab_layout.setContentsMargins(6, 6, 6, 6)
            tab_layout.setSpacing(10)
            
            # Picks column
            col_picks = QWidget(tab_widget)
            layout_picks = QVBoxLayout(col_picks)
            layout_picks.setContentsMargins(0, 0, 0, 0)
            layout_picks.setSpacing(4)
            
            lbl_picks = QLabel("Priority Picks", col_picks)
            lbl_picks.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 10px;")
            layout_picks.addWidget(lbl_picks)
            
            for i in range(1, 4):
                entry = QLineEdit(col_picks)
                entry.setPlaceholderText(f"Priority Pick {i}")
                entry.setFixedHeight(24)
                entry.setStyleSheet(self._get_entry_style())
                layout_picks.addWidget(entry)
                self._entries[f"pick_{key}_{i}"] = entry
                
            tab_layout.addWidget(col_picks)
            
            # Bans column
            col_bans = QWidget(tab_widget)
            layout_bans = QVBoxLayout(col_bans)
            layout_bans.setContentsMargins(0, 0, 0, 0)
            layout_bans.setSpacing(4)
            
            lbl_bans = QLabel("Priority Bans", col_bans)
            lbl_bans.setStyleSheet("color: #E67E22; font-weight: bold; font-size: 10px;")
            layout_bans.addWidget(lbl_bans)
            
            for i in range(1, 4):
                entry = QLineEdit(col_bans)
                entry.setPlaceholderText(f"Priority Ban {i}")
                entry.setFixedHeight(24)
                entry.setStyleSheet(self._get_entry_style())
                layout_bans.addWidget(entry)
                self._entries[f"ban_{key}_{i}"] = entry
                
            tab_layout.addWidget(col_bans)
            self.tabs.addTab(tab_widget, label)
            
        # Save Button
        self.btn_save = make_button(self.profiles_card, text="Save Draft Profiles", style="primary")
        self.btn_save.clicked.connect(self._save_draft_profiles)
        self.profiles_layout.addWidget(self.btn_save)
        
        self.scroll.add_widget(self.profiles_card)
        
        # ── 2. LIVE DRAFT ADVISOR CARD ──
        self.advisor_card = make_card(self)
        self.advisor_layout = QVBoxLayout(self.advisor_card)
        self.advisor_layout.setSpacing(8)
        
        self.lbl_advisor_title = QLabel("LIVE DRAFT ADVISOR", self)
        self.lbl_advisor_title.setStyleSheet("font-weight: bold; color: #C8AA6E; font-size: 11px; margin-bottom: 2px;")
        self.advisor_layout.addWidget(self.lbl_advisor_title)
        
        # Status Label
        self.lbl_status = QLabel("Draft Advisor is waiting for champion select to start...", self)
        self.lbl_status.setStyleSheet("color: #8A95A5; font-size: 11px; font-style: italic; padding: 4px;")
        self.lbl_status.setWordWrap(True)
        self.advisor_layout.addWidget(self.lbl_status)
        
        # Recommendations Layout (Hidden initially)
        self.rec_widget = QWidget(self.advisor_card)
        self.rec_layout = QVBoxLayout(self.rec_widget)
        self.rec_layout.setContentsMargins(0, 0, 0, 0)
        self.rec_layout.setSpacing(8)
        
        # Picks Recommendations
        self.lbl_rec_picks_title = QLabel("RECOMMENDED PICKS", self.rec_widget)
        self.lbl_rec_picks_title.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 9px;")
        self.rec_layout.addWidget(self.lbl_rec_picks_title)
        
        self.row_picks = QWidget(self.rec_widget)
        self.row_picks_layout = QHBoxLayout(self.row_picks)
        self.row_picks_layout.setContentsMargins(0, 0, 0, 0)
        self.row_picks_layout.setSpacing(4)
        self.rec_layout.addWidget(self.row_picks)
        
        # Bans Recommendations
        self.lbl_rec_bans_title = QLabel("RECOMMENDED BANS", self.rec_widget)
        self.lbl_rec_bans_title.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 9px;")
        self.rec_layout.addWidget(self.lbl_rec_bans_title)
        
        self.row_bans = QWidget(self.rec_widget)
        self.row_bans_layout = QHBoxLayout(self.row_bans)
        self.row_bans_layout.setContentsMargins(0, 0, 0, 0)
        self.row_bans_layout.setSpacing(4)
        self.rec_layout.addWidget(self.row_bans)
        
        self.rec_widget.setVisible(False)
        self.advisor_layout.addWidget(self.rec_widget)
        
        self.scroll.add_widget(self.advisor_card)
        
        # Load configs
        self._load_profiles()
        
        # Event bindings
        EventBus.on("draft_state_changed", self._on_draft_update)
        EventBus.on("league_connected", self._on_connected)
        
        # Load known champion names asynchronously
        QTimer.singleShot(150, self._setup_autocomplete)

    def _get_entry_style(self):
        bg_card = get_theme_color("colors.background.card", "#141E28")
        border = get_theme_color("colors.border.subtle", "#1E2328")
        gold = get_theme_color("colors.accent.gold", "#C8AA6E")
        return f"""
            QLineEdit {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 4px;
                color: #F0E6D2;
                font-size: 10px;
                padding-left: 6px;
                padding-right: 6px;
            }}
            QLineEdit:focus {{
                border: 1px solid {gold};
            }}
        """

    def _setup_autocomplete(self):
        root = self.window()
        assets = getattr(root, "assets", None)
        if assets:
            known = assets.get_known_champions()
            self.known_names = sorted(list(known.values()))
            
            # Setup completer on all input fields
            completer = QCompleter(self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchStartsWith)
            model = QStringListModel(self.known_names, completer)
            completer.setModel(model)
            
            for entry in self._entries.values():
                entry.setCompleter(completer)

    def _load_profiles(self):
        for key, entry in self._entries.items():
            entry.setText(self.config.get(key, ""))

    def _save_draft_profiles(self):
        for key, entry in self._entries.items():
            self.config.set(key, entry.text().strip())
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show("Draft Profiles Saved", icon="🛡️", theme="success")

    def _on_connected(self):
        # Refresh advisor status when client connects
        QMetaObject.invokeMethod(self, "_reset_advisor_status", Qt.QueuedConnection)

    @Slot()
    def _reset_advisor_status(self):
        if not get_league_service().is_connected:
            self.lbl_status.setText("Disconnected from LCU client.")
            self.rec_widget.setVisible(False)
        else:
            self.lbl_status.setText("Draft Advisor is waiting for champion select to start...")
            self.rec_widget.setVisible(False)

    # ── Real-Time Draft Selection Recommendation Engine ──
    def _on_draft_update(self, session):
        # Handle EventBus dispatch
        QMetaObject.invokeMethod(self, "update_live_advice", Qt.QueuedConnection, Q_ARG(dict, session or {}))

    @Slot(dict)
    def update_live_advice(self, session):
        if not session or not get_league_service().is_connected:
            self._reset_advisor_status()
            return
            
        # Get local player's active position role
        local_cell_id = session.get("localPlayerCellId", -1)
        my_team = session.get("myTeam", [])
        me = next((p for p in my_team if p.get("cellId") == local_cell_id), None)
        
        assigned_role = "All"
        if me:
            assigned_role = me.get("assignedPosition", "ALL").upper()
            if assigned_role == "UTILITY":
                assigned_role = "SUPPORT"
        
        # Display active position
        self.lbl_status.setText(f"Assigned Position: {assigned_role}\nAnalyzing draft state for counters and mode synergies...")
        
        # Fetch win rate recommendations from StatsScraper
        scraper = get_stats_scraper()
        
        # Map assigned role string to DDragon tags
        role_tag_map = {
            "TOP": ["Fighter", "Tank"],
            "JUNGLE": ["Fighter", "Assassin"],
            "MIDDLE": ["Mage", "Assassin"],
            "BOTTOM": ["Marksman"],
            "SUPPORT": ["Support", "Tank"]
        }
        target_tags = role_tag_map.get(assigned_role, [])
        
        # Query win rates for all known champions
        root = self.window()
        assets = getattr(root, "assets", None)
        
        # Cache list of banned champion IDs to avoid suggesting them
        banned_ids = self.draft_service.get_banned_champion_ids()
        
        picks_scored = []
        bans_scored = []
        
        if assets:
            for key, info in getattr(assets, "champ_data", {}).items():
                cid = int(info.get("key", 0))
                if cid in banned_ids:
                    continue
                    
                name = info.get("name", "")
                tags = info.get("tags", [])
                
                # Fetch Mode Specific Win Rate
                wr = scraper.get_win_rate(name)
                if wr <= 0:
                    continue
                    
                # Score pick based on win rate and role tag fit
                role_score = 10 if any(t in target_tags for t in tags) else 0
                if assigned_role == "ALL":
                    role_score = 10
                    
                picks_scored.append((name, cid, wr + role_score, wr))
                bans_scored.append((name, cid, wr))
                
        # Sort recommendations
        picks_scored.sort(key=lambda x: x[2], reverse=True)
        bans_scored.sort(key=lambda x: x[2], reverse=True)
        
        # Top 3 Picks & Bans
        top_picks = picks_scored[:3]
        top_bans = bans_scored[:3]
        
        # Re-build pick advice row
        while self.row_picks_layout.count() > 0:
            item = self.row_picks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        for name, cid, score, wr in top_picks:
            btn = QPushButton(f"{name} ({wr:.1f}%)", self.row_picks)
            btn.setFixedHeight(22)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._get_advice_btn_style("picks"))
            # Connect direct hover micro-interaction
            btn.clicked.connect(lambda checked=False, champ_id=cid: self._hover_champion(champ_id))
            self.row_picks_layout.addWidget(btn)
        self.row_picks_layout.addStretch()
            
        # Re-build ban advice row
        while self.row_bans_layout.count() > 0:
            item = self.row_bans_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        for name, cid, wr in top_bans:
            btn = QPushButton(f"{name} ({wr:.1f}%)", self.row_bans)
            btn.setFixedHeight(22)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._get_advice_btn_style("bans"))
            btn.clicked.connect(lambda checked=False, champ_id=cid: self._hover_ban(champ_id))
            self.row_bans_layout.addWidget(btn)
        self.row_bans_layout.addStretch()
            
        self.rec_widget.setVisible(True)

    def _get_advice_btn_style(self, theme):
        border_col = "#2ECC71" if theme == "picks" else "#E74C3C"
        hover_col = "#1E3D2F" if theme == "picks" else "#3D1E1E"
        return f"""
            QPushButton {{
                background-color: #101822;
                border: 1px solid {border_col};
                border-radius: 4px;
                color: #F0E6D2;
                font-size: 9px;
                font-weight: bold;
                padding-left: 6px;
                padding-right: 6px;
            }}
            QPushButton:hover {{
                background-color: {hover_col};
            }}
        """

    def _hover_champion(self, champ_id):
        # Click to hover/select champion directly in client
        self.draft_service.select_champion(champ_id, action_type="pick", lock_in=False)
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show("Hovering recommended pick...", icon="🎯", theme="success")

    def _hover_ban(self, champ_id):
        # Click to hover ban directly in client
        self.draft_service.select_champion(champ_id, action_type="ban", lock_in=False)
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show("Hovering recommended ban...", icon="🚫", theme="error")
