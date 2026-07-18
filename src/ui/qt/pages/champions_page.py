"""
PySide6 Champions Page Component
Manages the champion priority grid (ARAM list), fuzzy search, drag reordering, and import/export.
"""
import math
import string
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QMenu, QGraphicsOpacityEffect,
    QGridLayout, QScrollArea, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, Property, QPropertyAnimation, QEasingCurve, Slot, QPoint, QMimeData
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap, QImage, QDrag, QCursor

from ui.qt.widgets import ScrollableList, make_card, make_button
from ui.qt.theme import get_theme_color, get_theme_radius, get_theme_spacing
from services.settings_service import get_settings_service
from services.league_service import get_league_service
from core.events import EventBus
from utils.logger import Logger

# Standard size tokens
ICON_SIZE = 48
CELL_SIZE = 64
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
    """A single champion cell inside the priority grid."""
    
    def __init__(self, parent=None, champ_name="", index=-1, assets=None, on_click=None, on_drag_start=None):
        super().__init__(parent)
        self.champ_name = champ_name
        self.index = index
        self.on_click = on_click
        self.on_drag_start = on_drag_start
        self.selected = False
        
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        
        # UI Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
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
            # Fetch champion icon
            assets.get_icon_async("champion", champ_name, _on_icon_loaded, size=(ICON_SIZE, ICON_SIZE))
            
        # Tooltip with stats summary
        self.setToolTip(f"{champ_name} (Priority #{index + 1})")
        
        # Border styles
        self._border_subtle = get_theme_color("colors.border.subtle", "#1E2328")
        self._gold = get_theme_color("colors.accent.gold", "#C8AA6E")
        self.update_style()
        
        # Wiggle parameters
        self._wiggle_angle = 0.0

    def set_selected(self, selected):
        self.selected = selected
        self.update_style()

    def update_style(self):
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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            if self.on_click:
                self.on_click(self.index)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            if (event.position().toPoint() - self._drag_start_pos).manhattanLength() >= 10:
                if self.on_drag_start:
                    self.on_drag_start(self.index, self)
        super().mouseMoveEvent(event)


