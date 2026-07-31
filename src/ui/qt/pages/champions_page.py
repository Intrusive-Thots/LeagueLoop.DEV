"""
PySide6 Champions Page Component
Manages the champion priority grid (ARAM list), fuzzy search, drag reordering,
import/export, filtering by roles, sorting by mastery/A-Z, and rich hover stats cards.
"""
import math
import string
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QMenu, QGraphicsOpacityEffect,
    QGridLayout, QScrollArea, QFileDialog, QApplication
)
from PySide6.QtCore import Qt, QTimer, Property, QPropertyAnimation, QEasingCurve, Slot, QPoint, QMimeData
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap, QImage, QDrag, QCursor

from ui.qt.widgets import ScrollableList, make_button
from ui.qt.theme import get_theme_color, get_theme_radius, get_theme_spacing
from ui.qt.viewmodels.champions_viewmodel import ChampionsViewModel
from utils.logger import Logger

# Standard size tokens
ICON_SIZE = 48
CELL_SIZE = 72
_CLEAN_TRANS = str.maketrans("", "", " '.")


def pil_to_pixmap(pil_img):
    """Converts a PIL Image to QPixmap safely."""
    try:
        if pil_img.mode == "RGBA":
            qim = QImage(
                pil_img.tobytes("raw", "RGBA"),
                pil_img.width,
                pil_img.height,
                QImage.Format_RGBA8888
            )
        else:
            rgba_img = pil_img.convert("RGBA")
            qim = QImage(
                rgba_img.tobytes("raw", "RGBA"),
                rgba_img.width,
                rgba_img.height,
                QImage.Format_RGBA8888
            )
        return QPixmap.fromImage(qim)
    except Exception as e:
        Logger.error("ChampionsPage", f"Error converting PIL image: {e}")
        return QPixmap()


class RoundedIcon(QLabel):
    """Rounded champion avatar label."""

    def __init__(self, parent=None, radius=8):
        super().__init__(parent)
        self.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.radius = radius
        self.pixmap_val = None

    def set_pixmap(self, pixmap):
        self.pixmap_val = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.pixmap_val and not self.pixmap_val.isNull():
            path = QPainterPath()
            path.addRoundedRect(0, 0, self.width(), self.height(), self.radius, self.radius)
            painter.setClipPath(path)
            painter.drawPixmap(self.rect(), self.pixmap_val)
        else:
            # Fallback gold outline panel
            painter.setBrush(QBrush(QColor("#141E28")))
            painter.setPen(QPen(QColor(get_theme_color("colors.border.subtle", "#1E2328")), 1))
            painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, self.radius, self.radius)


class ChampionCellWidget(QFrame):
    """A single champion cell inside the priority grid with overlays and hover listeners."""

    def __init__(self, parent_page, parent_widget=None, champ_name="", index=-1, assets=None, on_click=None, on_drag_start=None):
        super().__init__(parent_widget)
        self.parent_page = parent_page
        self.champ_name = champ_name
        self.index = index
        self.on_click = on_click
        self.on_drag_start = on_drag_start
        self.selected = False

        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setCursor(Qt.PointingHandCursor)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        self.icon = RoundedIcon(self, radius=6)
        layout.addWidget(self.icon)

        # Async Icon Loading
        if assets:
            def _on_icon_loaded(img):
                if img and hasattr(img, "_image"):
                    pix = pil_to_pixmap(img._image)
                    self.icon.set_pixmap(pix)
            assets.get_icon_async("champion", champ_name, _on_icon_loaded, size=(ICON_SIZE, ICON_SIZE))

        # Tooltip fallback
        self.setToolTip(f"{champ_name} (Priority #{index + 1})")

        # Border styles
        self._border_subtle = get_theme_color("colors.border.subtle", "#1E2328")
        self._gold = get_theme_color("colors.accent.gold", "#C8AA6E")

        # Overlay Favorite Star Button
        self.btn_fav = QPushButton(self)
        self.btn_fav.setFixedSize(14, 14)
        self.btn_fav.setCursor(Qt.PointingHandCursor)
        self.btn_fav.clicked.connect(self._on_fav_clicked)
        self.btn_fav.move(CELL_SIZE - 18, 4)
        self.btn_fav.setStyleSheet("background: transparent; border: none; font-size: 11px; font-weight: bold;")
        self.btn_fav.raise_()

        # Update styling based on configuration
        self.update_style()
        self._wiggle_angle = 0.0

    def _on_fav_clicked(self):
        # Toggle favorite status in page config
        self.parent_page.toggle_favorite(self.champ_name)
        self.update_style()

    def set_selected(self, selected):
        self.selected = selected
        self.update_style()

    def update_style(self):
        # Check if favorited
        is_fav = self.parent_page.is_favorite(self.champ_name)
        self.btn_fav.setText("★" if is_fav else "☆")
        self.btn_fav.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {"#C8AA6E" if is_fav else "#6C757D"};
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: #F0E6D2;
            }}
        """)

        if self.selected:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {get_theme_color("colors.background.card", "#141E28")};
                    border: 2px solid {self._gold};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                }}
                QFrame:hover {{
                    background-color: {get_theme_color("colors.state.hover", "#1C2630")};
                    border: 1px solid {self._border_subtle};
                }}
            """)

    # ── Hover Enter/Leave for Preview Overlay Card ──
    def enterEvent(self, event):
        pos = self.mapToGlobal(QPoint(self.width() + 4, 0))
        self.parent_page.show_hover_card(self.champ_name, pos)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.parent_page.hide_hover_card()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            if self.on_click:
                self.on_click(self.index)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            # Check if grid reordering is locked due to active filters
            page = self.parent_page
            if page.selected_role != "All" or page.selected_sort != "Priority" or page.btn_favs_only.isChecked():
                return

            if (event.position().toPoint() - self._drag_start_pos).manhattanLength() >= 10:
                if self.on_drag_start:
                    self.on_drag_start(self.index, self)
        super().mouseMoveEvent(event)


