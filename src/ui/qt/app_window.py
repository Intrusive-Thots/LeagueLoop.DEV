"""
PySide6 Main Window Shell
Implements custom Riot-inspired window chrome, top-tab navigation (Version One style), and integrates with WindowService.
"""
import sys
import threading
import urllib.request
from PySide6.QtCore import Qt, QSize, Signal, Slot, Property, QPropertyAnimation, QEasingCurve, QTimer, QMetaObject, Q_ARG, QObject
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QSizePolicy, QDialog
)
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap

from services.window_service import get_window_service
from services.league_service import get_league_service
from services.settings_service import get_settings_service
from ui.qt.theme import apply_theme, get_theme_color
from ui.qt.widgets.icons import RiotIconWidget
from core.events import EventBus
from utils.logger import Logger


from ui.qt.widgets.navigation.header import HeaderBar


# ─────────────────────────────────────────────
# STATUS BAR
# ─────────────────────────────────────────────

class StatusBar(QFrame):
    """Bottom status bar displaying LCU connection state and mode, containing the power toggle."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setObjectName("statusBarFrame")
        self.setStyleSheet("""
            QFrame#statusBarFrame {
                background-color: #080E18;
                border-top: 1px solid #142236;
            }
            QLabel {
                color: #C8AA6E;
                font-size: 11px;
                font-family: "Inter", sans-serif;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        self.lbl_status = QLabel("● Disconnected", self)
        self.lbl_status.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        self.lbl_mode = QLabel("ARAM Mode", self)
        self.lbl_mode.setStyleSheet("color: #A0A5B5; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.lbl_mode)

        from ui.qt.widgets.inputs import QtLolToggle
        self.toggle_power = QtLolToggle(
            self,
            active_color="#A88A4E",
            inactive_color="#142236",
            knob_color="#F0E6D2"
        )
        self.toggle_power.setChecked(True)
        self.toggle_power.clicked.connect(self._on_power_toggled)
        layout.addWidget(self.toggle_power)

        from ui.qt.viewmodels.app_viewmodel import AppViewModel
        self.viewmodel = AppViewModel(self)

        self.viewmodel.league_connected.connect(self._on_connected)
        self.viewmodel.league_disconnected.connect(self._on_disconnected)
        self.viewmodel.queue_state_changed.connect(self._on_queue_state)

    def _connected_async(self):
        self.lbl_status.setText("● Connected to LCU")
        self.lbl_status.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 11px;")

    def _on_connected(self):
        QMetaObject.invokeMethod(self, "_connected_async", Qt.QueuedConnection)

    def _disconnected_async(self):
        self.lbl_status.setText("● Disconnected")
        self.lbl_status.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 11px;")

    def _on_disconnected(self):
        QMetaObject.invokeMethod(self, "_disconnected_async", Qt.QueuedConnection)

    def _on_queue_state(self, phase, search_state):
        mode_str = self.viewmodel.get_mode_string()
        self.lbl_mode.setText(mode_str)

    def _on_power_toggled(self):
        state = self.toggle_power.isChecked()
        self.viewmodel.toggle_power(state)

        from ui.qt.widgets.toast import ToastManager
        toast = ToastManager.get_instance()
        if toast:
            if state:
                toast.show("Automation Activated", icon="▶", theme="success")
            else:
                toast.show("Automation Paused", icon="⏸", theme="error")


# ─────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────

class LeagueLoopQtWindow(QMainWindow):
    """The primary PySide6 application window container with Version One top-tab navigation."""
    def __init__(self, ctk_app=None):
        super().__init__()
        self.ctk_app = ctk_app

        # Load singletons directly, independent of ctk_app
        self.config = get_settings_service()

        from services.asset_manager import get_asset_manager
        self.assets = get_asset_manager()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # No sidebar → full width goes to content. Clean 420px like V1.
        self.setMinimumSize(380, 600)
        self.resize(420, 640)

        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("centralWidget")
        self.central_widget.setStyleSheet("QWidget#centralWidget { background-color: #080E18; }")
        self.setCentralWidget(self.central_widget)

        self.outer_layout = QVBoxLayout(self.central_widget)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)

        self.header_bar = HeaderBar(self)
        self.outer_layout.addWidget(self.header_bar)

        # Page stack (no sidebar, full width)
        self.pages_stack = QStackedWidget(self)
        self.pages_stack.setObjectName("pagesStack")
        self.pages_stack.setStyleSheet("QStackedWidget#pagesStack { background-color: #080E18; }")
        self.outer_layout.addWidget(self.pages_stack)

        self.status_bar = StatusBar(self)
        self.outer_layout.addWidget(self.status_bar)

        self.setup_pages()
        apply_theme(self)

        self._win_service = get_window_service()
        self._win_service.register_window(
            int(self.winId()),
            self.on_geometry_updated,
            self.on_state_updated
        )

        self._setup_toast_overlay()
        self._tray_icon = None
        self._setup_tray_icon()

    def _setup_toast_overlay(self):
        try:
            from ui.qt.widgets.toast import ToastManager
            ToastManager.get_instance(self)
        except Exception as e:
            Logger.error("WindowShell", f"Failed to attach ToastManager: {e}")

    def _setup_tray_icon(self):
        try:
            from PySide6.QtWidgets import QSystemTrayIcon, QMenu
            from PySide6.QtGui import QAction, QIcon

            if not QSystemTrayIcon.isSystemTrayAvailable():
                return

            icon = QIcon("assets/app_icon.ico") if getattr(sys, 'frozen', False) else QIcon()
            self._tray_icon = QSystemTrayIcon(icon, self)

            tray_menu = QMenu()
            show_action = QAction("Show Window", self)
            show_action.triggered.connect(self.showNormal)
            tray_menu.addAction(show_action)

            quit_action = QAction("Exit LeagueLoop", self)
            quit_action.triggered.connect(QApplication.quit)
            tray_menu.addAction(quit_action)

            self._tray_icon.setContextMenu(tray_menu)
            self._tray_icon.activated.connect(self._on_tray_activated)
            self._tray_icon.show()
        except Exception as e:
            Logger.error("WindowShell", f"System Tray initialization failed: {e}")

    def _on_tray_activated(self, reason):
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.raise_()

    def setup_pages(self):
        """4-tab Version One layout: Play, Automations, Config, Misc."""
        from ui.qt.pages.play_page import PlayPage
        from ui.qt.pages.automations_page import AutomationsPage
        from ui.qt.pages.champions_page import ChampionsPage
        from ui.qt.pages.settings_page import SettingsPage

        self.page_classes = [
            PlayPage,          # Index 0 (Play)
            AutomationsPage,   # Index 1 (Automations)
            ChampionsPage,     # Index 2 (Config)
            SettingsPage,      # Index 3 (Misc)
        ]

        self.page_instances = [None] * len(self.page_classes)
        for i in range(len(self.page_classes)):
            placeholder = QWidget()
            self.pages_stack.addWidget(placeholder)

        self.switch_page(0)

    @property
    def play_page(self):
        return self.page_instances[0]

    @property
    def automations_page(self):
        return self.page_instances[1]

    @property
    def champions_page(self):
        return self.page_instances[2]

    @property
    def settings_page(self):
        return self.page_instances[3]

    # Legacy compatibility aliases
    @property
    def dashboard_page(self):
        return self.page_instances[0]  # Play is the new dashboard

    @property
    def accounts_page(self):
        return self.page_instances[4]  # Settings contains accounts

    def switch_page(self, index):
        if index < 0 or index >= len(self.page_classes):
            return

        if self.page_instances[index] is None:
            try:
                creator = self.page_classes[index]
                instance = creator(self)
                self.page_instances[index] = instance

                placeholder = self.pages_stack.widget(index)
                self.pages_stack.insertWidget(index, instance)
                self.pages_stack.removeWidget(placeholder)
                placeholder.deleteLater()
            except Exception as e:
                Logger.error("WindowShell", f"Error lazy loading page index {index}: {e}")
                error_widget = QWidget()
                l = QVBoxLayout(error_widget)
                lbl = QLabel(f"⚠️ Failed to load page: {e}\nPlease check logs.")
                lbl.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 11px;")
                l.addWidget(lbl)
                self.pages_stack.insertWidget(index, error_widget)
                return

        target_widget = self.pages_stack.widget(index)
        if not target_widget:
            return

        self.pages_stack.setCurrentIndex(index)

        # Update tab highlights
        if hasattr(self, "header_bar") and self.header_bar:
            self.header_bar.set_active_tab(index)

        # Fade-in transition
        if self.isVisible():
            from PySide6.QtWidgets import QGraphicsOpacityEffect
            target_widget.setGraphicsEffect(None)

            eff = QGraphicsOpacityEffect(target_widget)
            target_widget.setGraphicsEffect(eff)

            self._page_anim = QPropertyAnimation(eff, b"opacity", target_widget)
            self._page_anim.setDuration(150)
            self._page_anim.setStartValue(0.0)
            self._page_anim.setEndValue(1.0)
            self._page_anim.finished.connect(lambda: target_widget.setGraphicsEffect(None))
            self._page_anim.start()
        else:
            target_widget.setGraphicsEffect(None)

    @Slot(int, int, int, int)
    def on_geometry_updated(self, x, y, w, h):
        self.setGeometry(x, y, w, h)

    @Slot(str)
    def on_state_updated(self, state_action):
        if state_action == "minimize":
            self.showMinimized()
        elif state_action == "restore":
            self.showNormal()
            self.raise_()
        elif state_action == "topmost_on":
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
        elif state_action == "topmost_off":
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.show()

    def closeEvent(self, event):
        if self.config and self.config.get("run_in_tray", True):
            self.hide()
            if self._tray_icon:
                self._tray_icon.show()
            event.ignore()
        else:
            self._win_service.unregister_window(int(self.winId()))
            if self._tray_icon:
                self._tray_icon.hide()
            event.accept()
