"""
PySide6 Main Window Shell
Implements custom Riot-inspired window chrome, sidebar layout, page navigation, and integrates with WindowService.
"""
import sys
from PySide6.QtCore import Qt, QSize, Signal, Slot
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


class SidebarNavigation(QWidget):
    """Icon-based navigation panel for switching screens."""
    def __init__(self, on_change_page, parent=None):
        super().__init__(parent)
        self.on_change = on_change_page
        self.setFixedWidth(50)
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #0A1428;
                border-right: 1px solid #1A2332;
            }}
            QPushButton {{
                border: none;
                color: #6C757D;
                font-size: 16px;
                padding: 10px;
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
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 10, 0, 10)
        self.layout.setSpacing(8)
        
        self.buttons = []
        self._add_nav_item("Play", "🎮", 0)
        self._add_nav_item("Dashboard", "🏠", 1)
        self._add_nav_item("Friends", "👥", 2)
        self._add_nav_item("Champions", "⚔️", 3)
        self._add_nav_item("AI Coach", "🧠", 4)
        self._add_nav_item("Settings", "⚙️", 5)
        
        self.layout.addStretch()
        self.set_active(0)

    def _add_nav_item(self, name, icon_text, index):
        btn = QPushButton(icon_text, self)
        btn.setToolTip(name)
        btn.setProperty("active", "false")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._on_btn_clicked(index))
        self.layout.addWidget(btn)
        self.buttons.append(btn)

    def _on_btn_clicked(self, index):
        self.set_active(index)
        self.on_change(index)

    def set_active(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)


class LeagueLoopQtWindow(QMainWindow):
    """The primary PySide6 application window container."""
    def __init__(self):
        super().__init__()
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
        self.play_page = QWidget()
        l = QVBoxLayout(self.play_page)
        l.addWidget(QLabel("Play Area / Automation Controls"))
        self.pages_stack.addWidget(self.play_page)
        
        self.dashboard_page = QWidget()
        l = QVBoxLayout(self.dashboard_page)
        l.addWidget(QLabel("Dashboard Screen"))
        self.pages_stack.addWidget(self.dashboard_page)
        
        self.friends_page = QWidget()
        l = QVBoxLayout(self.friends_page)
        l.addWidget(QLabel("Friends Activity & Auto-Join"))
        self.pages_stack.addWidget(self.friends_page)
        
        self.champions_page = QWidget()
        l = QVBoxLayout(self.champions_page)
        l.addWidget(QLabel("Champions Overview & Win Rates"))
        self.pages_stack.addWidget(self.champions_page)
        
        self.coach_page = QWidget()
        l = QVBoxLayout(self.coach_page)
        l.addWidget(QLabel("AI Coach Screen"))
        self.pages_stack.addWidget(self.coach_page)
        
        from ui.qt.pages import SettingsPage
        self.settings_page = SettingsPage(self)
        self.pages_stack.addWidget(self.settings_page)

    def switch_page(self, index):
        self.pages_stack.setCurrentIndex(index)

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