class ChampionHoverCard(QFrame):
    """Popup tooltip overlay detailing stats, roles, and masteries."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hoverCard")
        self.setFixedSize(140, 110)

        border = get_theme_color("colors.accent.gold", "#C8AA6E")
        self.setStyleSheet(f"""
            QFrame#hoverCard {{
                background-color: #0A1428;
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        self.lbl_name = QLabel("Name", self)
        self.lbl_name.setStyleSheet("color: #F0E6D2; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl_name)

        self.lbl_roles = QLabel("Roles: --", self)
        self.lbl_roles.setStyleSheet("color: #8A95A5; font-size: 9px;")
        layout.addWidget(self.lbl_roles)

        self.lbl_mastery = QLabel("Mastery: --", self)
        self.lbl_mastery.setStyleSheet("color: #C8AA6E; font-size: 9px;")
        layout.addWidget(self.lbl_mastery)

        self.lbl_points = QLabel("Points: --", self)
        self.lbl_points.setStyleSheet("color: #8A95A5; font-size: 8px;")
        layout.addWidget(self.lbl_points)

        self.lbl_winrate = QLabel("Win Rate: --", self)
        self.lbl_winrate.setStyleSheet("color: #8A95A5; font-size: 9px; font-weight: bold;")
        layout.addWidget(self.lbl_winrate)

        self.setVisible(False)


class ChampionsPage(QWidget):
    """The PySide6 Champions Editor Page using ChampionsViewModel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewmodel = ChampionsViewModel(self)
        self.config = self.viewmodel.config
        self.undo_stack = []
        self._row_widgets = []

        # State
        self._all_champions = []
        self._selected_indices = set()
        self._edit_mode = False
        self._wiggle_state = 0.0

        # Load known champions asynchronously
        self._known_champions = {}
        self._search_cache = []
        self.mastery_cache = {}

        # Filters state
        self.selected_role = "All"
        self.selected_sort = "Priority"

        from ui.qt.widgets.components import SectionHeader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Un-nested section header for clean Version One visual hierarchy
        self.header = SectionHeader("Champion Priority Grid", "Snipe high priority bench & pick champions")
        layout.addWidget(self.header)

        self.card = QWidget(self)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(10)
        layout.addWidget(self.card, stretch=1)

        # ── 1. TOOLBAR ──
        toolbar = QWidget(self.card)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)

        # Edit Toggle Button
        self.btn_edit = QPushButton("Edit", toolbar)
        self.btn_edit.setFixedSize(50, 24)
        self.btn_edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {get_theme_color("colors.border.subtle", "#1E2328")};
                border-radius: 4px;
                color: {get_theme_color("colors.accent.primary", "#C8AA6E")};
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {get_theme_color("colors.state.hover")};
            }}
        """)
        self.btn_edit.clicked.connect(self._toggle_edit_mode)
        toolbar_layout.addWidget(self.btn_edit)

        # Quick Search Input
        self.entry_add = QLineEdit(toolbar)
        self.entry_add.setPlaceholderText("Add champion...")
        self.entry_add.setFixedHeight(24)
        self.entry_add.setMinimumWidth(80)
        bg_card = get_theme_color("colors.background.card", "#141E28")
        border = get_theme_color("colors.border.subtle", "#1E2328")
        gold = get_theme_color("colors.accent.gold", "#C8AA6E")
        self.entry_add.setStyleSheet(f"""
            QLineEdit {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 4px;
                color: #F0E6D2;
                font-size: 11px;
                padding-left: 6px;
                padding-right: 6px;
            }}
            QLineEdit:focus {{
                border: 1px solid {gold};
            }}
        """)
        self.entry_add.textChanged.connect(self._on_search_typing)
        self.entry_add.returnPressed.connect(self._commit_search_add)
        toolbar_layout.addWidget(self.entry_add)

        # Undo Button
        self.btn_undo = QPushButton("↩", toolbar)
        self.btn_undo.setFixedSize(24, 24)
        self.btn_undo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_undo.setCursor(Qt.PointingHandCursor)
        self.btn_undo.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {border};
                border-radius: 4px;
                color: {get_theme_color("colors.text.primary")};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {get_theme_color("colors.state.hover")};
            }}
        """)
        self.btn_undo.clicked.connect(self._undo_action)
        self.btn_undo.setToolTip("Undo Last Action")
        toolbar_layout.addWidget(self.btn_undo)

        # Export Button
        self.btn_export = QPushButton("⎘", toolbar)
        self.btn_export.setFixedSize(24, 24)
        self.btn_export.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {border};
                border-radius: 4px;
                color: {get_theme_color("colors.text.muted")};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {get_theme_color("colors.state.hover")};
            }}
        """)
        self.btn_export.clicked.connect(self._export_list)
        self.btn_export.setToolTip("Export List to Clipboard")
        toolbar_layout.addWidget(self.btn_export)

        # Import Button
        self.btn_import = QPushButton("📥", toolbar)
        self.btn_import.setFixedSize(24, 24)
        self.btn_import.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {border};
                border-radius: 4px;
                color: {get_theme_color("colors.text.muted")};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {get_theme_color("colors.state.hover")};
            }}
        """)
        self.btn_import.clicked.connect(self._import_list)
        self.btn_import.setToolTip("Import List from Clipboard")
        toolbar_layout.addWidget(self.btn_import)

        card_layout.addWidget(toolbar)

        # ── 2. FILTER BAR ──
        self.filter_bar = QWidget(self.card)
        self.filter_bar_layout = QVBoxLayout(self.filter_bar)
        self.filter_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_bar_layout.setSpacing(6)

        # Role Buttons Scroll Container
        self.scroll_roles = QScrollArea(self.filter_bar)
        self.scroll_roles.setWidgetResizable(True)
        self.scroll_roles.setFixedHeight(28)
        self.scroll_roles.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_roles.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_roles.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.roles_widget = QWidget(self.scroll_roles)
        self.roles_widget.setStyleSheet("background: transparent;")
        self.roles_layout = QHBoxLayout(self.roles_widget)
        self.roles_layout.setContentsMargins(0, 0, 0, 0)
        self.roles_layout.setSpacing(4)

        self.role_buttons = {}
        roles = ["All", "Fighter", "Mage", "Assassin", "Support", "Marksman", "Tank"]
        for r in roles:
            btn = QPushButton(r, self.roles_widget)
            btn.setFixedHeight(24)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            if r == "All":
                btn.setChecked(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._get_role_btn_qss(r == "All"))
            btn.clicked.connect(lambda checked=False, role=r: self._on_role_selected(role))
            self.roles_layout.addWidget(btn)
            self.role_buttons[r] = btn

        self.roles_layout.addStretch()
        self.scroll_roles.setWidget(self.roles_widget)
        self.filter_bar_layout.addWidget(self.scroll_roles)

        # Sort Selector Row Scroll Container
        self.scroll_sorts = QScrollArea(self.filter_bar)
        self.scroll_sorts.setWidgetResizable(True)
        self.scroll_sorts.setFixedHeight(26)
        self.scroll_sorts.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_sorts.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_sorts.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.sort_widget = QWidget(self.scroll_sorts)
        self.sort_widget.setStyleSheet("background: transparent;")
        self.sort_layout = QHBoxLayout(self.sort_widget)
        self.sort_layout.setContentsMargins(0, 0, 0, 0)
        self.sort_layout.setSpacing(4)

        lbl_sort = QLabel("Sort:", self.sort_widget)
        lbl_sort.setStyleSheet("color: #A0A5B5; font-size: 10px; font-weight: bold; background: transparent;")
        self.sort_layout.addWidget(lbl_sort)

        self.sort_buttons = {}
        sorts = [("Priority", "Priority"), ("A-Z", "Alphabetical"), ("Mastery", "Mastery"), ("Favs", "Favorites")]
        for name, code in sorts:
            btn = QPushButton(name, self.sort_widget)
            btn.setFixedHeight(22)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            if name == "Priority":
                btn.setChecked(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._get_sort_btn_qss(name == "Priority"))
            btn.clicked.connect(lambda checked=False, s=name: self._on_sort_selected(s))
            self.sort_layout.addWidget(btn)
            self.sort_buttons[name] = btn

        self.sort_layout.addStretch()

        # Favorites Toggle
        self.btn_favs_only = QPushButton("★ Favorites", self.sort_widget)
        self.btn_favs_only.setFixedHeight(22)
        self.btn_favs_only.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_favs_only.setCheckable(True)
        self.btn_favs_only.setCursor(Qt.PointingHandCursor)
        self.btn_favs_only.setStyleSheet(self._get_favs_btn_qss(False))
        self.btn_favs_only.clicked.connect(self._on_favs_only_toggled)
        self.sort_layout.addWidget(self.btn_favs_only)

        self.scroll_sorts.setWidget(self.sort_widget)
        self.filter_bar_layout.addWidget(self.scroll_sorts)
        card_layout.addWidget(self.filter_bar)

        # --- Suggestions Row ---
        self.suggestions_widget = QWidget(self.card)
        self.suggestions_layout = QHBoxLayout(self.suggestions_widget)
        self.suggestions_layout.setContentsMargins(0, 0, 0, 0)
        self.suggestions_layout.setSpacing(4)
        self.suggestions_widget.setVisible(False)
        card_layout.addWidget(self.suggestions_widget)

        # --- Edit Mode Bar (Hidden by default) ---
        self.edit_bar = QWidget(self.card)
        self.edit_bar_layout = QHBoxLayout(self.edit_bar)
        self.edit_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_bar_layout.setSpacing(6)
        self.edit_bar.setVisible(False)

        self.btn_delete = QPushButton("Delete Selected", self.edit_bar)
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setFixedHeight(24)
        self.btn_delete.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {get_theme_color("colors.state.danger", "#E74C3C")};
                border-radius: 4px;
                color: {get_theme_color("colors.state.danger", "#E74C3C")};
                font-weight: bold;
                font-size: 11px;
                padding-left: 8px;
                padding-right: 8px;
            }}
            QPushButton:hover {{
                background-color: #4d1111;
            }}
        """)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.edit_bar_layout.addWidget(self.btn_delete)

        self.btn_clear_all = QPushButton("Clear All", self.edit_bar)
        self.btn_clear_all.setCursor(Qt.PointingHandCursor)
        self.btn_clear_all.setFixedHeight(24)
        self.btn_clear_all.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {get_theme_color("colors.state.danger", "#E74C3C")};
                border-radius: 4px;
                color: {get_theme_color("colors.state.danger", "#E74C3C")};
                font-weight: bold;
                font-size: 11px;
                padding-left: 8px;
                padding-right: 8px;
            }}
            QPushButton:hover {{
                background-color: #4d1111;
            }}
        """)
        self.btn_clear_all.clicked.connect(self._clear_all)
        self.edit_bar_layout.addWidget(self.btn_clear_all)

        self.edit_bar_layout.addStretch()
        card_layout.addWidget(self.edit_bar)

        # --- Grid Scroll Area ---
        self.scroll = QScrollArea(self.card)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        self.grid_container = QWidget(self.scroll)
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll.setWidget(self.grid_container)
        card_layout.addWidget(self.scroll)

        # Rich Hover Stats Preview Overlay
        self.hover_card = ChampionHoverCard(self)

        # Wiggle timer for iOS-style wiggle animation
        self.wiggle_timer = QTimer(self)
        self.wiggle_timer.timeout.connect(self._on_wiggle_tick)

        # LCU connection event binding to reload masteries
        self.viewmodel.league_connected.connect(self._on_league_connected)

        # Initial scan/load
        QTimer.singleShot(100, self._load_known_champions)
        QTimer.singleShot(200, self._render_grid)
        self._sync_undo_btn()

    def _get_role_btn_qss(self, active):
        bg = "#1E2D42" if active else "#0E1826"
        color = "#F0E6D2" if active else "#A0A5B5"
        border = "#C8AA6E" if active else "#1B2A3E"
        return f"""
            QPushButton {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
                color: {color};
                font-size: 10px;
                font-weight: bold;
                padding: 3px 6px;
            }}
            QPushButton:hover {{
                color: #F0E6D2;
                background-color: #1E2D42;
                border: 1px solid #C8AA6E;
            }}
        """

    def _get_sort_btn_qss(self, active):
        bg = "#1E2D42" if active else "#0E1826"
        color = "#F0E6D2" if active else "#A0A5B5"
        border = "#C8AA6E" if active else "#1B2A3E"
        return f"""
            QPushButton {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
                color: {color};
                font-size: 10px;
                font-weight: bold;
                padding: 3px 6px;
            }}
            QPushButton:hover {{
                color: #F0E6D2;
                background-color: #1E2D42;
                border: 1px solid #C8AA6E;
            }}
        """

    def _get_favs_btn_qss(self, active):
        bg = "#A88A4E" if active else "#0E1826"
        color = "#0A1428" if active else "#A0A5B5"
        border = "#C8AA6E" if active else "#1B2A3E"
        return f"""
            QPushButton {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
                color: {color};
                font-size: 10px;
                font-weight: bold;
                padding: 3px 8px;
            }}
            QPushButton:hover {{
                color: #F0E6D2;
                background-color: #1E2D42;
                border: 1px solid #C8AA6E;
            }}
        """

    # ── Role & Sort Updates ──
    def _on_role_selected(self, role):
        self.selected_role = role
        for name, btn in self.role_buttons.items():
            btn.setStyleSheet(self._get_role_btn_qss(name == role))
        self._render_grid()

    def _on_sort_selected(self, sort_type):
        self.selected_sort = sort_type
        for name, btn in self.sort_buttons.items():
            btn.setStyleSheet(self._get_sort_btn_qss(name == sort_type))
        self._render_grid()

    def _on_favs_only_toggled(self, checked):
        self.btn_favs_only.setStyleSheet(self._get_favs_btn_qss(checked))
        self._render_grid()

    # ── Favorite Operations ──
    def is_favorite(self, name) -> bool:
        favs = self.config.get("priority_picker", {}).get("favorites", [])
        return name in favs

    def toggle_favorite(self, name):
        cfg = self.config.get("priority_picker", {})
        favs = cfg.get("favorites", [])
        if name in favs:
            favs.remove(name)
        else:
            favs.append(name)
        cfg["favorites"] = favs
        self.config.set("priority_picker", cfg)

        # Redraw cells to update star colors
        for w in self._row_widgets:
            if w.champ_name == name:
                w.update_style()

        # Re-sort if sorted by favorites
        if self.selected_sort == "Favs" or self.btn_favs_only.isChecked():
            self._render_grid()

    # ── Mastery Resolvers ──
    @Slot(object)
    def _on_league_connected(self, event_data):
        self._load_masteries()
        self._render_grid()

    def _load_masteries(self):
        lcu = self.viewmodel.get_league_service()
        try:
            if lcu and lcu.is_connected:
                records = lcu.get_champion_masteries() or []
                self.mastery_cache = {r.get("championId"): r for r in records}
        except Exception as e:
            Logger.error("ChampionsPage", f"Mastery query error: {e}")

    def get_mastery_for(self, champ_name) -> dict:
        if not self.mastery_cache:
            return None
        root = self.window()
        assets = getattr(root, "assets", None)
        if not assets:
            return None
        cid = assets.name_to_id.get(champ_name.lower())
        if cid:
            return self.mastery_cache.get(cid)
        return None

    def get_champ_tags(self, champ_name) -> list:
        root = self.window()
        assets = getattr(root, "assets", None)
        if not assets or not hasattr(assets, "champ_data"):
            return []
        for key, info in assets.champ_data.items():
            if info.get("name", "").lower() == champ_name.lower() or key.lower() == champ_name.lower():
                return info.get("tags", [])
        return []

    # ── Hover Preview Operations ──
    def show_hover_card(self, name, global_pos):
        # Prevent popup overlapping sidebar navigation
        local_pos = self.mapFromGlobal(global_pos)
        self.hover_card.lbl_name.setText(name)

        # Tags
        tags = self.get_champ_tags(name)
        self.hover_card.lbl_roles.setText(f"Roles: {', '.join(tags)}" if tags else "Roles: Unknown")

        # Mastery
        mastery = self.get_mastery_for(name)
        if mastery:
            lvl = mastery.get("championLevel", 0)
            pts = mastery.get("championPoints", 0)
            self.hover_card.lbl_mastery.setText(f"Mastery: Lvl {lvl}")
            self.hover_card.lbl_points.setText(f"Points: {pts:,}")
        else:
            self.hover_card.lbl_mastery.setText("Mastery: Level 0")
            self.hover_card.lbl_points.setText("Points: 0")

            # Request win rate stats
            stats = self.viewmodel.get_stats_sync()
            if stats:
                wr = stats.get_win_rate(name)
                if wr > 0:
                    self.hover_card.lbl_winrate.setText(f"Win Rate: {wr:.1f}%")
                    if wr >= 53.0:
                        self.hover_card.lbl_winrate.setStyleSheet("color: #2ECC71; font-size: 9px; font-weight: bold;")
                    elif wr <= 48.0:
                        self.hover_card.lbl_winrate.setStyleSheet("color: #E74C3C; font-size: 9px; font-weight: bold;")
                    else:
                        self.hover_card.lbl_winrate.setStyleSheet("color: #C8AA6E; font-size: 9px; font-weight: bold;")
                else:
                    self.hover_card.lbl_winrate.setText("Win Rate: --")
                    self.hover_card.lbl_winrate.setStyleSheet("color: #8A95A5; font-size: 9px;")

        # Apply position locks
        x = local_pos.x()
        y = local_pos.y()
        if x + self.hover_card.width() > self.width():
            x = max(0, x - self.hover_card.width() - 10)
        if y + self.hover_card.height() > self.height():
            y = max(0, self.height() - self.hover_card.height() - 10)

        self.hover_card.move(x, y)
        self.hover_card.setVisible(True)
        self.hover_card.raise_()

    def hide_hover_card(self):
        self.hover_card.setVisible(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "scroll") and self.scroll.viewport():
            vw = self.scroll.viewport().width()
            calc_cols = max(1, vw // (CELL_SIZE + 4))
            if getattr(self, "_last_rendered_cols", None) != calc_cols:
                self._render_grid()

    def _load_known_champions(self):
        root = self.window()
        assets = getattr(root, "assets", None)
        if assets:
            self._known_champions = assets.get_known_champions()
            self._search_cache = sorted([(v.lower(), v) for v in self._known_champions.values()], key=lambda x: x[1])
            self._load_masteries()

    def _get_priority_list(self):
        return self.config.get("priority_picker", {}).get("list", [])

    def _save_priority_list(self, lst, record_history=True):
        if record_history:
            prev = list(self._get_priority_list())
            self.undo_stack.append(prev)
            if len(self.undo_stack) > 10:
                self.undo_stack.pop(0)
            self._sync_undo_btn()

        cfg = self.config.get("priority_picker", {})
        cfg["list"] = lst
        self.config.set("priority_picker", cfg)

    def _sync_undo_btn(self):
        border = get_theme_color("colors.border.subtle", "#1E2328")
        if self.undo_stack:
            self.btn_undo.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {border};
                    border-radius: 4px;
                    color: {get_theme_color("colors.accent.primary", "#C8AA6E")};
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {get_theme_color("colors.state.hover")};
                }}
            """)
        else:
            self.btn_undo.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {border};
                    border-radius: 4px;
                    color: {get_theme_color("colors.text.disabled")};
                }}
            """)

    @Slot()
    def _render_grid(self):
        for w in self._row_widgets:
            w.setParent(None)
            w.deleteLater()
        self._row_widgets.clear()

        raw_list = self._get_priority_list()

        # 1. Process items and map to structured objects to sort and filter
        processed = []
        for index, name in enumerate(raw_list):
            tags = self.get_champ_tags(name)
            mastery = self.get_mastery_for(name) or {}
            is_fav = self.is_favorite(name)

            processed.append({
                "name": name,
                "orig_idx": index,
                "tags": tags,
                "mastery_lvl": mastery.get("championLevel", 0),
                "mastery_pts": mastery.get("championPoints", 0),
                "is_fav": is_fav
            })

        # 2. Filter by Roles & Favorites
        filtered = []
        for p in processed:
            # Role filtering
            if self.selected_role != "All":
                if self.selected_role not in p["tags"]:
                    continue
            # Favorites filter checkbox
            if self.btn_favs_only.isChecked():
                if not p["is_fav"]:
                    continue
            filtered.append(p)

        # 3. Sort Filtered List
        if self.selected_sort == "A-Z":
            filtered.sort(key=lambda x: x["name"].lower())
        elif self.selected_sort == "Mastery":
            # Sort by level desc, then points desc
            filtered.sort(key=lambda x: (x["mastery_lvl"], x["mastery_pts"]), reverse=True)
        elif self.selected_sort == "Favs":
            filtered.sort(key=lambda x: x["is_fav"], reverse=True)
        else:
            # Default priority sort
            filtered.sort(key=lambda x: x["orig_idx"])

        root = self.window()
        assets = getattr(root, "assets", None)

        # Calculate dynamic columns based on viewport width
        viewport_w = self.scroll.viewport().width() if hasattr(self, "scroll") and self.scroll.viewport() else 360
        cols = max(1, viewport_w // (CELL_SIZE + 4))
        self._last_rendered_cols = cols

        for i, item in enumerate(filtered):
            row_idx = i // cols
            col_idx = i % cols

            cell = ChampionCellWidget(
                self,
                self.grid_container,
                champ_name=item["name"],
                index=item["orig_idx"],
                assets=assets,
                on_click=self._on_cell_clicked,
                on_drag_start=self._on_cell_drag_started
            )
            cell.set_selected(item["orig_idx"] in self._selected_indices)

            self.grid_layout.addWidget(cell, row_idx, col_idx)
            self._row_widgets.append(cell)

        # Re-trigger wiggle animation if editing and default order is active
        is_order_locked = (self.selected_role != "All" or self.selected_sort != "Priority" or self.btn_favs_only.isChecked())
        if self._edit_mode and not is_order_locked:
            self._start_wiggle()
        else:
            self._stop_wiggle()

    def _on_cell_clicked(self, idx):
        if not self._edit_mode:
            return

        if idx in self._selected_indices:
            self._selected_indices.remove(idx)
        else:
            self._selected_indices.add(idx)

        # Redraw to update borders
        for w in self._row_widgets:
            w.set_selected(w.index in self._selected_indices)

    def _on_cell_drag_started(self, idx, cell):
        # Do not allow drag start if custom sorting or filters are active
        if self.selected_role != "All" or self.selected_sort != "Priority" or self.btn_favs_only.isChecked():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(idx))
        drag.setMimeData(mime)

        if cell.icon.pixmap_val:
            drag.setPixmap(cell.icon.pixmap_val)
            drag.setHotSpot(QPoint(ICON_SIZE // 2, ICON_SIZE // 2))

        self.setAcceptDrops(True)
        drag.exec(Qt.MoveAction)
        self.setAcceptDrops(False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            src_idx = int(event.mimeData().text())
            pos = event.position().toPoint()

            relative_pos = self.grid_container.mapFrom(self, pos)
            grid_x = relative_pos.x()
            grid_y = relative_pos.y()

            col = max(0, min(3, grid_x // CELL_SIZE))
            row = max(0, grid_y // CELL_SIZE)

            target_idx = (row * 4) + col

            names = self._get_priority_list()
            target_idx = max(0, min(target_idx, len(names) - 1))

            if target_idx != src_idx:
                item = names.pop(src_idx)
                names.insert(target_idx, item)
                self._save_priority_list(names)
                self._selected_indices = {target_idx}
                self._render_grid()

            event.acceptProposedAction()
        except Exception as e:
            Logger.error("ChampionsPage", f"Drop error: {e}")

    # --- Edit Mode & Wiggle ---
    def _toggle_edit_mode(self):
        self._edit_mode = not self._edit_mode
        self._selected_indices.clear()

        self.edit_bar.setVisible(self._edit_mode)
        self.entry_add.setEnabled(not self._edit_mode)

        if self._edit_mode:
            self.btn_edit.setText("Done")
            self.btn_edit.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {get_theme_color("colors.state.danger", "#E74C3C")};
                    border-radius: 4px;
                    color: {get_theme_color("colors.state.danger", "#E74C3C")};
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: #4d1111;
                }}
            """)
            self._start_wiggle()
        else:
            self.btn_edit.setText("Edit")
            self.btn_edit.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {get_theme_color("colors.border.subtle", "#1E2328")};
                    border-radius: 4px;
                    color: {get_theme_color("colors.accent.primary", "#C8AA6E")};
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: {get_theme_color("colors.state.hover")};
                }}
            """)
            self._stop_wiggle()

        self._render_grid()

    def _start_wiggle(self):
        self.wiggle_timer.start(50)

    def _stop_wiggle(self):
        self.wiggle_timer.stop()
        for w in self._row_widgets:
            if hasattr(w, "setRotation"):
                w.setRotation(0)

    def _on_wiggle_tick(self):
        self._wiggle_state += 0.5
        for i, w in enumerate(self._row_widgets):
            if hasattr(w, "setRotation"):
                ang = 3.0 * math.sin(self._wiggle_state + i)
                w.setRotation(ang)

    def _on_search_typing(self, text):
        text = text.strip().lower()
        if not text:
            self.suggestions_widget.setVisible(False)
            return

        # Resolve fuzzy recommendations
        suggestions = []
        for key_low, canonical in self._search_cache:
            if key_low.startswith(text):
                suggestions.append(canonical)
            if len(suggestions) >= 4:
                break

        # Fill suggestion buttons
        # Clear old suggestion buttons
        while self.suggestions_layout.count() > 0:
            item = self.suggestions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if suggestions:
            for s in suggestions:
                btn = QPushButton(s, self.suggestions_widget)
                btn.setFixedHeight(24)
                btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #1E2D42;
                        border: 1px solid #C8AA6E;
                        border-radius: 4px;
                        color: #F0E6D2;
                        font-size: 11px;
                        font-weight: bold;
                        padding-left: 8px;
                        padding-right: 8px;
                    }}
                    QPushButton:hover {{
                        background-color: #283C57;
                        color: #FFFFFF;
                    }}
                """)
                btn.clicked.connect(lambda checked=False, name=s: self._select_suggestion(name))
                self.suggestions_layout.addWidget(btn)
            self.suggestions_layout.addStretch()
            self.suggestions_widget.setVisible(True)
        else:
            self.suggestions_widget.setVisible(False)

    def _select_suggestion(self, name):
        self.entry_add.setText(name)
        self._commit_search_add()

    def _commit_search_add(self):
        raw = self.entry_add.text().strip()
        self.entry_add.clear()
        self.suggestions_widget.setVisible(False)

        if not raw:
            return

        if raw.lower() == "#all":
            from ui.qt.widgets.toast import ToastManager
            all_champs = [canonical for _, canonical in self._search_cache]
            if not all_champs:
                all_champs = ["Aatrox", "Ahri", "Akali", "Akshan", "Alistar", "Amumu", "Anivia", "Annie", "Aphelios", "Ashe", "Aurelion Sol", "Azir", "Bard", "BelVeth", "Blitzcrank", "Brand", "Braum", "Briar", "Caitlyn", "Camille", "Cassiopeia", "ChoGath", "Corki", "Darius", "Diana", "Dr. Mundo", "Draven", "Ekko", "Elise", "Evelynn", "Ezreal", "Fiddlesticks", "Fiora", "Fizz", "Galio", "Gangplank", "Garen", "Gnar", "Gragas", "Graves", "Gwen", "Hecarim", "Heimerdinger", "Hwei", "Illaoi", "Irelia", "Ivern", "Janna", "Jarvan IV", "Jax", "Jayce", "Jhin", "Jinx", "KSante", "Kaisa", "Kalista", "Karma", "Karthus", "Kassadin", "Katarina", "Kayle", "Kayn", "Kennen", "KhaZix", "Kindred", "Kled", "KogMaw", "LeBlanc", "Lee Sin", "Leona", "Lillia", "Lissandra", "Lucian", "Lulu", "Lux", "Malphite", "Malzahar", "Maokai", "Master Yi", "Milio", "Miss Fortune", "Mordekaiser", "Morgana", "Naafiri", "Nami", "Nasus", "Nautilus", "Neeko", "Nidalee", "Nilah", "Nocturne", "Nunu & Willump", "Olaf", "Orianna", "Ornn", "Pantheon", "Poppy", "Pyke", "Qiyana", "Quinn", "Rakan", "Rammus", "RekSai", "Rell", "Renata Glasc", "Renekton", "Rengar", "Riven", "Rumble", "Ryze", "Samira", "Sejuani", "Senna", "Seraphine", "Sett", "Shaco", "Shen", "Shyvana", "Singed", "Sion", "Sivir", "Skarner", "Smolder", "Sona", "Soraka", "Swain", "Sylas", "Syndra", "Tahm Kench", "Taliyah", "Talon", "Taric", "Teemo", "Thresh", "Tristana", "Trundle", "Tryndamere", "Twisted Fate", "Twitch", "Udyr", "Urgot", "Varus", "Vayne", "Veigar", "VelKoz", "Vex", "Vi", "Viego", "Viktor", "Vladimir", "Volibear", "Warwick", "Wukong", "Xayah", "Xerath", "Xin Zhao", "Yasuo", "Yone", "Yorick", "Yuumi", "Zac", "Zed", "Zeri", "Ziggs", "Zilean", "Zoe", "Zyra"]

            names = self._get_priority_list()
            added_count = 0
            for name in all_champs:
                if name not in names:
                    names.append(name)
                    added_count += 1

            self.role_priority[self.active_role] = names
            self.config.set("role_priority", self.role_priority)
            self._render_grid()
            self._sync_undo_btn()
            from ui.qt.widgets.toast import ToastManager
            toast = ToastManager.get_instance()
            if toast:
                toast.show(f"Added {added_count} champions (#all)", icon="✨", theme="info")
            return

        resolved = self._resolve_champion_name(raw)
        if not resolved:
            from ui.qt.widgets.toast import ToastManager
            ToastManager.get_instance().show("Unknown Champion Name", icon="⚠️", theme="error")
            return

        # Check duplicate
        names = self._get_priority_list()
        if resolved in names:
            from ui.qt.widgets.toast import ToastManager
            ToastManager.get_instance().show(f"{resolved} already in grid", icon="ℹ️", theme="error")
            return

        names.append(resolved)
        self._save_priority_list(names)

        # Redraw
        self._render_grid()

        # Scroll to bottom
        QTimer.singleShot(100, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def _resolve_champion_name(self, raw):
        low = raw.lower()
        if low in self._known_champions:
            return self._known_champions[low]

        # Prefix match lookup
        for key_low, canonical in self._search_cache:
            if key_low.startswith(low):
                return canonical
        return None

    def _delete_selected(self):
        if not self._selected_indices:
            return

        names = self._get_priority_list()
        new_names = [names[i] for i in range(len(names)) if i not in self._selected_indices]

        self.role_priority[self.active_role] = new_names
        self.config.set("role_priority", self.role_priority)
        self._render_grid()
        self._sync_undo_btn()

    def _clear_all(self):
        names = self._get_priority_list()
        if not names:
            return

        self._save_priority_list([])
        self._selected_indices.clear()
        self._render_grid()

    def _undo_action(self):
        if not self.undo_stack:
            return

        self.role_priority[self.active_role] = self._undo_stack.pop()
        self.config.set("role_priority", self.role_priority)
        self._render_grid()
        self._sync_undo_btn()
        self._render_grid()

    def _export_list(self):
        names = self._get_priority_list()
        text = ", ".join(names)
        QApplication.clipboard().setText(text)
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show("Priority list copied!", icon="📋", theme="success")

    def _import_list(self):
        text = QApplication.clipboard().text().strip()
        if not text:
            return

        parts = [p.strip() for p in text.split(",") if p.strip()]
        resolved_list = []
        unknown = []

        for p in parts:
            res = self._resolve_champion_name(p)
            if res:
                if res not in resolved_list:
                    resolved_list.append(res)
            else:
                unknown.append(p)

        if len(self.role_priority[self.active_role]) > 1:
            self.role_priority[self.active_role] = resolved_list
            self.config.set("role_priority", self.role_priority)
            self._render_grid()
            self._sync_undo_btn()
            from ui.qt.widgets.toast import ToastManager
            if unknown:
                ToastManager.get_instance().show(f"Imported {len(resolved_list)} champions. Skipped: {', '.join(unknown)}", icon="⚠️", theme="success")
            else:
                ToastManager.get_instance().show(f"Imported {len(resolved_list)} champions successfully!", icon="📥", theme="success")
        else:
            from ui.qt.widgets.toast import ToastManager
            ToastManager.get_instance().show("Failed to resolve any champions", icon="⚠️", theme="error")


# Extends ChampionCellWidget to support Rotation transformations
class RotatedFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rotation = 0.0

    @Property(float)
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, r):
        self._rotation = r
        self.update()

    def paintEvent(self, event):
        if self._rotation == 0.0:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Translate to center, rotate, and translate back
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.rotate(self._rotation)
        painter.translate(-self.width() / 2.0, -self.height() / 2.0)

        # Render cell contents normally but rotated
        super().paintEvent(event)


