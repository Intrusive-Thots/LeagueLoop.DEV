"""
PySide6 Friend Row Component
Renders individual friend cards with status dots, badges, and avatars.
"""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtCore import Qt, QMetaObject, Q_ARG, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap, QImage

from ui.qt.theme import get_theme_color
from services.friend_service import get_friend_service
from utils.logger import Logger

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
        Logger.error("FriendRow", f"Error converting PIL image: {e}")
        return QPixmap()


class CircleLabel(QLabel):
    """Custom circular image widget for profile icons."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.pixmap_val = None

    def set_pixmap(self, pixmap):
        self.pixmap_val = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.pixmap_val and not self.pixmap_val.isNull():
            path = QPainterPath()
            path.addEllipse(0, 0, self.width(), self.height())
            painter.setClipPath(path)
            painter.drawPixmap(self.rect(), self.pixmap_val)
        else:
            painter.setBrush(QBrush(QColor("#141E28")))
            painter.setPen(QPen(QColor(get_theme_color("colors.accent.gold", "#C8AA6E")), 1))
            painter.drawEllipse(0, 0, self.width() - 1, self.height() - 1)


class FriendRowWidget(QFrame):
    """A single friend entry card featuring profile avatar, status dot, rank badges, and auto-join toggle."""
    
    def __init__(self, parent=None, friend_data=None, assets=None, on_toggle_auto=None, on_context=None):
        super().__init__(parent)
        self.friend_data = friend_data
        self.on_toggle_auto = on_toggle_auto
        self.on_context = on_context
        
        self.name = friend_data.get("gameName", "") or friend_data.get("name", "")
        self.name_lower = friend_data.get("_name_lower", self.name.lower())
        self.avail = friend_data.get("availability", "offline")
        
        self.setFixedHeight(46)
        self.setCursor(Qt.PointingHandCursor)
        
        border = get_theme_color("colors.border.subtle", "#1E2328")
        self.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
            }}
            QFrame:hover {{
                background-color: {get_theme_color("colors.state.hover", "#1C2630")};
                border: 1px solid {border};
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)
        
        self.avatar = CircleLabel(self)
        layout.addWidget(self.avatar)
        
        icon_id = friend_data.get("icon", 1)
        if not isinstance(icon_id, int) or icon_id < 0:
            icon_id = 1
        if assets:
            def _on_icon_loaded(img):
                if img and hasattr(img, "_image"):
                    pix = pil_to_pixmap(img._image)
                    QMetaObject.invokeMethod(self.avatar, "set_pixmap", Qt.QueuedConnection, Q_ARG(QPixmap, pix))
            assets.get_icon_async("profileicon", str(icon_id), _on_icon_loaded, size=(32, 32))
            
        self.status_dot = QLabel("●", self)
        is_online = self.avail != "offline"
        dot_color = get_theme_color("colors.state.success", "#2ECC71") if is_online else get_theme_color("colors.state.error", "#E74C3C")
        self.status_dot.setStyleSheet(f"color: {dot_color}; font-size: 13px;")
        layout.addWidget(self.status_dot)
        
        text_widget = QWidget(self)
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        name_color = get_theme_color("colors.accent.primary", "#C8AA6E") if is_online else get_theme_color("colors.text.disabled", "#5C6B73")
        self.lbl_name = QLabel(self.name, text_widget)
        self.lbl_name.setStyleSheet(f"color: {name_color}; font-weight: bold; font-size: 12px; background: transparent;")
        text_layout.addWidget(self.lbl_name)
        
        status_msg = "Offline"
        if is_online:
            status_msg = friend_data.get("availabilityMessage") or friend_data.get("statusMessage") or "Online"
            lol = friend_data.get("lol", {})
            game_state = lol.get("gameStatus") or friend_data.get("gameStatus")
            
            if game_state == "inGame":
                champ_id = lol.get("championId") or friend_data.get("championId")
                if champ_id and assets:
                    try:
                        cname = assets.get_champ_name(int(champ_id))
                        status_msg = f"In Game - {cname}"
                    except Exception:
                        status_msg = "In Game"
                else:
                    status_msg = "In Game"
            elif game_state == "champSelect":
                status_msg = "Champ Select"
            elif game_state == "inQueue":
                status_msg = "In Queue"
                
        lbl_msg_color = get_theme_color("colors.text.muted", "#A0A5B5") if is_online else get_theme_color("colors.text.disabled", "#5C6B73")
        self.lbl_msg = QLabel(status_msg, text_widget)
        self.lbl_msg.setStyleSheet(f"color: {lbl_msg_color}; font-size: 10px; background: transparent;")
        text_layout.addWidget(self.lbl_msg)
        
        layout.addWidget(text_widget)
        layout.addStretch()
        
        lol_dict = friend_data.get("lol", {})
        tier = lol_dict.get("rankedLeagueTier") or friend_data.get("tier", "")
        division = lol_dict.get("rankedLeagueDivision") or friend_data.get("division", "")
        if tier and str(tier).lower() != "unranked":
            rank_str = f"{tier[:3].upper()} {division}"
            self.lbl_rank = QLabel(rank_str, self)
            self.lbl_rank.setStyleSheet("""
                color: #C8AA6E;
                font-size: 8px;
                font-weight: bold;
                background-color: #151F2F;
                border: 1px solid #1E2839;
                border-radius: 3px;
                padding-left: 4px;
                padding-right: 4px;
                height: 14px;
            """)
            layout.addWidget(self.lbl_rank)
        
        self.is_auto = get_friend_service().get_auto_join_status(self.name_lower)
        self.btn_auto = QPushButton("⚭", self)
        self.btn_auto.setFixedSize(24, 24)
        self.btn_auto.setCursor(Qt.PointingHandCursor)
        
        auto_color = get_theme_color("colors.accent.blue", "#00A2FF") if self.is_auto else get_theme_color("colors.text.disabled")
        self.btn_auto.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {auto_color};
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
            }}
        """)
        self.btn_auto.clicked.connect(self._toggle_auto_join)
        layout.addWidget(self.btn_auto)
        
        self.setToolTip(f"{self.name} - Status: {self.avail.capitalize()}")
        self.btn_auto.setToolTip("Auto-Join Config - Click to Toggle")

    def _toggle_auto_join(self):
        if self.on_toggle_auto:
            self.on_toggle_auto(self.name)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.on_context:
                self.on_context(self.name, event.globalPosition().toPoint())
        else:
            super().mousePressEvent(event)
