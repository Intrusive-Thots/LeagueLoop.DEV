"""
PySide6 Main Window Shell
Implements custom Riot-inspired window chrome, sidebar layout, page navigation, and integrates with WindowService.
"""
import sys
from PySide6.QtCore import Qt, QSize, Signal, Slot, Property, QPropertyAnimation, QEasingCurve, QTimer, QMetaObject, Q_ARG
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QSizePolicy
)
from PySide6.QtGui import QIcon, QMouseEvent

from services.window_service import get_window_service
from services.league_service import get_league_service
from services.settings_service import get_settings_service
from ui.qt.theme import apply_theme, get_theme_color, get_theme_radius, get_theme_spacing
from core.events import EventBus
from utils.logger import Logger

class CustomTitleBar(QWidget):
    """Custom title bar for dragging and basic controls."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(32)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        
        # Logo / Title
        self.title_label = QLabel("League Loop", self)
        self.title_label.setStyleSheet("font-weight: bold; color: #F0E6D2;")
        layout.addWidget(self.title_label)
        layout.addStretch()
        
        # Dock/Undock toggle
        self.btn_dock = QPushButton("🔗", self)
        self.btn_dock.setFixedSize(20, 20)
        self.btn_dock.setCursor(Qt.PointingHandCursor)
        self.btn_dock.setStyleSheet("border: none; color: #C8AA6E;")
        self.btn_dock.clicked.connect(self._toggle_dock)
        layout.addWidget(self.btn_dock)
        
        # Minimize button
        self.btn_min = QPushButton("─", self)
        self.btn_min.setFixedSize(20, 20)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.setStyleSheet("border: none; color: #C8AA6E;")
        self.btn_min.clicked.connect(self.parent.showMinimized)
        layout.addWidget(self.btn_min)
        
        # Close button
        self.btn_close = QPushButton("✕", self)
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("border: none; color: #E74C3C;")
        self.btn_close.clicked.connect(self.parent.close)
        layout.addWidget(self.btn_close)
        
        self._drag_position = None
        self._window_service = get_window_service()
        self._update_dock_icon()

    def _toggle_dock(self):
        is_docked = self._window_service.is_docked
        self._window_service.set_docked_mode(not is_docked)
        self._update_dock_icon()

    def _update_dock_icon(self):
        is_docked = self._window_service.is_docked
        self.btn_dock.setText("🔗" if is_docked else "🔓")
        self.btn_dock.setToolTip("Docked Mode (Snaps to League)" if is_docked else "Undocked Mode (Free Window)")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_position and not self._window_service.is_docked:
            self.parent.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()


class StatusBar(QFrame):
    """Bottom status bar displaying LCU connection state and mode."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("statusBarFrame")
        self.setStyleSheet(f"""
            QFrame#statusBarFrame {{
                background-color: #0A1428;
                border-top: 1px solid #1A2332;
            }}
            QLabel {{
                color: #C8AA6E;
                font-size: 11px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        
        self.lbl_status = QLabel("Disconnected", self)
        layout.addWidget(self.lbl_status)
        
        layout.addStretch()
        
        self.lbl_mode = QLabel("ARAM Mode", self)
        layout.addWidget(self.lbl_mode)
        
        EventBus.on("league_connected", self._on_connected)
        EventBus.on("league_disconnected", self._on_disconnected)
        
    def _connected_async(self):
        self.lbl_status.setText("Connected to LCU")
        self.lbl_status.setStyleSheet("color: #2ECC71;")

    def _on_connected(self):
        from PySide6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self, "_connected_async", Qt.QueuedConnection)
        
    def _disconnected_async(self):
        self.lbl_status.setText("Disconnected")
        self.lbl_status.setStyleSheet("color: #E74C3C;")

    def _on_disconnected(self):
        from PySide6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self, "_disconnected_async", Qt.QueuedConnection)


class NavButton(QPushButton):
    """Custom navigation button supporting text labels, icons, and reactive badges."""
    
    def __init__(self, name, icon_char, page_index, parent=None):
        super().__init__(parent)
        self.name = name
        self.icon_char = icon_char
        self.page_index = page_index
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedHeight(36)
        
        self.btn_layout = QHBoxLayout(self)
        self.btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_layout.setSpacing(10)
        self.btn_layout.setAlignment(Qt.AlignCenter)
        
        self.icon_lbl = QLabel(icon_char, self)
        self.icon_lbl.setStyleSheet("color: inherit; font-size: 16px; background: transparent; font-weight: normal;")
        self.btn_layout.addWidget(self.icon_lbl)
        
        self.text_lbl = QLabel(name, self)
        self.text_lbl.setStyleSheet("color: inherit; font-size: 12px; background: transparent;")
        self.text_lbl.setVisible(False)
        self.btn_layout.addWidget(self.text_lbl)
        
        self.btn_layout.addStretch()
        
        self.badge_lbl = QLabel("", self)
        self.badge_lbl.setStyleSheet("""
            background-color: #C8AA6E;
            color: #0A1428;
            font-size: 9px;
            font-weight: bold;
            border-radius: 6px;
            padding-left: 4px;
            padding-right: 4px;
            min-width: 12px;
            height: 12px;
        """)
        self.badge_lbl.setAlignment(Qt.AlignCenter)
        self.badge_lbl.setVisible(False)
        self.btn_layout.addWidget(self.badge_lbl)
        
        self.setProperty("active", "false")

    def set_active(self, active):
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_badge_value(self, val):
        if val:
            self.badge_lbl.setText(str(val))
            # Only show badge if expanded or if it's the ARAM priority Sniper or Friends list
            # We can allow the badge to overlap or only show in expanded mode
            self.badge_lbl.setVisible(self.text_lbl.isVisible())
        else:
            self.badge_lbl.setText("")
            self.badge_lbl.setVisible(False)

    def set_expanded_state(self, expanded):
        self.text_lbl.setVisible(expanded)
        self.badge_lbl.setVisible(expanded and bool(self.badge_lbl.text()))
        if expanded:
            self.btn_layout.setContentsMargins(12, 0, 12, 0)
            self.btn_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        else:
            self.btn_layout.setContentsMargins(0, 0, 0, 0)
            self.btn_layout.setAlignment(Qt.AlignCenter)


class SidebarNavigation(QWidget):
    """Modern collapsible navigation sidebar with animated resizing, sections, and badges."""
    
    def __init__(self, on_change_page, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarNav")
        self.on_change = on_change_page
        self.is_expanded = False
        
        # Start collapsed: 56px (icon only)
        self._width = 56
        self.setFixedWidth(self._width)
        
        self.setStyleSheet(f"""
            QWidget#sidebarNav {{
                background-color: #0A1428;
                border-right: 1px solid #1A2332;
            }}
            QPushButton {{
                border: none;
                color: #6C757D;
                background-color: transparent;
                margin-left: 6px;
                margin-right: 6px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                color: #F0E6D2;
                background-color: #1C2630;
            }}
            QPushButton[active="true"] {{
                color: #C8AA6E;
                background-color: #0F1923;
                border-left: 2px solid #C8AA6E;
            }}
            QPushButton:focus {{
                border: 1px solid #C8AA6E;
            }}
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 5, 0, 10)
        self.layout.setSpacing(6)
        
        # ── 1. COLLAPSE TOGGLE BUTTON ROW ──
        self.toggle_row = QWidget(self)
        self.toggle_row_layout = QHBoxLayout(self.toggle_row)
        self.toggle_row_layout.setContentsMargins(10, 0, 10, 0)
        self.toggle_row_layout.addStretch()
        
        self.btn_toggle_expand = QPushButton("▶", self)
        self.btn_toggle_expand.setFixedSize(24, 24)
        self.btn_toggle_expand.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_expand.setStyleSheet("""
            QPushButton {
                border: none;
                color: #6C757D;
                font-size: 12px;
                background-color: transparent;
            }
            QPushButton:hover {
                color: #F0E6D2;
            }
        """)
        self.btn_toggle_expand.clicked.connect(self.toggle_expand)
        self.toggle_row_layout.addWidget(self.btn_toggle_expand)
        
        self.layout.addWidget(self.toggle_row)
        
        # Organize navigation items in categories
        self.CATEGORIES = {
            "CORE": [
                ("Dashboard", "🏠", 1),
                ("Play", "🎮", 0),
            ],
            "AUTOMATION": [
                ("Champions", "⚔️", 3),
                ("Friends", "👥", 2),
                ("AI Coach", "🧠", 4),
            ],
            "SYSTEM": [
                ("Settings", "⚙️", 5),
            ]
        }
        
        self.buttons = []
        self.headers = []
        
        # Create categories and nav buttons
        for category_name, items in self.CATEGORIES.items():
            # Category label (only visible when expanded)
            lbl_header = QLabel(category_name, self)
            lbl_header.setStyleSheet("""
                color: #565C64;
                font-size: 9px;
                font-weight: bold;
                margin-left: 12px;
                margin-top: 8px;
                margin-bottom: 2px;
                background: transparent;
            """)
            lbl_header.setVisible(False)
            self.layout.addWidget(lbl_header)
            self.headers.append(lbl_header)
            
            for name, icon_char, page_index in items:
                btn = NavButton(name, icon_char, page_index, self)
                btn.setToolTip(name)
                btn.clicked.connect(lambda checked=False, idx=page_index: self._on_btn_clicked(idx))
                self.layout.addWidget(btn)
                self.buttons.append(btn)
        
        self.layout.addStretch()
        
        # Add thin gold divider line
        self.divider = QFrame(self)
        self.divider.setFixedHeight(1)
        self.divider.setStyleSheet("background-color: #1E2328; border: none; margin-left: 10px; margin-right: 10px;")
        self.layout.addWidget(self.divider)
        
        # Power label
        self.lbl_power = QLabel("AUTO", self)
        self.lbl_power.setAlignment(Qt.AlignCenter)
        self.lbl_power.setStyleSheet("color: #6C757D; font-size: 8px; font-weight: bold; background: transparent;")
        self.lbl_power.setVisible(False)
        self.layout.addWidget(self.lbl_power)
        
        # main power toggle
        from ui.qt.pages.settings_page import QtLolToggle
        self.toggle_power = QtLolToggle(
            self,
            active_color="#A88A4E",
            inactive_color="#1E2328",
            knob_color="#F0E6D2"
        )
        self.toggle_power.setChecked(True)
        self.toggle_power.clicked.connect(self._on_power_toggled)
        self.layout.addWidget(self.toggle_power, alignment=Qt.AlignCenter)
        
        # Width Animation
        self.anim = QPropertyAnimation(self, b"sidebar_width", self)
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        # EventBus listeners
        EventBus.on("friends_state_changed", self._on_friends_state_changed)
        EventBus.on("setting_changed", self._on_setting_changed)
        EventBus.on("automation_queue_state", self._on_queue_state)
        
        # Initial active page
        self.set_active(0)
        
        # Update badges after load
        QTimer.singleShot(100, self.update_badges)

    @Property(int)
    def sidebar_width(self):
        return self._width

    @sidebar_width.setter
    def sidebar_width(self, w):
        self._width = w
        self.setFixedWidth(w)

    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        self.anim.stop()
        
        start_w = self.width()
        target_w = 160 if self.is_expanded else 56
        
        # Chevron state
        self.btn_toggle_expand.setText("◀" if self.is_expanded else "▶")
        
        # Hide/Show header/power elements immediately
        for header in self.headers:
            header.setVisible(self.is_expanded)
        self.lbl_power.setVisible(self.is_expanded)
        
        # Update buttons
        for btn in self.buttons:
            btn.set_expanded_state(self.is_expanded)
            
        # Update tooltip visibility (disable tooltips when expanded to prevent clutter)
        for btn in self.buttons:
            btn.setToolTip("" if self.is_expanded else btn.name)
            
        # Animate width transition
        self.anim.setStartValue(start_w)
        self.anim.setEndValue(target_w)
        self.anim.start()
        
        # Refresh badges to render correctly in expanded mode
        self.update_badges()

    def _on_power_toggled(self):
        state = self.toggle_power.isChecked()
        app_win = self.window()
        if hasattr(app_win, "ctk_app") and app_win.ctk_app:
            app_win.ctk_app.toggle_power(state)
            
        from ui.qt.widgets.toast import ToastManager
        if state:
            ToastManager.get_instance().show("Automation Activated", icon="▶", theme="success")
        else:
            ToastManager.get_instance().show("Automation Paused", icon="⏸", theme="error")

    def _on_btn_clicked(self, page_index):
        self.set_active(page_index)
        self.on_change(page_index)

    def set_active(self, page_index):
        for btn in self.buttons:
            btn.set_active(btn.page_index == page_index)

    # ── Thread-Safe Reactive Badge Updates ──
    def update_badges(self):
        # 1. Update online friends count
        try:
            from services.friend_service import get_friend_service
            friends = get_friend_service().get_friends()
            online_count = sum(1 for f in friends if f.get("availability", "offline") != "offline")
            for btn in self.buttons:
                if btn.name == "Friends":
                    btn.set_badge_value(online_count if online_count > 0 else "")
        except Exception as e:
            Logger.error("SidebarNavigation", f"Badge error (Friends): {e}")

        # 2. Update priority grid size
        try:
            from services.settings_service import get_settings_service
            champions = get_settings_service().get("priority_picker", {}).get("list", [])
            for btn in self.buttons:
                if btn.name == "Champions":
                    btn.set_badge_value(len(champions) if len(champions) > 0 else "")
        except Exception as e:
            Logger.error("SidebarNavigation", f"Badge error (Champions): {e}")

    def update_queue_badge(self, phase):
        for btn in self.buttons:
            if btn.name == "Play":
                if phase == "Matchmaking":
                    btn.set_badge_value("●")
                else:
                    btn.set_badge_value("")

    def _on_friends_state_changed(self):
        QMetaObject.invokeMethod(self, "_update_friends_badge_async", Qt.QueuedConnection)

    @Slot()
    def _update_friends_badge_async(self):
        self.update_badges()

    def _on_setting_changed(self, key, val):
        if key == "priority_picker":
            QMetaObject.invokeMethod(self, "_update_champions_badge_async", Qt.QueuedConnection)

    @Slot()
    def _update_champions_badge_async(self):
        self.update_badges()

    def _on_queue_state(self, phase, state):
        QMetaObject.invokeMethod(self, "_update_queue_badge_async", Qt.QueuedConnection, Q_ARG(str, phase))

    @Slot(str)
    def _update_queue_badge_async(self, phase):
        self.update_queue_badge(phase)


