"""
PySide6 LeagueLoop Main Window Shell.
Implements custom frameless titlebar, theme integration, sidebar navigation,
and containerized service integration.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.qt.theme import (
    COLOR_BACKGROUND_DARK,
    COLOR_BACKGROUND_PANEL,
    COLOR_BORDER,
    COLOR_DANGER,
    COLOR_GOLD_PRIMARY,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    get_global_stylesheet,
)
from ui.qt.widgets.navigation.sidebar import QtNavigationSidebar
from ui.qt.widgets.play_tab import QtPlayTab
from ui.qt.widgets.priority_tab import QtPriorityTab
from ui.qt.widgets.diagnostics_tab import QtDiagnosticsTab
from ui.qt.widgets.settings_tab import QtSettingsTab


class CustomTitleBar(QFrame):
    """Custom frameless draggable title bar."""

    def __init__(self, parent: LeagueLoopMainWindow):
        super().__init__(parent)
        self._parent = parent
        self.setFixedHeight(32)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BACKGROUND_DARK};
                border-bottom: 1px solid {COLOR_BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 4, 0)

        self.title_label = QLabel("Queqq — League of Legends Client Companion", self)
        self.title_label.setStyleSheet(f"""
            color: {COLOR_TEXT_SECONDARY};
            font-size: 12px;
            font-weight: 500;
        """)
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Window control buttons
        self.btn_min = QPushButton("🗕", self)
        self.btn_min.setFixedSize(28, 24)
        self.btn_min.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #A09B8C;
                font-size: 12px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #1E282D;
                color: #FFFFFF;
            }
        """)
        self.btn_min.clicked.connect(self._parent.showMinimized)
        layout.addWidget(self.btn_min)

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setFixedSize(28, 24)
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: #A09B8C;
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_DANGER};
                color: #FFFFFF;
            }}
        """)
        self.btn_close.clicked.connect(self._parent.close)
        layout.addWidget(self.btn_close)


class LeagueLoopMainWindow(QMainWindow):
    """Primary PySide6 application window."""

    def __init__(self, container=None):
        super().__init__()
        self.container = container
        self._drag_pos = QPoint()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.resize(960, 640)
        self.setStyleSheet(get_global_stylesheet())

        # Central Root Widget
        root_widget = QWidget(self)
        self.setCentralWidget(root_widget)

        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Titlebar
        self.title_bar = CustomTitleBar(self)
        root_layout.addWidget(self.title_bar)

        # Body Layout: Sidebar + Stacked Content
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root_layout.addLayout(body_layout)

        self.sidebar = QtNavigationSidebar(parent=self)
        self.sidebar.tab_selected.connect(self._on_tab_switched)
        body_layout.addWidget(self.sidebar)

        self.tab_stack = QStackedWidget(self)
        body_layout.addWidget(self.tab_stack)

        # Populate tab pages
        self.tab_pages = {}
        for key, name, icon in self.sidebar.DEFAULT_TABS:
            if key == "play":
                page = QtPlayTab(container=self.container, parent=self)
            elif key == "priority":
                page = QtPriorityTab(container=self.container, parent=self)
            elif key == "diagnostics":
                page = QtDiagnosticsTab(container=self.container, parent=self)
            elif key == "settings":
                page = QtSettingsTab(container=self.container, parent=self)
            else:
                page = self._create_placeholder_page(key, name)
            self.tab_stack.addWidget(page)
            self.tab_pages[key] = page

    def _create_placeholder_page(self, key: str, name: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel(f"{name}", page)
        header.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {COLOR_GOLD_PRIMARY};
            margin-bottom: 8px;
        """)
        layout.addWidget(header)

        card = QFrame(page)
        card.setObjectName("panel")
        card_layout = QVBoxLayout(card)
        desc = QLabel(f"PySide6 {name} view initialized.", card)
        desc.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px;")
        card_layout.addWidget(desc)
        layout.addWidget(card)

        layout.addStretch()
        return page

    def _on_tab_switched(self, key: str) -> None:
        page = self.tab_pages.get(key)
        if page:
            self.tab_stack.setCurrentWidget(page)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
