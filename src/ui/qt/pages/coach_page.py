"""
PySide6 Coach Page Component
Handles draft priority planning, role champion preferences, and live AI synergy/counter draft recommendations.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTabWidget,
    QPushButton, QFrame, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, Slot

from ui.qt.widgets import ScrollableList, make_card, make_button
from ui.qt.theme import get_theme_color
from ui.qt.pages.champions_page import RoundedIcon, pil_to_pixmap
from services.settings_service import get_settings_service
from services.draft_service import get_draft_service
from core.events import EventBus


class RolePriorityListWidget(QWidget):
    """Interactive priority list for a specific lane role (TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY)."""

    def __init__(self, role="MIDDLE", parent=None):
        super().__init__(parent)
        self.role = role
        self.config = get_settings_service()
        self.active_champs = self._load_role_champs()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Search / Add Bar
        add_bar = QWidget(self)
        add_layout = QHBoxLayout(add_bar)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(6)

        self.entry_add = QLineEdit(add_bar)
        self.entry_add.setPlaceholderText(f"Add champion to {role} priority...")
        self.entry_add.returnPressed.connect(self._add_champion)
        add_layout.addWidget(self.entry_add)

        btn_add = make_button(add_bar, text="+ Add", style="secondary", width=60)
        btn_add.clicked.connect(self._add_champion)
        add_layout.addWidget(btn_add)

        layout.addWidget(add_bar)

        # List container
        self.list_container = QWidget(self)
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)

        layout.addWidget(self.list_container)
        self._render_list()

    def _load_role_champs(self):
        profiles = self.config.get("draft_role_profiles", {})
        default_defaults = {
            "TOP": ["Aatrox", "Darius", "Garen"],
            "JUNGLE": ["Lee Sin", "Graves", "Vi"],
            "MIDDLE": ["Ahri", "Syndra", "Zed"],
            "BOTTOM": ["Jinx", "Ezreal", "Kaisa"],
            "UTILITY": ["Thresh", "Nami", "Lulu"]
        }
        return profiles.get(self.role, default_defaults.get(self.role, []))

    def _save_role_champs(self):
        profiles = self.config.get("draft_role_profiles", {})
        profiles[self.role] = self.active_champs
        self.config.set("draft_role_profiles", profiles)

    def _add_champion(self):
        raw = self.entry_add.text().strip()
        if not raw:
            return

        if raw.lower() == "#all":
            from ui.qt.widgets.toast import ToastManager
            all_champs = ["Aatrox", "Ahri", "Akali", "Akshan", "Alistar", "Amumu", "Anivia", "Annie", "Aphelios", "Ashe", "Aurelion Sol", "Azir", "Bard", "BelVeth", "Blitzcrank", "Brand", "Braum", "Briar", "Caitlyn", "Camille", "Cassiopeia", "ChoGath", "Corki", "Darius", "Diana", "Dr. Mundo", "Draven", "Ekko", "Elise", "Evelynn", "Ezreal", "Fiddlesticks", "Fiora", "Fizz", "Galio", "Gangplank", "Garen", "Gnar", "Gragas", "Graves", "Gwen", "Hecarim", "Heimerdinger", "Hwei", "Illaoi", "Irelia", "Ivern", "Janna", "Jarvan IV", "Jax", "Jayce", "Jhin", "Jinx", "KSante", "Kaisa", "Kalista", "Karma", "Karthus", "Kassadin", "Katarina", "Kayle", "Kayn", "Kennen", "KhaZix", "Kindred", "Kled", "KogMaw", "LeBlanc", "Lee Sin", "Leona", "Lillia", "Lissandra", "Lucian", "Lulu", "Lux", "Malphite", "Malzahar", "Maokai", "Master Yi", "Milio", "Miss Fortune", "Mordekaiser", "Morgana", "Naafiri", "Nami", "Nasus", "Nautilus", "Neeko", "Nidalee", "Nilah", "Nocturne", "Nunu & Willump", "Olaf", "Orianna", "Ornn", "Pantheon", "Poppy", "Pyke", "Qiyana", "Quinn", "Rakan", "Rammus", "RekSai", "Rell", "Renata Glasc", "Renekton", "Rengar", "Riven", "Rumble", "Ryze", "Samira", "Sejuani", "Senna", "Seraphine", "Sett", "Shaco", "Shen", "Shyvana", "Singed", "Sion", "Sivir", "Skarner", "Smolder", "Sona", "Soraka", "Swain", "Sylas", "Syndra", "Tahm Kench", "Taliyah", "Talon", "Taric", "Teemo", "Thresh", "Tristana", "Trundle", "Tryndamere", "Twisted Fate", "Twitch", "Udyr", "Urgot", "Varus", "Vayne", "Veigar", "VelKoz", "Vex", "Vi", "Viego", "Viktor", "Vladimir", "Volibear", "Warwick", "Wukong", "Xayah", "Xerath", "Xin Zhao", "Yasuo", "Yone", "Yorick", "Yuumi", "Zac", "Zed", "Zeri", "Ziggs", "Zilean", "Zoe", "Zyra"]
            added_count = 0
            for name in all_champs:
                if name not in self.active_champs:
                    self.active_champs.append(name)
                    added_count += 1
            self._save_role_champs()
            self.entry_add.clear()
            self._render_list()
            toast = ToastManager.get_instance()
            if toast:
                toast.show(f"Added {added_count} champions to {self.role} (#all)", icon="✨", theme="info")
            return

        text = raw.title()
        if text and text not in self.active_champs:
            self.active_champs.append(text)
            self._save_role_champs()
            self.entry_add.clear()
            self._render_list()

    def _remove_champion(self, name):
        if name in self.active_champs:
            self.active_champs.remove(name)
            self._save_role_champs()
            self._render_list()

    def _render_list(self):
        while self.list_layout.count() > 0:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.active_champs:
            lbl_empty = QLabel("No priority champions set for this role.", self)
            lbl_empty.setStyleSheet("color: #6C757D; font-size: 11px; font-style: italic; margin-top: 6px;")
            self.list_layout.addWidget(lbl_empty)
            return

        for idx, name in enumerate(self.active_champs):
            row = QFrame(self)
            row.setFixedHeight(30)
            row.setStyleSheet("""
                QFrame {
                    background-color: #0E1826;
                    border: 1px solid #1B2A3E;
                    border-radius: 4px;
                }
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 0, 8, 0)
            rl.setSpacing(8)

            lbl_num = QLabel(f"#{idx+1}", row)
            lbl_num.setStyleSheet("color: #C8AA6E; font-size: 10px; font-weight: bold;")
            rl.addWidget(lbl_num)

            icon_lbl = RoundedIcon(row, radius=4)
            icon_lbl.setFixedSize(22, 22)
            root = self.window()
            assets = getattr(root, "assets", None)
            if assets and hasattr(assets, "get_champion_icon_pil"):
                try:
                    pil_img = assets.get_champion_icon_pil(name)
                    if pil_img:
                        pix = pil_to_pixmap(pil_img)
                        if not pix.isNull():
                            icon_lbl.setPixmap(pix.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                except Exception:
                    pass
            rl.addWidget(icon_lbl)

            lbl_name = QLabel(name, row)
            lbl_name.setStyleSheet("color: #F0E6D2; font-size: 11px; font-weight: bold;")
            rl.addWidget(lbl_name)

            rl.addStretch()

            btn_del = QPushButton("✕", row)
            btn_del.setFixedSize(18, 18)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #E74C3C;
                    font-size: 11px;
                    border: none;
                }
                QPushButton:hover {
                    color: #FF6B6B;
                }
            """)
            btn_del.clicked.connect(lambda checked=False, n=name: self._remove_champion(n))
            rl.addWidget(btn_del)

            self.list_layout.addWidget(row)


class CoachPage(QWidget):
    """The PySide6 AI Coach Page supporting draft strategy planning and live recommendations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        self.draft_service = get_draft_service()
        self.active_role = "MIDDLE"

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(10)

        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)

        # ── 1. DRAFT PROFILES CARD ──
        self.profiles_card = make_card(title="DRAFT PRIORITY PLANNER")

        self.lbl_info = QLabel("Configure champion priority preferences by role for automated pick/ban selection.", self)
        self.lbl_info.setStyleSheet("color: #A0A5B5; font-size: 11px;")
        self.profiles_card.add_widget(self.lbl_info)

        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet("""
            QTabWidget::panel {
                border: 1px solid #1E2D42;
                background-color: #0A1424;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #080E18;
                color: #A0A5B5;
                padding: 6px 12px;
                border: 1px solid #1E2D42;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #0F1A2A;
                color: #C8AA6E;
                font-weight: bold;
            }
        """)

        self.role_widgets = {}
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        for r in roles:
            w = RolePriorityListWidget(role=r, parent=self.tabs)
            self.tabs.addTab(w, r)
            self.role_widgets[r] = w

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.profiles_card.add_widget(self.tabs)
        self.scroll.add_widget(self.profiles_card)

        # ── 2. LIVE DRAFT ADVISOR CARD ──
        self.advisor_card = make_card(title="LIVE DRAFT ADVISOR")

        # Session Status
        self.lbl_status = QLabel("Draft Advisor standby. Connect to League Client and enter Champ Select for live recommendations.", self)
        self.lbl_status.setStyleSheet("color: #A0A5B5; font-size: 11px; font-style: italic;")
        self.lbl_status.setWordWrap(True)
        self.advisor_card.add_widget(self.lbl_status)

        # Team Comp Breakdown Container
        self.comp_widget = QWidget(self)
        self.comp_layout = QVBoxLayout(self.comp_widget)
        self.comp_layout.setContentsMargins(0, 6, 0, 6)
        self.comp_layout.setSpacing(6)

        self.lbl_comp_title = QLabel("TEAM COMPOSITION BALANCE", self.comp_widget)
        self.lbl_comp_title.setStyleSheet("color: #C8AA6E; font-size: 10px; font-weight: bold;")
        self.comp_layout.addWidget(self.lbl_comp_title)

        # AD / AP Progress Bar
        self.bar_ad_ap = QProgressBar(self.comp_widget)
        self.bar_ad_ap.setFixedHeight(12)
        self.bar_ad_ap.setTextVisible(False)
        self.bar_ad_ap.setStyleSheet("""
            QProgressBar {
                background-color: #3498DB;
                border: 1px solid #1A2B3E;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #E74C3C;
                border-radius: 2px;
            }
        """)
        self.comp_layout.addWidget(self.bar_ad_ap)

        self.lbl_comp_metrics = QLabel("AD: 50%  |  AP: 50%  |  CC Score: 7.5  |  Frontline: 2 Tanks", self.comp_widget)
        self.lbl_comp_metrics.setStyleSheet("color: #F0E6D2; font-size: 11px; font-weight: bold;")
        self.comp_layout.addWidget(self.lbl_comp_metrics)

        self.advisor_card.add_widget(self.comp_widget)

        # Recommendations List Container
        self.recs_widget = QWidget(self)
        self.recs_layout = QVBoxLayout(self.recs_widget)
        self.recs_layout.setContentsMargins(0, 6, 0, 0)
        self.recs_layout.setSpacing(6)
        self.advisor_card.add_widget(self.recs_widget)

        self.scroll.add_widget(self.advisor_card)

        # Event listeners
        EventBus.on("draft_state_changed", self._on_draft_state_changed)
        self._refresh_advisor()

    def _on_tab_changed(self, index):
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        if 0 <= index < len(roles):
            self.active_role = roles[index]
            self._refresh_advisor()

    def _on_draft_state_changed(self, session_data):
        self._refresh_advisor()

    def _refresh_advisor(self):
        session = self.draft_service.get_session()
        in_draft = bool(session and session.get("actions"))

        if not in_draft:
            self.lbl_status.setText("Draft Advisor standby. Active recommendations will render automatically during Champ Select.")
            self.lbl_status.setStyleSheet("color: #A0A5B5; font-size: 11px; font-style: italic;")
        else:
            self.lbl_status.setText("🟢 ACTIVE CHAMP SELECT — Live recommendations computed for " + self.active_role + " role:")
            self.lbl_status.setStyleSheet("color: #2ECC71; font-size: 11px; font-weight: bold;")

        # Update Comp Stats
        comp = self.draft_service.get_team_comp_analysis()
        self.bar_ad_ap.setValue(comp["ad_ratio"])
        self.lbl_comp_metrics.setText(
            f"AD: {comp['ad_ratio']}%  |  AP: {comp['ap_ratio']}%  |  CC Score: {comp['cc_score']}  |  Frontline: {comp['frontline']} Tank(s)"
        )

        # Clear old recommendations
        while self.recs_layout.count() > 0:
            item = self.recs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recs = self.draft_service.get_recommendations(role=self.active_role)
        for r in recs:
            card = QFrame(self.recs_widget)
            card.setFixedHeight(44)
            card.setStyleSheet("""
                QFrame {
                    background-color: #0E1826;
                    border: 1px solid #1E2D42;
                    border-radius: 6px;
                }
                QFrame:hover {
                    border-color: #C8AA6E;
                    background-color: #142236;
                }
            """)
            cl = QHBoxLayout(card)
            cl.setContentsMargins(10, 0, 10, 0)
            cl.setSpacing(8)

            lbl_tier = QLabel(r["tier"], card)
            lbl_tier.setFixedSize(28, 20)
            lbl_tier.setAlignment(Qt.AlignCenter)
            lbl_tier.setStyleSheet("""
                background-color: #C8AA6E;
                color: #080E18;
                font-weight: bold;
                font-size: 10px;
                border-radius: 3px;
            """)
            cl.addWidget(lbl_tier)

            icon_lbl = RoundedIcon(card, radius=4)
            icon_lbl.setFixedSize(26, 26)
            root = self.window()
            assets = getattr(root, "assets", None)
            if assets and hasattr(assets, "get_champion_icon_pil"):
                try:
                    pil_img = assets.get_champion_icon_pil(r["name"])
                    if pil_img:
                        pix = pil_to_pixmap(pil_img)
                        if not pix.isNull():
                            icon_lbl.setPixmap(pix.scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                except Exception:
                    pass
            cl.addWidget(icon_lbl)

            lbl_name = QLabel(r["name"], card)
            lbl_name.setStyleSheet("color: #F0E6D2; font-size: 12px; font-weight: bold;")
            cl.addWidget(lbl_name)

            lbl_win = QLabel(f"Win Rate: {r['win_rate']:.1f}%", card)
            lbl_win.setStyleSheet("color: #A0A5B5; font-size: 10px;")
            cl.addWidget(lbl_win)

            cl.addStretch()

            lbl_counter = QLabel(r["counter_rating"], card)
            lbl_counter.setStyleSheet("color: #2ECC71; font-size: 10px; font-weight: bold;")
            cl.addWidget(lbl_counter)

            btn_select = make_button(card, text="Select", style="secondary", width=50)
            btn_select.clicked.connect(lambda checked=False, name=r["name"]: self._select_champ(name))
            cl.addWidget(btn_select)

            self.recs_layout.addWidget(card)

    def _select_champ(self, name):
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show(f"Selected {name} for Draft Action", icon="🛡️", theme="info")
