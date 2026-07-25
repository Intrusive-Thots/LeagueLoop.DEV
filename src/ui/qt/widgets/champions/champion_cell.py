"""
PySide6 Champion Cell Component
Handles rendering individual champion icons in the priority grid with drag-and-drop support,
favorite toggling, rotation animations, and hover state overlays.
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, Property
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap, QImage

from ui.qt.theme import get_theme_color
from utils.logger import Logger

ICON_SIZE = 48
CELL_SIZE = 72

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
        Logger.error("ChampionCell", f"Error converting PIL image: {e}")
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


class RotatedFrame(QFrame):
    """QFrame subclass that supports rotation for wiggle animations."""
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
        
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.rotate(self._rotation)
        painter.translate(-self.width() / 2.0, -self.height() / 2.0)
        
        super().paintEvent(event)


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
        self._drag_start_pos = None
        
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
            
        self.setToolTip(f"{champ_name} (Priority #{index + 1})")
        
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
        
        self.update_style()

    def _on_fav_clicked(self):
        self.parent_page.toggle_favorite(self.champ_name)
        self.update_style()

    def set_selected(self, selected):
        self.selected = selected
        self.update_style()

    def update_style(self):
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
        if event.buttons() == Qt.LeftButton and self._drag_start_pos is not None:
            # Reordering check - delegate to parent page to decide if locked
            if not getattr(self.parent_page, "can_reorder", lambda: True)():
                return
                
            if (event.position().toPoint() - self._drag_start_pos).manhattanLength() >= 10:
                if self.on_drag_start:
                    self.on_drag_start(self.index, self)
        super().mouseMoveEvent(event)
