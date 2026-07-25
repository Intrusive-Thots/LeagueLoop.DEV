"""
PySide6 Friends Page Component
Manages active friend lists, online status indicators, rank badges,
active champion indicators, and context menus for Quick Invite, Spectate, and Chat.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QMenu, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QMetaObject, Slot, Q_ARG, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap, QImage

from ui.qt.widgets import ScrollableList, make_card, make_button
from ui.qt.theme import get_theme_color, get_theme_radius, get_theme_spacing
from services.friend_service import get_friend_service
from services.league_service import get_league_service
from core.events import EventBus
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
        Logger.error("FriendsPage", f"Error converting PIL image: {e}")
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
            # Gold-rimmed dark blue placeholder circle
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
        
        # Stylesheet layout matching design tokens
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
        
        # Circle Avatar
        self.avatar = CircleLabel(self)
        layout.addWidget(self.avatar)
        
        # Async Icon Loading
        icon_id = friend_data.get("icon", 1)
        if not isinstance(icon_id, int) or icon_id < 0:
            icon_id = 1
        if assets:
            def _on_icon_loaded(img):
                if img and hasattr(img, "_image"):
                    pix = pil_to_pixmap(img._image)
                    QMetaObject.invokeMethod(self.avatar, "set_pixmap", Qt.QueuedConnection, Q_ARG(QPixmap, pix))
            assets.get_icon_async("profileicon", str(icon_id), _on_icon_loaded, size=(32, 32))
            
        # Status Dot
        self.status_dot = QLabel("●", self)
        is_online = self.avail != "offline"
        dot_color = get_theme_color("colors.state.success", "#2ECC71") if is_online else get_theme_color("colors.state.error", "#E74C3C")
        self.status_dot.setStyleSheet(f"color: {dot_color}; font-size: 13px;")
        layout.addWidget(self.status_dot)
        
        # Text Stack Layout (Name + Message / Champion status)
        text_widget = QWidget(self)
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        name_color = get_theme_color("colors.accent.primary", "#C8AA6E") if is_online else get_theme_color("colors.text.disabled", "#5C6B73")
        self.lbl_name = QLabel(self.name, text_widget)
        self.lbl_name.setStyleSheet(f"color: {name_color}; font-weight: bold; font-size: 12px; background: transparent;")
        text_layout.addWidget(self.lbl_name)
        
        # Resolve dynamic game details
        status_msg = "Offline"
        if is_online:
            status_msg = friend_data.get("availabilityMessage") or friend_data.get("statusMessage") or "Online"
            
            # Check LCU inner game state details
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
        
        # Resolve Rank Details
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
        
        # Auto-Join Toggle Icon Button
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
        
        # Tooltips
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


class FriendsPage(ScrollableList):
    """The PySide6 Friends Management Page containing active logs, filters, stats, and auto-join states."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._friends_data = []
        self._row_widgets = []
        
        self.container_layout.setContentsMargins(16, 16, 16, 16)
        self.container_layout.setSpacing(12)
        
        # Setup UI frame card
        self.setup_ui()
        
        # Subscribe to EventBus updates
        EventBus.on("friends_state_changed", self._on_friends_state_changed)
        
        # Initial render
        self.refresh_list_data()

    def setup_ui(self):
        self.card = make_card(title="FRIEND LIST")
        self.add_widget(self.card)
        
        # Header Toolbar Layout
        toolbar = QWidget(self.card)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)
        
        # Online Badge Indicator bubble
        self.lbl_online_count = QLabel("0", toolbar)
        self.lbl_online_count.setFixedSize(22, 18)
        self.lbl_online_count.setAlignment(Qt.AlignCenter)
        self.lbl_online_count.setStyleSheet(f"""
            QLabel {{
                background-color: {get_theme_color("colors.text.muted")};
                color: {get_theme_color("colors.background.app")};
                border-radius: 9px;
                font-weight: bold;
                font-size: 10px;
            }}
        """)
        toolbar_layout.addWidget(self.lbl_online_count)
        
        # Filter Input
        self.entry_filter = QLineEdit(toolbar)
        self.entry_filter.setPlaceholderText("Search friends...")
        self.entry_filter.setFixedHeight(24)
        
        bg_card = get_theme_color("colors.background.card", "#141E28")
        border = get_theme_color("colors.border.subtle", "#1E2328")
        gold = get_theme_color("colors.accent.gold", "#C8AA6E")
        self.entry_filter.setStyleSheet(f"""
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
        self.entry_filter.textChanged.connect(self._apply_filter)
        toolbar_layout.addWidget(self.entry_filter)
        
        # Mass Invite Button
        self.btn_invite = make_button(toolbar, text="👥 Invite All", style="primary", width=80, height=24)
        self.btn_invite.setStyleSheet("""
            QPushButton {
                font-size: 10px;
                font-weight: bold;
            }
        """)
        self.btn_invite.clicked.connect(self._on_mass_invite)
        self.btn_invite.setToolTip("Invite all online friends (or VIPs) to your lobby")
        toolbar_layout.addWidget(self.btn_invite)
        
        # Export Clipboard Button
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
                color: #FFFFFF;
            }}
        """)
        self.btn_export.clicked.connect(self._export_list)
        self.btn_export.setToolTip("Export List to Clipboard")
        toolbar_layout.addWidget(self.btn_export)
        
        # Refresh Data Button
        self.btn_refresh = QPushButton("↻", toolbar)
        self.btn_refresh.setFixedSize(24, 24)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {border};
                border-radius: 4px;
                color: {get_theme_color("colors.text.muted")};
                font-size: 15px;
            }}
            QPushButton:hover {{
                background-color: {get_theme_color("colors.state.hover")};
                color: #FFFFFF;
            }}
        """)
        self.btn_refresh.clicked.connect(self._refresh_friends_data)
        self.btn_refresh.setToolTip("Refresh Friend List")
        toolbar_layout.addWidget(self.btn_refresh)
        
        self.card.add_widget(toolbar)
        
        # Content frame containing friend rows list
        self.list_container = QFrame(self.card)
        self.list_container.setStyleSheet("background-color: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(2)
        
        self.card.add_widget(self.list_container)

    def refresh_list_data(self):
        """Initializes state from FriendService."""
        self._friends_data = get_friend_service().get_friends()
        if self._friends_data:
            self._render_list()
        else:
            get_friend_service().fetch_friends()

    def _on_friends_state_changed(self):
        self._friends_data = get_friend_service().get_friends()
        # Safe thread-dispatching
        QMetaObject.invokeMethod(self, "_render_list", Qt.QueuedConnection)

    @Slot()
    def _render_list(self):
        # Clear old rows
        for w in self._row_widgets:
            w.setParent(None)
            w.deleteLater()
        self._row_widgets.clear()
        
        # Filter matching text
        filter_text = self.entry_filter.text().strip().lower()
        
        # Update online count bubble
        online_count = sum(1 for f in self._friends_data if f.get("availability", "offline") != "offline")
        self.lbl_online_count.setText(str(online_count))
        if online_count > 0:
            self.lbl_online_count.setStyleSheet(f"""
                QLabel {{
                    background-color: {get_theme_color("colors.state.success")};
                    color: {get_theme_color("colors.background.app")};
                    border-radius: 9px;
                    font-weight: bold;
                    font-size: 10px;
                }}
            """)
        else:
            self.lbl_online_count.setStyleSheet(f"""
                QLabel {{
                    background-color: {get_theme_color("colors.text.muted")};
                    color: {get_theme_color("colors.background.app")};
                    border-radius: 9px;
                    font-weight: bold;
                    font-size: 10px;
                }}
            """)
            
        if not self._friends_data:
            lbl = QLabel("Checking friends...", self.list_container)
            lbl.setStyleSheet(f"color: {get_theme_color('colors.text.muted')}; font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(lbl)
            self._row_widgets.append(lbl)
            return

        # Fetch AssetManager from top window
        root = self.window()
        assets = getattr(root, "assets", None)
        
        row_count = 0
        for friend in self._friends_data:
            name = friend.get("gameName", "") or friend.get("name", "")
            if not name:
                continue
                
            # Filter matches
            if filter_text and filter_text not in name.lower():
                continue
                
            row = FriendRowWidget(
                self.list_container,
                friend_data=friend,
                assets=assets,
                on_toggle_auto=self._toggle_auto_join,
                on_context=self._show_context_menu
            )
            self.list_layout.addWidget(row)
            self._row_widgets.append(row)
            row_count += 1
            
        if row_count == 0:
            lbl = QLabel("No friends match the active filter.", self.list_container)
            lbl.setStyleSheet(f"color: {get_theme_color('colors.text.muted')}; font-size: 11px; padding: 12px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(lbl)
            self._row_widgets.append(lbl)

    def _toggle_auto_join(self, name):
        get_friend_service().toggle_auto_join(name)
        self._render_list()

    def _apply_filter(self):
        self._render_list()

    def _show_context_menu(self, friend_name, pos):
        menu = QMenu(self)
        border = get_theme_color("colors.border.subtle", "#1E2328")
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {get_theme_color("colors.background.card")};
                color: {get_theme_color("colors.text.primary")};
                border: 1px solid {border};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 4px 16px;
            }}
            QMenu::item:selected {{
                background-color: {get_theme_color("colors.state.hover")};
                color: #FFFFFF;
            }}
        """)
        
        name_lower = friend_name.lower()
        is_auto = get_friend_service().get_auto_join_status(name_lower)
        label = "✕ Disable Auto-Join" if is_auto else "✓ Enable Auto-Join"
        
        act_toggle = menu.addAction(label)
        act_toggle.triggered.connect(lambda: self._toggle_auto_join(friend_name))
        
        act_invite = menu.addAction("👥 Send Party Invite")
        act_invite.triggered.connect(lambda: get_friend_service().invite_friend(friend_name))
        
        act_spectate = menu.addAction("👁 Spectate Game")
        act_spectate.triggered.connect(lambda: self._spectate_friend(friend_name))
        
        act_msg = menu.addAction("💬 Quick Message (Copy Name)")
        act_msg.triggered.connect(lambda: self._message_friend(friend_name))
        
        menu.exec(pos)

    def _spectate_friend(self, name):
        from ui.qt.widgets.toast import ToastManager
        lcu = get_league_service()
        if lcu and lcu.is_connected:
            # Trigger launch spectate LCU call
            lcu.request("POST", "/lol-spectator/v1/spectate/launch", json={"summonerName": name})
            ToastManager.get_instance().show(f"Launching Spectator: {name}", icon="👁", theme="success")
        else:
            ToastManager.get_instance().show("Client not connected", icon="⚠️", theme="error")

    def _message_friend(self, name):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(name)
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show(f"Copied {name} to clipboard", icon="💬", theme="success")

    def _on_mass_invite(self):
        EventBus.emit("action:mass_invite")

    def _refresh_friends_data(self):
        get_friend_service().fetch_friends()

    def _export_list(self):
        from ui.qt.widgets.toast import ToastManager
        if not self._friends_data:
            ToastManager.get_instance().show("Friend list is empty!", icon="⚠️", theme="error")
            return
            
        names = [f.get("name", "") for f in self._friends_data if f.get("name", "")]
        export_str = "\n".join(names)
        
        from PySide6.QtGui import QGuiApplication
        cb = QGuiApplication.clipboard()
        cb.setText(export_str)
        
        ToastManager.get_instance().show(
            "Friend List Copied!",
            icon="📋",
            theme="success",
            confetti=True
        )
