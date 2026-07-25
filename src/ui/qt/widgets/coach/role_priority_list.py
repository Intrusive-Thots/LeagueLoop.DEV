from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from PySide6.QtCore import Qt

from ui.qt.widgets import make_button
from ui.qt.pages.champions_page import RoundedIcon, pil_to_pixmap
from services.settings_service import get_settings_service

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