class ChampionsPage(QWidget):
    """The PySide6 Champions Page containing the ARAM Priority Grid."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        self.undo_stack = []
        self._row_widgets = []
        self._selected_indices = set()
        self._edit_mode = False
        self._wiggle_state = 0.0
        
        # Load known champions asynchronously
        self._known_champions = {}
        self._search_cache = []
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Main Grid Scroll Frame Card
        self.card = make_card(self, title="ARAM PRIORITY SNIPER")
        layout.addWidget(self.card.parentWidget())
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(10)
        
        # --- Toolbar ---
        toolbar = QWidget(self.card)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)
        
        # Edit Toggle Button
        self.btn_edit = QPushButton("Edit", toolbar)
        self.btn_edit.setFixedSize(50, 24)
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
        self.grid_layout.setSpacing(6)
        
        self.scroll.setWidget(self.grid_container)
        card_layout.addWidget(self.scroll)
        
        # Wiggle timer for iOS-style wiggle animation
        self.wiggle_timer = QTimer(self)
        self.wiggle_timer.timeout.connect(self._on_wiggle_tick)
        
        # Initial scan/load
        QTimer.singleShot(100, self._load_known_champions)
        QTimer.singleShot(200, self._render_grid)
        self._sync_undo_btn()

    def _load_known_champions(self):
        root = self.window()
        assets = getattr(root, "assets", None)
        if assets:
            self._known_champions = assets.get_known_champions()
            self._search_cache = sorted([(v.lower(), v) for v in self._known_champions.values()], key=lambda x: x[1])

    def _get_priority_list(self):
        raw = self.config.get("priority_picker", {}).get("list", [])
        # Deduplicate
        return list(dict.fromkeys(raw))

    def _save_priority_list(self, lst, record_history=True):
        if record_history:
            current = self._get_priority_list()
            if current != lst:
                self.undo_stack.append(current)
                if len(self.undo_stack) > 10:
                    self.undo_stack.pop(0)
                self._sync_undo_btn()
                
        cfg = self.config.get("priority_picker", {})
        cfg["list"] = list(dict.fromkeys(lst))
        self.config.set("priority_picker", cfg)
        EventBus.emit("settings_saved")

    def _sync_undo_btn(self):
        self.btn_undo.setEnabled(len(self.undo_stack) > 0)
        if len(self.undo_stack) > 0:
            self.btn_undo.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {get_theme_color("colors.border.subtle", "#1E2328")};
                    border-radius: 4px;
                    color: {get_theme_color("colors.text.primary")};
                }}
            """)
        else:
            self.btn_undo.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {get_theme_color("colors.border.subtle", "#1E2328")};
                    border-radius: 4px;
                    color: {get_theme_color("colors.text.disabled")};
                }}
            """)

    @Slot()
    def _render_grid(self):
        # Clear old rows
        for w in self._row_widgets:
            w.setParent(None)
            w.deleteLater()
        self._row_widgets.clear()
        
        priority_list = self._get_priority_list()
        
        root = self.window()
        assets = getattr(root, "assets", None)
        
        cols = 4
        for i, name in enumerate(priority_list):
            row_idx = i // cols
            col_idx = i % cols
            
            cell = ChampionCellWidget(
                self.grid_container,
                champ_name=name,
                index=i,
                assets=assets,
                on_click=self._on_cell_clicked,
                on_drag_start=self._on_cell_drag_started
            )
            cell.set_selected(i in self._selected_indices)
            
            self.grid_layout.addWidget(cell, row_idx, col_idx)
            self._row_widgets.append(cell)
            
        # Re-trigger wiggle if in edit mode
        if self._edit_mode:
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
            
        self._render_grid()

    def _on_cell_drag_started(self, idx, cell):
        if self._edit_mode:
            return # No drag/drop inside wiggle edit mode
            
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(idx))
        drag.setMimeData(mime)
        
        # Pixmap preview
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
            
            # Map drop position to row/col
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
        if not self.wiggle_timer.isActive():
            self.wiggle_timer.start(50)

    def _stop_wiggle(self):
        self.wiggle_timer.stop()
        for w in self._row_widgets:
            if isinstance(w, ChampionCellWidget):
                # Reset offset geometry
                w.icon.move(4, 4)

    def _on_wiggle_tick(self):
        self._wiggle_state += 0.4
        for i, w in enumerate(self._row_widgets):
            if isinstance(w, ChampionCellWidget):
                # iOS-style sinusoidal wiggle offsets for realistic wiggling
                dx = int(math.sin(self._wiggle_state + i * 1.2) * 1.5)
                dy = int(math.cos(self._wiggle_state * 0.8 + i * 0.7) * 1.2)
                w.icon.move(4 + dx, 4 + dy)

    # --- Add Search / Typing Handlers ---
    def _on_search_typing(self, text):
        query = text.strip().lower()
        
        # Clear suggestions list
        for w in self.suggestions_widget.findChildren(QPushButton):
            w.setParent(None)
            w.deleteLater()
            
        if not query:
            self.suggestions_widget.setVisible(False)
            return
            
        # Find matches
        matches = []
        for champ_lower, champ in self._search_cache:
            if champ_lower.startswith(query):
                matches.append(champ)
            elif query in champ_lower:
                matches.append(champ)
                
        unique_matches = list(dict.fromkeys(matches))[:3]
        
        if not unique_matches:
            self.suggestions_widget.setVisible(False)
            return
            
        self.suggestions_widget.setVisible(True)
        border = get_theme_color("colors.border.subtle", "#1E2328")
        
        for champ in unique_matches:
            btn = QPushButton(champ, self.suggestions_widget)
            btn.setFixedHeight(20)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_theme_color("colors.background.card")};
                    border: 1px solid {border};
                    border-radius: 10px;
                    color: {get_theme_color("colors.text.primary")};
                    font-size: 10px;
                    padding-left: 8px;
                    padding-right: 8px;
                }}
                QPushButton:hover {{
                    background-color: {get_theme_color("colors.state.hover")};
                }}
            """)
            btn.clicked.connect(lambda checked=False, name=champ: self._select_suggestion(name))
            self.suggestions_layout.addWidget(btn)
            
        self.suggestions_layout.addStretch()

    def _select_suggestion(self, name):
        self.entry_add.setText(name)
        self._commit_search_add()

    def _commit_search_add(self):
        raw = self.entry_add.text().strip()
        if not raw:
            return
            
        # Secret: "all"
        if raw.lower() == "all":
            names = self._get_priority_list()
            for champ in self._known_champions.values():
                if champ not in names:
                    names.append(champ)
            self._save_priority_list(names)
            
            self.entry_add.clear()
            self.suggestions_widget.setVisible(False)
            self._render_grid()
            return
            
        # Resolve champion name
        resolved = self._resolve_champion_name(raw)
        if not resolved:
            # Shake effect on input border
            self.entry_add.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {get_theme_color("colors.background.card", "#141E28")};
                    border: 1.5px solid {get_theme_color("colors.state.error", "#E74C3C")};
                    border-radius: 4px;
                    color: #F0E6D2;
                    font-size: 11px;
                    padding-left: 6px;
                    padding-right: 6px;
                }}
            """)
            QTimer.singleShot(1000, lambda: self.entry_add.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {get_theme_color("colors.background.card", "#141E28")};
                    border: 1px solid {get_theme_color("colors.border.subtle", "#1E2328")};
                    border-radius: 4px;
                    color: #F0E6D2;
                    font-size: 11px;
                    padding-left: 6px;
                    padding-right: 6px;
                }}
                QLineEdit:focus {{
                    border: 1px solid {get_theme_color("colors.accent.gold", "#C8AA6E")};
                }}
            """))
            return
            
        names = self._get_priority_list()
        if resolved not in names:
            names.append(resolved)
            self._save_priority_list(names)
            
        self.entry_add.clear()
        self.suggestions_widget.setVisible(False)
        self._render_grid()

    def _resolve_champion_name(self, raw):
        res = self._known_champions.get(raw)
        if res:
            return res
        normalized = raw.translate(_CLEAN_TRANS).lower()
        # Search exact normalized
        for c_lower, c in self._search_cache:
            if c_lower.translate(_CLEAN_TRANS) == normalized:
                return c
        return None

    # --- Actions ---
    def _delete_selected(self):
        if not self._selected_indices:
            return
            
        names = self._get_priority_list()
        # Delete items
        new_names = [names[i] for i in range(len(names)) if i not in self._selected_indices]
        self._save_priority_list(new_names)
        self._selected_indices.clear()
        self._render_grid()
        
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show("Removed selected champions", icon="🗑️", theme="success")

    def _clear_all(self):
        # Require double-click/confirmation dialog
        from ui.qt.widgets.toast import ToastManager
        
        dialog = QMessageBox(self.window())
        dialog.setWindowTitle("Clear ARAM list")
        dialog.setText("Are you sure you want to clear the entire priority list?")
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dialog.setStyleSheet(f"background-color: {get_theme_color('colors.background.panel')}; color: #F0E6D2;")
        
        res = dialog.exec()
        if res == QMessageBox.Yes:
            self._save_priority_list([])
            self._selected_indices.clear()
            self._render_grid()
            ToastManager.get_instance().show("Priority list cleared", icon="🗑️", theme="error")

    def _undo_action(self):
        if not self.undo_stack:
            return
            
        previous = self.undo_stack.pop()
        self._save_priority_list(previous, record_history=False)
        self._sync_undo_btn()
        self._selected_indices.clear()
        self._render_grid()
        
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show("Undid last edit", icon="↩", theme="success")

    def _export_list(self):
        names = self._get_priority_list()
        if not names:
            return
            
        export_str = ", ".join(names)
        from PySide6.QtGui import QGuiApplication
        cb = QGuiApplication.clipboard()
        cb.setText(export_str)
        
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show("List copied to clipboard", icon="📋", theme="success")

    def _import_list(self):
        from PySide6.QtGui import QGuiApplication
        cb = QGuiApplication.clipboard()
        raw = cb.text().strip()
        
        from ui.qt.widgets.toast import ToastManager
        if not raw:
            ToastManager.get_instance().show("Clipboard is empty!", icon="⚠️", theme="error")
            return
            
        potential_champs = [c.strip() for c in raw.split(",") if c.strip()]
        resolved_names = []
        for p in potential_champs:
            resolved = self._resolve_champion_name(p)
            if resolved:
                resolved_names.append(resolved)
                
        resolved_names = list(dict.fromkeys(resolved_names))
        if not resolved_names:
            ToastManager.get_instance().show("No valid champions in clipboard.", icon="⚠️", theme="error")
            return
            
        self._save_priority_list(resolved_names)
        self._render_grid()
        
        ToastManager.get_instance().show(
            f"Imported {len(resolved_names)} champions!",
            icon="📥",
            theme="success"
        )
