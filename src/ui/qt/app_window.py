"""
PySide6 Main Window Shell
Implements custom Riot-inspired window chrome, vector sidebar layout, page navigation, and integrates with WindowService.
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


class HeaderBar(QWidget):
    """Custom premium title bar supporting dragging, status displays, and controls."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(40)
        self.setObjectName("headerBarFrame")
        
        self.setStyleSheet("""
            QWidget#headerBarFrame {
                background-color: #080E18;
                border-bottom: 1px solid #142236;
            }
            QLabel {
                font-family: "Inter", sans-serif;
                background: transparent;
            }
            QPushButton {
                border: none;
                background-color: transparent;
                padding: 0px;
                margin: 0px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #142236;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)
        
        # 1. Logo Icon & App Title
        self.logo_icon = RiotIconWidget("play", size=16, color="#C8AA6E", parent=self)
        layout.addWidget(self.logo_icon)
        
        self.logo_lbl = QLabel("League Loop", self)
        self.logo_lbl.setStyleSheet("font-weight: bold; color: #C8AA6E; font-size: 12px;")
        layout.addWidget(self.logo_lbl)
        
        # 2. Active Page Title
        self.page_title_lbl = QLabel("|  Play", self)
        self.page_title_lbl.setStyleSheet("color: #F0E6D2; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.page_title_lbl)
        
        layout.addStretch()
        
        # 3. Queue Timer Badge
        self.timer_lbl = QLabel("⏳ 0:00", self)
        self.timer_lbl.setStyleSheet("color: #C8AA6E; font-size: 11px; font-weight: bold; background: #0E1A2E; padding: 2px 8px; border-radius: 4px; border: 1px solid #1E2D42;")
        self.timer_lbl.setVisible(False)
        layout.addWidget(self.timer_lbl)
        
        # 4. Profile Badge
        self.profile_lbl = QLabel("", self)
        self.profile_lbl.setStyleSheet("color: #C8AA6E; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.profile_lbl)
        
        # 5. Hotkey Badge
        self.hotkey_badge = QLabel("F3 Queue", self)
        self.hotkey_badge.setStyleSheet("color: #A0A5B5; font-size: 10px; padding: 3px 8px; border: 1px solid #1C2B3E; border-radius: 4px; background-color: #0A1424;")
        layout.addWidget(self.hotkey_badge)
        
        # 6. Settings Gear Button
        self.btn_settings = QPushButton(self)
        self.btn_settings.setFixedSize(26, 26)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setToolTip("Settings")
        btn_set_layout = QHBoxLayout(self.btn_settings)
        btn_set_layout.setContentsMargins(4, 4, 4, 4)
        btn_set_layout.addWidget(RiotIconWidget("settings", size=16, color="#A0A5B5", parent=self.btn_settings))
        self.btn_settings.clicked.connect(lambda: self.parent.switch_page(5))
        layout.addWidget(self.btn_settings)
        
        # 7. Dock Toggle
        self.btn_dock = QPushButton(self)
        self.btn_dock.setFixedSize(26, 26)
        self.btn_dock.setCursor(Qt.PointingHandCursor)
        btn_dock_layout = QHBoxLayout(self.btn_dock)
        btn_dock_layout.setContentsMargins(4, 4, 4, 4)
        self.dock_icon_widget = RiotIconWidget("dock", size=16, color="#C8AA6E", parent=self.btn_dock)
        btn_dock_layout.addWidget(self.dock_icon_widget)
        self.btn_dock.clicked.connect(self._toggle_dock)
        layout.addWidget(self.btn_dock)
        
        # 8. Minimize Button
        self.btn_min = QPushButton(self)
        self.btn_min.setFixedSize(26, 26)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        btn_min_layout = QHBoxLayout(self.btn_min)
        btn_min_layout.setContentsMargins(4, 4, 4, 4)
        btn_min_layout.addWidget(RiotIconWidget("minimize", size=16, color="#C8AA6E", parent=self.btn_min))
        self.btn_min.clicked.connect(self.parent.showMinimized)
        layout.addWidget(self.btn_min)
        
        # 9. Close Button
        self.btn_close = QPushButton(self)
        self.btn_close.setFixedSize(26, 26)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        btn_close_layout = QHBoxLayout(self.btn_close)
        btn_close_layout.setContentsMargins(4, 4, 4, 4)
        btn_close_layout.addWidget(RiotIconWidget("close", size=16, color="#E74C3C", parent=self.btn_close))
        self.btn_close.clicked.connect(self.parent.close)
        layout.addWidget(self.btn_close)
        
        self._drag_position = None
        self._window_service = get_window_service()
        self._update_dock_icon()
        
        EventBus.on("queue_timer_tick", self._on_timer_tick)
        EventBus.on("automation_queue_state", self._on_queue_state)
        EventBus.on("summoner_changed", self._on_summoner_changed)
        EventBus.on("league_disconnected", self._on_league_disconnected)
        
    def set_page_title(self, name):
        self.page_title_lbl.setText(f"|  {name}")
        
    def _toggle_dock(self):
        is_docked = self._window_service.is_docked
        self._window_service.set_docked_mode(not is_docked)
        self._update_dock_icon()
        
    def _update_dock_icon(self):
        is_docked = self._window_service.is_docked
        self.btn_dock.setToolTip("Docked Mode (Snaps to League)" if is_docked else "Undocked Mode (Free Window)")
        
    def _on_timer_tick(self, current, estimated):
        cur_min, cur_sec = divmod(int(current), 60)
        est_min, est_sec = divmod(int(estimated), 60)
        text = f"⏳ {cur_min}:{cur_sec:02d} / {est_min}:{est_sec:02d}"
        QMetaObject.invokeMethod(self.timer_lbl, "setText", Qt.QueuedConnection, Q_ARG(str, text))
        
    def _on_queue_state(self, phase, search_state):
        is_searching = phase in ["Matchmaking"] or (search_state and search_state.get("isSearching", False))
        QMetaObject.invokeMethod(self.timer_lbl, "setVisible", Qt.QueuedConnection, Q_ARG(bool, bool(is_searching)))
        
    def _on_summoner_changed(self, info):
        if info:
            name = info.get("displayName", "")
            level = info.get("summonerLevel", 0)
            text = f"👤 {name} (Lv.{level})" if name else ""
            QMetaObject.invokeMethod(self.profile_lbl, "setText", Qt.QueuedConnection, Q_ARG(str, text))
            
    def _on_league_disconnected(self):
        QMetaObject.invokeMethod(self.profile_lbl, "setText", Qt.QueuedConnection, Q_ARG(str, ""))
        QMetaObject.invokeMethod(self.timer_lbl, "setVisible", Qt.QueuedConnection, Q_ARG(bool, False))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_position and not self._window_service.is_docked:
            self.parent.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()


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
        
        from ui.qt.pages.settings_page import QtLolToggle
        self.toggle_power = QtLolToggle(
            self,
            active_color="#A88A4E",
            inactive_color="#142236",
            knob_color="#F0E6D2"
        )
        self.toggle_power.setChecked(True)
        self.toggle_power.clicked.connect(self._on_power_toggled)
        layout.addWidget(self.toggle_power)
        
        EventBus.on("league_connected", self._on_connected)
        EventBus.on("league_disconnected", self._on_disconnected)
        EventBus.on("automation_queue_state", self._on_queue_state)
        
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
        app_win = self.window()
        mode_str = "Auto Mode"
        if app_win and hasattr(app_win, "ctk_app") and app_win.ctk_app:
            q_id = app_win.ctk_app.automation.current_queue_id
            if q_id == 450: mode_str = "ARAM Mode"
            elif q_id == 1900: mode_str = "Classic Mode"
            elif q_id == 420: mode_str = "Solo/Duo Mode"
            elif q_id == 440: mode_str = "Flex Mode"
            elif q_id == 400: mode_str = "Draft Mode"
            else:
                mode_str = f"{app_win.config.get('aram_mode', 'ARAM')} Mode"
        QMetaObject.invokeMethod(self.lbl_mode, "setText", Qt.QueuedConnection, Q_ARG(str, mode_str))

    def _on_power_toggled(self):
        state = self.toggle_power.isChecked()
        app_win = self.window()
        if app_win and hasattr(app_win, "ctk_app") and app_win.ctk_app:
            app_win.ctk_app.toggle_power(state)
            
        from ui.qt.widgets.toast import ToastManager
        if state:
            ToastManager.get_instance().show("Automation Activated", icon="▶", theme="success")
        else:
            ToastManager.get_instance().show("Automation Paused", icon="⏸", theme="error")


class NavButton(QPushButton):
    """Custom navigation button supporting text labels, vector icons, and centered alignment."""
    def __init__(self, name, icon_name, page_index, parent=None):
        super().__init__(parent)
        self.name = name
        self.icon_name = icon_name
        self.page_index = page_index
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedHeight(46)
        
        self.btn_layout = QHBoxLayout(self)
        self.btn_layout.setContentsMargins(12, 0, 12, 0)
        self.btn_layout.setSpacing(12)
        self.btn_layout.setAlignment(Qt.AlignCenter)
        
        self.icon_widget = RiotIconWidget(icon_name, size=18, color="#6C757D", parent=self)
        self.btn_layout.addWidget(self.icon_widget)
        
        self.text_lbl = QLabel(name, self)
        self.text_lbl.setStyleSheet("color: inherit; font-size: 12px; font-weight: 600; background: transparent;")
        self.text_lbl.setVisible(False)
        self.btn_layout.addWidget(self.text_lbl)
        
        self.btn_layout.addStretch()
        
        self.badge_lbl = QLabel("", self)
        self.badge_lbl.setStyleSheet("""
            background-color: #C8AA6E;
            color: #080E18;
            font-size: 9px;
            font-weight: bold;
            border-radius: 6px;
            padding-left: 4px;
            padding-right: 4px;
            min-width: 14px;
            height: 14px;
        """)
        self.badge_lbl.setAlignment(Qt.AlignCenter)
        self.badge_lbl.setVisible(False)
        self.btn_layout.addWidget(self.badge_lbl)
        
        self.setProperty("active", "false")

    def set_active(self, active):
        self.setProperty("active", "true" if active else "false")
        self.icon_widget.set_color("#C8AA6E" if active else "#6C757D")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_badge_value(self, val):
        if val:
            self.badge_lbl.setText(str(val))
            self.badge_lbl.setVisible(self.text_lbl.isVisible())
        else:
            self.badge_lbl.setText("")
            self.badge_lbl.setVisible(False)

    def set_expanded_state(self, expanded):
        self.text_lbl.setVisible(expanded)
        self.badge_lbl.setVisible(expanded and bool(self.badge_lbl.text()))
        if expanded:
            self.btn_layout.setContentsMargins(14, 0, 14, 0)
            self.btn_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        else:
            self.btn_layout.setContentsMargins(0, 0, 0, 0)
            self.btn_layout.setAlignment(Qt.AlignCenter)


class SidebarNavigation(QWidget):
    """Modern collapsible navigation sidebar with animated resizing and vector icons."""
    def __init__(self, on_change_page, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarNav")
        self.on_change = on_change_page
        self.is_expanded = False
        
        self._width = 64
        self.setFixedWidth(self._width)
        
        self.setStyleSheet("""
            QWidget#sidebarNav {
                background-color: #080E18;
                border-right: 1px solid #142236;
            }
            QPushButton {
                border: none;
                color: #6C757D;
                background-color: transparent;
                margin-left: 6px;
                margin-right: 6px;
                border-radius: 6px;
            }
            QPushButton:hover {
                color: #F0E6D2;
                background-color: #121F33;
            }
            QPushButton[active="true"] {
                color: #C8AA6E;
                background-color: #0F1A2A;
                border-left: 3px solid #C8AA6E;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 12, 0, 12)
        self.layout.setSpacing(8)
        
        # Expand toggle button
        self.toggle_row = QWidget(self)
        self.toggle_row_layout = QHBoxLayout(self.toggle_row)
        self.toggle_row_layout.setContentsMargins(14, 0, 14, 0)
        self.toggle_row_layout.addStretch()
        
        self.btn_toggle_expand = QPushButton(self)
        self.btn_toggle_expand.setFixedSize(24, 24)
        self.btn_toggle_expand.setCursor(Qt.PointingHandCursor)
        btn_exp_layout = QHBoxLayout(self.btn_toggle_expand)
        btn_exp_layout.setContentsMargins(2, 2, 2, 2)
        self.toggle_icon_widget = RiotIconWidget("chevron_right", size=16, color="#6C757D", parent=self.btn_toggle_expand)
        btn_exp_layout.addWidget(self.toggle_icon_widget)
        self.btn_toggle_expand.clicked.connect(self.toggle_expand)
        self.toggle_row_layout.addWidget(self.btn_toggle_expand)
        self.layout.addWidget(self.toggle_row)
        
        self.CATEGORIES = {
            "CORE": [
                ("Dashboard", "home", 1),
                ("Play", "play", 0),
                ("Predictor", "home", 7),
            ],
            "AUTOMATION": [
                ("Champions", "champions", 3),
                ("Friends", "friends", 2),
                ("AI Coach", "coach", 4),
                ("Patch Notes", "gear", 8),
            ],
            "SYSTEM": [
                ("Accounts", "gear", 6),
                ("Settings", "settings", 5),
            ]
        }
        
        self.buttons = []
        self.headers = []
        
        for category_name, items in self.CATEGORIES.items():
            lbl_header = QLabel(category_name, self)
            lbl_header.setStyleSheet("color: #4A5668; font-size: 9px; font-weight: bold; margin-left: 14px; margin-top: 8px; margin-bottom: 2px; background: transparent;")
            lbl_header.setVisible(False)
            self.layout.addWidget(lbl_header)
            self.headers.append(lbl_header)
            
            for name, icon_name, page_index in items:
                btn = NavButton(name, icon_name, page_index, self)
                btn.setToolTip(name)
                btn.clicked.connect(lambda checked=False, idx=page_index: self._on_btn_clicked(idx))
                self.layout.addWidget(btn)
                self.buttons.append(btn)
        
        self.layout.addStretch()
        
        self.anim = QPropertyAnimation(self, b"sidebar_width", self)
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        EventBus.on("friends_state_changed", self._on_friends_state_changed)
        EventBus.on("setting_changed", self._on_setting_changed)
        EventBus.on("automation_queue_state", self._on_queue_state)
        
        self.set_active(0)
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
        
        app_win = self.window()
        if app_win and hasattr(app_win, "anim_win"):
            app_win.anim_win.stop()
            
        start_w = self.width()
        target_w = 200 if self.is_expanded else 64
        
        self.toggle_icon_widget.set_icon("chevron_left" if self.is_expanded else "chevron_right")
        
        for header in self.headers:
            header.setVisible(self.is_expanded)
        
        for btn in self.buttons:
            btn.set_expanded_state(self.is_expanded)
            btn.setToolTip("" if self.is_expanded else btn.name)
            
        self.anim.setStartValue(start_w)
        self.anim.setEndValue(target_w)
        self.anim.start()
        
        if app_win and hasattr(app_win, "anim_win"):
            win_start_w = app_win.width()
            win_target_w = 580 if self.is_expanded else 450
            app_win.anim_win.setStartValue(win_start_w)
            app_win.anim_win.setEndValue(win_target_w)
            app_win.anim_win.start()
            
        self.update_badges()

    def _on_btn_clicked(self, page_index):
        self.set_active(page_index)
        self.on_change(page_index)

    def set_active(self, page_index):
        for btn in self.buttons:
            btn.set_active(btn.page_index == page_index)

    def update_badges(self):
        try:
            from services.friend_service import get_friend_service
            friends = get_friend_service().get_friends()
            online_count = sum(1 for f in friends if f.get("availability", "offline") != "offline")
            for btn in self.buttons:
                if btn.name == "Friends":
                    btn.set_badge_value(online_count if online_count > 0 else "")
        except Exception as e:
            Logger.error("SidebarNavigation", f"Badge error (Friends): {e}")

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
        self.config = ctk_app.config if ctk_app else None
        self.assets = ctk_app.assets if ctk_app else None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # Set clean default width (450px wide collapsed)
        self.setMinimumSize(420, 600)
        self.resize(450, 640)
        
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        self.outer_layout = QVBoxLayout(self.central_widget)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)
        
        self.header_bar = HeaderBar(self)
        self.outer_layout.addWidget(self.header_bar)
        
        self.anim_win = QPropertyAnimation(self, b"window_width", self)
        self.anim_win.setDuration(150)
        self.anim_win.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.body_widget = QWidget(self)
        self.body_layout = QHBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        
        self.navigation = SidebarNavigation(self.switch_page, self)
        self.body_layout.addWidget(self.navigation)
        
        self.pages_stack = QStackedWidget(self)
        self.body_layout.addWidget(self.pages_stack)
        
        self.outer_layout.addWidget(self.body_widget)
        
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
            import os
            
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
                
            icon_path = "assets/app.ico" if os.path.exists("assets/app.ico") else ("assets/app.png" if os.path.exists("assets/app.png") else "")
            icon = QIcon(icon_path) if icon_path else QIcon()
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
        from ui.qt.pages.play_page import PlayPage
        from ui.qt.pages.dashboard_page import DashboardPage
        from ui.qt.pages.friends_page import FriendsPage
        from ui.qt.pages.champions_page import ChampionsPage
        from ui.qt.pages.coach_page import CoachPage
        from ui.qt.pages.settings_page import SettingsPage
        from ui.qt.pages.accounts_page import AccountsPage
        from ui.qt.pages.match_predictor_page import MatchPredictorPage
        from ui.qt.pages.patch_notes_page import PatchNotesPage

        self.page_classes = [
            PlayPage,           # Index 0
            DashboardPage,      # Index 1
            FriendsPage,        # Index 2
            ChampionsPage,      # Index 3
            CoachPage,          # Index 4
            SettingsPage,       # Index 5
            AccountsPage,       # Index 6
            MatchPredictorPage, # Index 7
            PatchNotesPage,     # Index 8
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
    def dashboard_page(self):
        return self.page_instances[1]

    @property
    def friends_page(self):
        return self.page_instances[2]

    @property
    def champions_page(self):
        return self.page_instances[3]

    @property
    def coach_page(self):
        return self.page_instances[4]

    @property
    def settings_page(self):
        return self.page_instances[5]

    @property
    def accounts_page(self):
        return self.page_instances[6]

    def switch_page(self, index):
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
        
        if hasattr(self, "navigation") and self.navigation:
            self.navigation.set_active(index)
            
        if hasattr(self, "header_bar") and self.header_bar:
            page_name = self.page_classes[index].__name__.replace("Page", "")
            if page_name == "Coach":
                page_name = "AI Coach"
            self.header_bar.set_page_title(page_name)
        
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        target_widget.setGraphicsEffect(None)
        
        eff = QGraphicsOpacityEffect(target_widget)
        target_widget.setGraphicsEffect(eff)
        
        anim = QPropertyAnimation(eff, b"opacity", target_widget)
        anim.setDuration(150)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()

    @Slot(int, int, int, int)
    def on_geometry_updated(self, x, y, w, h):
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QTimer, QThread
            app_inst = QApplication.instance()
            if app_inst and QThread.currentThread() != app_inst.thread():
                QTimer.singleShot(0, lambda: self.setGeometry(x, y, w, h))
                return
        except Exception:
            pass
        self.setGeometry(x, y, w, h)

    @Slot(str)
    def on_state_updated(self, state_action):
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QTimer, QThread
            app_inst = QApplication.instance()
            if app_inst and QThread.currentThread() != app_inst.thread():
                QTimer.singleShot(0, lambda: self.on_state_updated(state_action))
                return
        except Exception:
            pass

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
        if self.config and self.config.get("run_in_tray", True) and self._tray_icon and self._tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self._win_service.unregister_window(int(self.winId()))
            if self._tray_icon:
                self._tray_icon.hide()
            event.accept()

    @Property(int)
    def window_width(self):
        return self.width()

    @window_width.setter
    def window_width(self, w):
        self.resize(w, self.height())