class LeagueLoopQtWindow(QMainWindow):
    """The primary PySide6 application window container."""
    def __init__(self, ctk_app=None):
        super().__init__()
        self.ctk_app = ctk_app
        self.assets = ctk_app.assets if ctk_app else None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        self.setMinimumSize(300, 520)
        self.resize(300, 520)
        
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        # Outer Layout
        self.outer_layout = QVBoxLayout(self.central_widget)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)
        
        # Add Custom Title Bar
        self.title_bar = CustomTitleBar(self)
        self.outer_layout.addWidget(self.title_bar)
        
        # Main Body (Sidebar + Content Stack)
        self.body_widget = QWidget(self)
        self.body_layout = QHBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        
        self.navigation = SidebarNavigation(self.switch_page, self)
        self.body_layout.addWidget(self.navigation)
        
        self.pages_stack = QStackedWidget(self)
        self.body_layout.addWidget(self.pages_stack)
        
        self.outer_layout.addWidget(self.body_widget)
        
        # Add Status Bar
        self.status_bar = StatusBar(self)
        self.outer_layout.addWidget(self.status_bar)
        
        # Setup Pages (Placeholder pages for now)
        self.setup_pages()
        
        # Set QSS Style
        apply_theme(self)
        
        # Register with WindowService
        self._win_service = get_window_service()
        self._win_service.register_window(
            int(self.winId()),
            self.on_geometry_updated,
            self.on_state_updated
        )
        
        # Initialize Toast Manager overlay
        from ui.qt.widgets.toast import ToastManager
        self._toast_manager = ToastManager.get_instance(self)
        
        # Handle custom window focus styling
        self.setFocusPolicy(Qt.StrongFocus)

    def setup_pages(self):
        # Create Page Shells
        from ui.qt.pages import PlayPage
        self.play_page = PlayPage(self)
        self.pages_stack.addWidget(self.play_page)
        
        from ui.qt.pages import DashboardPage
        self.dashboard_page = DashboardPage(self)
        self.pages_stack.addWidget(self.dashboard_page)
        
        from ui.qt.pages import FriendsPage
        self.friends_page = FriendsPage(self)
        self.pages_stack.addWidget(self.friends_page)
        
        from ui.qt.pages import ChampionsPage
        self.champions_page = ChampionsPage(self)
        self.pages_stack.addWidget(self.champions_page)
        
        self.coach_page = QWidget()
        l = QVBoxLayout(self.coach_page)
        l.addWidget(QLabel("AI Coach Screen"))
        self.pages_stack.addWidget(self.coach_page)
        
        from ui.qt.pages import SettingsPage
        self.settings_page = SettingsPage(self)
        self.pages_stack.addWidget(self.settings_page)

    def switch_page(self, index):
        target_widget = self.pages_stack.widget(index)
        if not target_widget:
            return
            
        self.pages_stack.setCurrentIndex(index)
        
        # Apply smooth fade transition
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        target_widget.setGraphicsEffect(None)  # Reset any existing effect
        
        eff = QGraphicsOpacityEffect(target_widget)
        target_widget.setGraphicsEffect(eff)
        
        anim = QPropertyAnimation(eff, b"opacity", target_widget)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()

    @Slot(int, int, int, int)
    def on_geometry_updated(self, x, y, w, h):
        """Callback from WindowService to update position to snap to League Client."""
        # Use invokeMethod style to ensure safe execution on the Qt event loop thread
        self.setGeometry(x, y, w, h)

    @Slot(str)
    def on_state_updated(self, state_action):
        """Callback from WindowService to synchronize visibility and topmost status."""
        if state_action == "minimize":
            self.showMinimized()
        elif state_action == "restore":
            self.showNormal()
            self.raise_()
        elif state_action == "topmost_on":
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.show()
        elif state_action == "topmost_off":
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()

    def closeEvent(self, event):
        # Unregister window on close
        self._win_service.unregister_window(int(self.winId()))
        event.accept()