# Re-implement ChampionCellWidget to inherit from RotatedFrame to enable wiggle rotation!
# Since python classes are defined dynamically, we can dynamically override the parent class
# Or we can just have ChampionCellWidget inherit from RotatedFrame directly.
# Let's ensure ChampionCellWidget inherits from RotatedFrame!
class ChampionCellWidget(RotatedFrame):
    """A single champion cell inside the priority grid with overlays and hover listeners."""

    def __init__(self, parent_page, parent_widget=None, champ_name="", index=-1, assets=None, on_click=None, on_drag_start=None):
        super().__init__(parent_widget)
        self.parent_page = parent_page
        self.champ_name = champ_name
        self.index = index
        self.on_click = on_click
        self.on_drag_start = on_drag_start
        self.selected = False

        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setCursor(Qt.PointingHandCursor)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        self.icon = RoundedIcon(self, radius=6)
        layout.addWidget(self.icon)

        # Async Icon Loading
        if assets:
            def _on_icon_loaded(img):
                if img and hasattr(img, "_image"):
                    pix = pil_to_pixmap(img._image)
                    self.icon.set_pixmap(pix)
            assets.get_icon_async("champion", champ_name, _on_icon_loaded, size=(ICON_SIZE, ICON_SIZE))

        # Tooltip fallback
        self.setToolTip(f"{champ_name} (Priority #{index + 1})")

        # Border styles
        self._border_subtle = get_theme_color("colors.border.subtle", "#1E2328")
        self._gold = get_theme_color("colors.accent.gold", "#C8AA6E")

        # Overlay Favorite Star Button
        self.btn_fav = QPushButton(self)
        self.btn_fav.setFixedSize(14, 14)
        self.btn_fav.setCursor(Qt.PointingHandCursor)
        self.btn_fav.clicked.connect(self._on_fav_clicked)
        self.btn_fav.move(CELL_SIZE - 18, 4)
        self.btn_fav.setStyleSheet("background: transparent; border: none; font-size: 11px; font-weight: bold;")
        self.btn_fav.raise_()

        # Update styling based on configuration
        self.update_style()
        self._drag_start_pos = None

    def _on_fav_clicked(self):
        # Toggle favorite status in page config
        self.parent_page.toggle_favorite(self.champ_name)
        self.update_style()

    def set_selected(self, selected):
        self.selected = selected
        self.update_style()

    def update_style(self):
        # Check if favorited
        is_fav = self.parent_page.is_favorite(self.champ_name)
        self.btn_fav.setText("★" if is_fav else "☆")
        self.btn_fav.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {"#C8AA6E" if is_fav else "#6C757D"};
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: #F0E6D2;
            }}
        """)

        if self.selected:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {get_theme_color("colors.background.card", "#141E28")};
                    border: 2px solid {self._gold};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                }}
                QFrame:hover {{
                    background-color: {get_theme_color("colors.state.hover", "#1C2630")};
                    border: 1px solid {self._border_subtle};
                }}
            """)

    # ── Hover Enter/Leave for Preview Overlay Card ──
    def enterEvent(self, event):
        pos = self.mapToGlobal(QPoint(self.width() + 4, 0))
        self.parent_page.show_hover_card(self.champ_name, pos)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.parent_page.hide_hover_card()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            if self.on_click:
                self.on_click(self.index)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            # Check if grid reordering is locked due to active filters
            page = self.parent_page
            if page.selected_role != "All" or page.selected_sort != "Priority" or page.btn_favs_only.isChecked():
                return

            if (event.position().toPoint() - self._drag_start_pos).manhattanLength() >= 10:
                if self.on_drag_start:
                    self.on_drag_start(self.index, self)
        super().mouseMoveEvent(event)
