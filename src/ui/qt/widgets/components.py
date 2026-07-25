"""
Standardized UI Component Library for LeagueLoop
Implements Riot Games inspired modern widgets following the Version One design philosophy.
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFrame, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, Slot, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QColor

from ui.qt.widgets.icons import RiotIconWidget
from ui.qt.widgets.inputs import QtLolToggle


class SectionHeader(QWidget):
    """Clean, un-nested section title establishing visual hierarchy without card bloat."""
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(2)
        
        self.lbl_title = QLabel(title.upper(), self)
        self.lbl_title.setStyleSheet("""
            color: #C8AA6E;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            background: transparent;
        """)
        layout.addWidget(self.lbl_title)
        
        if subtitle:
            self.lbl_sub = QLabel(subtitle, self)
            self.lbl_sub.setStyleSheet("color: #A0A5B5; font-size: 11px; background: transparent;")
            layout.addWidget(self.lbl_sub)


class PrimaryButton(QPushButton):
    """Riot Gold gradient Call-To-Action button with animated glow effect."""
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(0)
        self.shadow.setColor(QColor("#C8AA6E"))
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(120)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._on_anim_val)

        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0E6D2, stop:0.5 #C8AA6E, stop:1 #A88A4E);
                color: #080E18;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 0.5px;
                border: 1px solid #FFF2D6;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:0.5 #DCC186, stop:1 #C8AA6E);
                border-color: #FFFFFF;
                color: #000000;
            }
            QPushButton:pressed {
                background: #8A6F3B;
                border-color: #A88A4E;
            }
            QPushButton:disabled {
                color: #5C6578;
                background-color: #121E2E;
                border: 1px solid #1E2D42;
            }
        """)

    def _on_anim_val(self, val):
        self.shadow.setBlurRadius(val)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.anim.stop()
        self.anim.setStartValue(self.shadow.blurRadius())
        self.anim.setEndValue(15.0)
        self.anim.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.anim.stop()
        self.anim.setStartValue(self.shadow.blurRadius())
        self.anim.setEndValue(0.0)
        self.anim.start()


class SecondaryButton(QPushButton):
    """Neutral outlined action button."""
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(0)
        self.shadow.setColor(QColor("#C8AA6E"))
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(120)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._on_anim_val)

        self.setStyleSheet("""
            QPushButton {
                background-color: #0E1826;
                color: #F0E6D2;
                font-weight: 600;
                font-size: 11px;
                border: 1px solid #1E2D42;
                border-radius: 6px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #16263D;
                border-color: #C8AA6E;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #0A121E;
            }
        """)

    def _on_anim_val(self, val):
        self.shadow.setBlurRadius(val)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.anim.stop()
        self.anim.setStartValue(self.shadow.blurRadius())
        self.anim.setEndValue(12.0)
        self.anim.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.anim.stop()
        self.anim.setStartValue(self.shadow.blurRadius())
        self.anim.setEndValue(0.0)
        self.anim.start()


