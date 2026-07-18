"""
PySide6 Dashboard Page Component
Displays modular diagnostic widgets (LCU Connection, Game State, Friends Summary, Automation)
supporting custom drag-and-drop reordering.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QMetaObject, Slot, Q_ARG, Property, QPoint, QMimeData
from PySide6.QtGui import QColor, QFont, QDrag, QPixmap

from ui.qt.widgets import ScrollableList, make_card
from ui.qt.theme import get_theme_color, get_theme_radius
from services.league_service import get_league_service
from services.friend_service import get_friend_service
from services.settings_service import get_settings_service
from core.events import EventBus
from utils.logger import Logger


class DashboardWidget(QFrame):
    """Base styled card panel for dashboard modules supporting drag-and-drop reordering."""
    
    def __init__(self, parent_page, parent_widget=None, title="MODULE"):
        super().__init__(parent_widget)
        self.parent_page = parent_page
        self.setObjectName("dashboardWidget")
        self._drag_start_pos = None
        self.title_text = title
        
        # Sleek dark blue card styling
        border = get_theme_color("colors.border.subtle", "#1E2328")
        bg_card = get_theme_color("colors.background.card", "#141E28")
        self.setStyleSheet(f"""
            QFrame#dashboardWidget {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        # Gold header
        self.lbl_title = QLabel(title, self)
        gold = get_theme_color("colors.accent.gold", "#C8AA6E")
        self.lbl_title.setStyleSheet(f"color: {gold}; font-weight: bold; font-size: 11px; background: transparent;")
        layout.addWidget(self.lbl_title)
        
        # Divider line
        divider = QFrame(self)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {border}; border: none;")
        layout.addWidget(divider)
        
        # Content layout
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        self.content_layout.setSpacing(4)
        
        layout.addWidget(self.content_widget)

    def set_drag_over(self, active: bool):
        border = "#C8AA6E" if active else get_theme_color("colors.border.subtle", "#1E2328")
        bg_card = get_theme_color("colors.background.card", "#141E28")
        self.setStyleSheet(f"""
            QFrame#dashboardWidget {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_start_pos:
            if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
                return
            
            # Initiate drag reorder
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setData("application/x-dashboard-widget", self.title_text.encode("utf-8"))
            drag.setMimeData(mime_data)
            
            # Take a snapshot of the widget for the drag thumbnail
            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.position().toPoint())
            
            # Set target reference on page
            self.parent_page.dragged_module = self
            
            # Execute drag operation
            drag.exec(Qt.MoveAction)


class LcuAccountModule(DashboardWidget):
    """Shows summoner profile, name, level, and client connection metrics."""
    
    def __init__(self, parent_page, parent=None):
        super().__init__(parent_page, parent, title="LCU ACCOUNT")
        
        self.lbl_name = QLabel(" Summoner: Loading...", self)
        self.lbl_name.setStyleSheet("color: #F0E6D2; font-weight: bold; font-size: 12px;")
        self.content_layout.addWidget(self.lbl_name)
        
        self.lbl_level = QLabel(" Level: --", self)
        self.lbl_level.setStyleSheet("color: #A0A5B5; font-size: 11px;")
        self.content_layout.addWidget(self.lbl_level)
        
        self.lbl_status = QLabel(" LCU Connection: Disconnected", self)
        self.lbl_status.setStyleSheet("color: #E74C3C; font-size: 11px;")
        self.content_layout.addWidget(self.lbl_status)
        
        # Event bindings
        EventBus.on("league_connected", self._on_connected)
        EventBus.on("league_disconnected", self._on_disconnected)
        
        self.update_info()

    def update_info(self):
        lcu = get_league_service()
        if lcu and lcu.is_connected:
            self.lbl_status.setText(" LCU Connection: Connected")
            self.lbl_status.setStyleSheet("color: #2ECC71; font-size: 11px;")
            
            # Fetch details
            info = lcu.get_summoner_info() or {}
            name = info.get("displayName") or info.get("gameName") or "Summoner"
            level = info.get("summonerLevel") or "--"
            self.lbl_name.setText(f" Summoner: {name}")
            self.lbl_level.setText(f" Level: {level}")
        else:
            self.lbl_status.setText(" LCU Connection: Disconnected")
            self.lbl_status.setStyleSheet("color: #E74C3C; font-size: 11px;")
            self.lbl_name.setText(" Summoner: Unknown")
            self.lbl_level.setText(" Level: --")

    def _on_connected(self):
        QMetaObject.invokeMethod(self, "update_info", Qt.QueuedConnection)

    def _on_disconnected(self):
        QMetaObject.invokeMethod(self, "update_info", Qt.QueuedConnection)


class GameflowModule(DashboardWidget):
    """Tracks queue search states and active gameflow phases (e.g. Matchmaking)."""
    
    def __init__(self, parent_page, parent=None):
        super().__init__(parent_page, parent, title="GAME STATE")
        
        self.lbl_phase = QLabel("Phase: None", self)
        self.lbl_phase.setStyleSheet(f"color: {get_theme_color('colors.accent.primary', '#C8AA6E')}; font-weight: bold; font-size: 14px;")
        self.content_layout.addWidget(self.lbl_phase)
        
        self.lbl_action = QLabel("Idle and waiting...", self)
        self.lbl_action.setStyleSheet("color: #A0A5B5; font-size: 11px;")
        self.content_layout.addWidget(self.lbl_action)
        
        EventBus.on("automation_queue_state", self._on_queue_state)
        
        self.update_state("None")

    def update_state(self, phase, state=None):
        if not phase:
            phase = "None"
        self.lbl_phase.setText(f"Phase: {phase}")
        
        # Display descriptive actions
        if phase == "Matchmaking":
            self.lbl_action.setText("Searching for a match...")
            self.lbl_phase.setStyleSheet("color: #00A2FF; font-weight: bold; font-size: 14px;")
        elif phase == "ReadyCheck":
            self.lbl_action.setText("Match found! Auto-Accepting...")
            self.lbl_phase.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 14px;")
        elif phase == "ChampSelect":
            self.lbl_action.setText("Champion Select in progress.")
            self.lbl_phase.setStyleSheet("color: #E67E22; font-weight: bold; font-size: 14px;")
        elif phase == "InProgress":
            self.lbl_action.setText("In Game.")
            self.lbl_phase.setStyleSheet("color: #9B59B6; font-weight: bold; font-size: 14px;")
        else:
            self.lbl_action.setText("Idle and waiting...")
            self.lbl_phase.setStyleSheet(f"color: {get_theme_color('colors.accent.primary', '#C8AA6E')}; font-weight: bold; font-size: 14px;")

    def _on_queue_state(self, phase, state):
        QMetaObject.invokeMethod(self, "update_state", Qt.QueuedConnection, Q_ARG(str, phase))


class FriendsSummaryModule(DashboardWidget):
    """Summarizes online friends count and auto-join indicators."""
    
    def __init__(self, parent_page, parent=None):
        super().__init__(parent_page, parent, title="FRIENDS SUMMARY")
        
        self.lbl_count = QLabel("Online Friends: --", self)
        self.lbl_count.setStyleSheet("color: #F0E6D2; font-weight: bold; font-size: 12px;")
        self.content_layout.addWidget(self.lbl_count)
        
        self.lbl_auto_join = QLabel("Auto-Joins Enabled: 0", self)
        self.lbl_auto_join.setStyleSheet("color: #A0A5B5; font-size: 11px;")
        self.content_layout.addWidget(self.lbl_auto_join)
        
        EventBus.on("friends_state_changed", self._on_friends_updated)
        
        self.update_stats()

    def update_stats(self):
        friends = get_friend_service().get_friends()
        online_count = sum(1 for f in friends if f.get("availability", "offline") != "offline")
        self.lbl_count.setText(f"Online Friends: {online_count} / {len(friends)}")
        
        # Count auto-joins
        auto_joins = 0
        for f in friends:
            name = f.get("gameName", "") or f.get("name", "")
            name_lower = f.get("_name_lower", name.lower())
            if get_friend_service().get_auto_join_status(name_lower):
                auto_joins += 1
                
        self.lbl_auto_join.setText(f"Auto-Joins Enabled: {auto_joins}")

    def _on_friends_updated(self):
        QMetaObject.invokeMethod(self, "update_stats", Qt.QueuedConnection)


class AutomationModule(DashboardWidget):
    """Shows automation checklist options and ARAM priority list counts."""
    
    def __init__(self, parent_page, parent=None):
        super().__init__(parent_page, parent, title="AUTOMATION STATE")
        self.config = get_settings_service()
        
        self.lbl_status = QLabel("Automation: ACTIVE", self)
        self.lbl_status.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 12px;")
        self.content_layout.addWidget(self.lbl_status)
        
        self.lbl_aram = QLabel("ARAM Priority List: 0", self)
        self.lbl_aram.setStyleSheet("color: #A0A5B5; font-size: 11px;")
        self.content_layout.addWidget(self.lbl_aram)
        
        self.lbl_delay = QLabel("Accept Delay: 2.0s", self)
        self.lbl_delay.setStyleSheet("color: #A0A5B5; font-size: 11px;")
        self.content_layout.addWidget(self.lbl_delay)
        
        EventBus.on("settings_saved", self._on_settings_saved)
        
        self.update_settings()

    def update_settings(self):
        aram_list = self.config.get("priority_picker", {}).get("list", [])
        self.lbl_aram.setText(f"ARAM Priority List: {len(aram_list)} champs")
        
        delay = float(self.config.get("accept_delay", 2.0))
        self.lbl_delay.setText(f"Accept Delay: {delay:.1f}s")
        
        root = self.window()
        if hasattr(root, "navigation") and hasattr(root.navigation, "toggle_power"):
            is_active = root.navigation.toggle_power.isChecked()
            if is_active:
                self.lbl_status.setText("Automation: ACTIVE")
                self.lbl_status.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 12px;")
            else:
                self.lbl_status.setText("Automation: PAUSED")
                self.lbl_status.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 12px;")

    def _on_settings_saved(self):
        QMetaObject.invokeMethod(self, "update_settings", Qt.QueuedConnection)


class DashboardPage(QWidget):
    """The main Dashboard Page displaying modular diagnostic cards supporting reorderable drag drop."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.dragged_module = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Page Card Header
        self.card = make_card(self, title="LEAGUELOOP DASHBOARD")
        layout.addWidget(self.card.parentWidget())
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(10)
        
        # Grid layout for modular widgets
        self.grid_widget = QWidget(self.card)
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        
        # Instantiate modules
        self.account_module = LcuAccountModule(self, self.grid_widget)
        self.gameflow_module = GameflowModule(self, self.grid_widget)
        self.friends_module = FriendsSummaryModule(self, self.grid_widget)
        self.auto_module = AutomationModule(self, self.grid_widget)
        
        self.modules = [
            self.account_module,
            self.gameflow_module,
            self.friends_module,
            self.auto_module
        ]
        
        # Initial grid population
        self.rebuild_grid()
        card_layout.addWidget(self.grid_widget)

    def rebuild_grid(self):
        # Clear existing layout items
        while self.grid.count() > 0:
            self.grid.takeAt(0)
            
        # Place 4 modules in 2x2 layout
        for i, module in enumerate(self.modules):
            row = i // 2
            col = i % 2
            self.grid.addWidget(module, row, col)

    def swap_modules(self, module_a, module_b):
        if module_a not in self.modules or module_b not in self.modules:
            return
        idx_a = self.modules.index(module_a)
        idx_b = self.modules.index(module_b)
        
        # Swap slots
        self.modules[idx_a], self.modules[idx_b] = self.modules[idx_b], self.modules[idx_a]
        self.rebuild_grid()

    def find_module_at(self, local_pos):
        # Map target coordinates from card spacing to grid widget bounds
        grid_pos = self.grid_widget.mapFrom(self.card, local_pos)
        for module in self.modules:
            if module.geometry().contains(grid_pos):
                return module
        return None

    # ── Drag & Drop Event Overrides ──
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-dashboard-widget"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-dashboard-widget"):
            local_pos = self.card.mapFrom(self, event.position().toPoint())
            target = self.find_module_at(local_pos)
            
            # Render hover borders
            for module in self.modules:
                if module == target and module != self.dragged_module:
                    module.set_drag_over(True)
                else:
                    module.set_drag_over(False)
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-dashboard-widget"):
            local_pos = self.card.mapFrom(self, event.position().toPoint())
            target = self.find_module_at(local_pos)
            
            # Reset borders
            for module in self.modules:
                module.set_drag_over(False)
                
            if target and target != self.dragged_module:
                self.swap_modules(self.dragged_module, target)
                
            self.dragged_module = None
            event.acceptProposedAction()