class DangerButton(QPushButton):
    """Red accent warning button."""
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(0)
        self.shadow.setColor(QColor("#E74C3C"))
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(120)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._on_anim_val)

        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(231, 76, 60, 0.12);
                color: #E74C3C;
                font-weight: 600;
                font-size: 11px;
                border: 1px solid rgba(231, 76, 60, 0.4);
                border-radius: 6px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: rgba(231, 76, 60, 0.25);
                border-color: #E74C3C;
            }
            QPushButton:pressed {
                background-color: rgba(231, 76, 60, 0.35);
            }
        """)

    def _on_anim_val(self, val):
        self.shadow.setBlurRadius(val)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.anim.stop()
        self.anim.setStartValue(self.shadow.blurRadius())
        self.anim.setEndValue(12.0)
        self.anim.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.anim.stop()
        self.anim.setStartValue(self.shadow.blurRadius())
        self.anim.setEndValue(0.0)
        self.anim.start()


class CleanSettingRow(QWidget):
    """Spacious, minimal inline setting row with toggle."""
    toggled = Signal(bool)

    def __init__(self, title: str, subtitle: str = "", initial_state: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        
        self.lbl_title = QLabel(title, self)
        self.lbl_title.setStyleSheet("color: #F0E6D2; font-size: 12px; font-weight: 500; background: transparent;")
        text_layout.addWidget(self.lbl_title)
        
        if subtitle:
            self.lbl_sub = QLabel(subtitle, self)
            self.lbl_sub.setStyleSheet("color: #6C757D; font-size: 10px; background: transparent;")
            text_layout.addWidget(self.lbl_sub)
            
        layout.addLayout(text_layout, stretch=1)
        
        self.toggle = QtLolToggle(
            self,
            active_color="#C8AA6E",
            inactive_color="#142236",
            knob_color="#F0E6D2"
        )
        self.toggle.setChecked(initial_state)
        self.toggle.clicked.connect(self._on_toggled)
        layout.addWidget(self.toggle)

    def _on_toggled(self):
        val = self.toggle.isChecked()
        self.toggled.emit(val)

    def setChecked(self, val: bool):
        self.toggle.setChecked(val)


class MasterToggleRow(QWidget):
    """Master toggle row (matching Version One $ ALL ON UX)."""
    master_toggled = Signal(bool)

    def __init__(self, title: str = "$ ALL ON", initial_state: bool = True, parent=None):
        super().__init__(parent)
        self.setObjectName("masterToggleRow")
        self.setStyleSheet("""
            QWidget#masterToggleRow {
                background-color: #0E1826;
                border: 1px solid #1E2D42;
                border-radius: 6px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        self.lbl_title = QLabel(title, self)
        self.lbl_title.setStyleSheet("color: #C8AA6E; font-size: 12px; font-weight: bold;")
        layout.addWidget(self.lbl_title, stretch=1)
        
        self.toggle = QtLolToggle(
            self,
            active_color="#C8AA6E",
            inactive_color="#142236",
            knob_color="#F0E6D2"
        )
        self.toggle.setChecked(initial_state)
        self.toggle.clicked.connect(self._on_click)
        layout.addWidget(self.toggle)

    def _on_click(self):
        val = self.toggle.isChecked()
        self.lbl_title.setText("$ ALL ON" if val else "$ ALL OFF")
        self.master_toggled.emit(val)


class SearchBar(QLineEdit):
    """Clean search input with embedded icon."""
    def __init__(self, placeholder: str = "Search...", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(30)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #0A1424;
                color: #F0E6D2;
                border: 1px solid #1E2D42;
                border-radius: 6px;
                padding-left: 10px;
                padding-right: 10px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #C8AA6E;
                background-color: #0E1826;
            }
        """)


class StatusBadge(QLabel):
    """Pill indicator badge for status messaging."""
    def __init__(self, text: str = "", status: str = "info", parent=None):
        super().__init__(text, parent)
        self.set_status(text, status)

    def set_status(self, text: str, status: str = "info"):
        self.setText(text)
        if status == "connected" or status == "success":
            color = "#2ECC71"
            bg = "rgba(46, 204, 113, 0.12)"
            border = "rgba(46, 204, 113, 0.3)"
        elif status == "warning" or status == "gold":
            color = "#C8AA6E"
            bg = "rgba(200, 170, 110, 0.12)"
            border = "rgba(200, 170, 110, 0.3)"
        elif status == "error" or status == "disconnected":
            color = "#E74C3C"
            bg = "rgba(231, 76, 60, 0.12)"
            border = "rgba(231, 76, 60, 0.3)"
        else:
            color = "#A0A5B5"
            bg = "#0A1424"
            border = "#1E2D42"

        self.setStyleSheet(f"""
            color: {color};
            font-size: 10px;
            font-weight: bold;
            background-color: {bg};
            border: 1px solid {border};
            border-radius: 4px;
            padding: 2px 8px;
        """)
