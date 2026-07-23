"""
PySide6 Settings Page Component
Manages advanced configurations, hotkeys, status updates, and presets.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QTimer, Property, QPropertyAnimation, QEasingCurve, Slot, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QKeySequence

from ui.qt.widgets import ScrollableList, make_card, make_button
from ui.qt.theme import get_theme_color
from services.settings_service import get_settings_service
from core.events import EventBus
from core.version import __version__


class QtLolToggle(QPushButton):
    """Custom Riot-style animated sliding toggle switch for PySide6."""
    
    def __init__(self, parent=None, active_color=None, inactive_color=None, knob_color=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(34, 18)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.active_color = QColor(active_color or "#A88A4E")
        self.inactive_color = QColor(inactive_color or "#1E2328")
        self.knob_color = QColor(knob_color or "#F0E6D2")
        
        self._knob_position = 2.0
        
        self.anim = QPropertyAnimation(self, b"knob_position", self)
        self.anim.setDuration(120)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

    @Property(float)
    def knob_position(self):
        return self._knob_position

    @knob_position.setter
    def knob_position(self, pos):
        self._knob_position = pos
        self.update()

    def setChecked(self, checked):
        b_checked = str(checked).lower() in ("true", "1", "yes") if isinstance(checked, str) else bool(checked)
        super().setChecked(b_checked)
        self.anim.stop()
        self._knob_position = 16.0 if b_checked else 2.0
        self.update()

    def nextCheckState(self):
        super().nextCheckState()
        target = 16.0 if self.isChecked() else 2.0
        self.anim.stop()
        self.anim.setStartValue(self._knob_position)
        self.anim.setEndValue(target)
        self.anim.start()

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key_Space, Qt.Key_Enter, Qt.Key_Return]:
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        track_color = self.active_color if self.isChecked() else self.inactive_color
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 9, 9)
        
        painter.setBrush(QBrush(self.knob_color))
        painter.drawEllipse(QPoint(int(self._knob_position + 9), 9), 6, 6)
        
        if self.hasFocus():
            painter.setPen(QPen(QColor("#4A90E2"), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(0, 0, self.width(), self.height(), 9, 9)


class SettingsToggleRow(QWidget):
    """Horizontal setting row with label and QtLolToggle."""
    
    def __init__(self, parent=None, label_text="", initial_state=False, on_toggle=None):
        super().__init__(parent)
        self.on_toggle = on_toggle
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        
        self.setStyleSheet("""
            QWidget {
                background: transparent;
            }
            QWidget:hover {
                background-color: rgba(200, 170, 110, 0.05);
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(12)
        
        self.lbl_text = QLabel(label_text, self)
        self.lbl_text.setStyleSheet("color: #F0E6D2; font-size: 12px; font-weight: normal;")
        layout.addWidget(self.lbl_text, alignment=Qt.AlignVCenter)
        
        layout.addStretch()
        
        self.toggle = QtLolToggle(
            self,
            active_color="#A88A4E",
            inactive_color="#1E2328",
            knob_color="#F0E6D2"
        )
        self.toggle.setChecked(initial_state)
        self.toggle.clicked.connect(self._on_toggle_clicked)
        layout.addWidget(self.toggle, alignment=Qt.AlignVCenter)
        
    def _on_toggle_clicked(self):
        if self.on_toggle:
            self.on_toggle(self.toggle.isChecked())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle.click()
            event.accept()

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key_Space, Qt.Key_Enter, Qt.Key_Return]:
            self.toggle.click()
            event.accept()
        else:
            super().keyPressEvent(event)


class SettingsSliderRow(QWidget):
    """Horizontal setting row with label, QSlider, and live value badge."""
    
    def __init__(self, parent=None, label_text="", initial_value=0.0, min_val=0.0, max_val=5.0, step=0.5, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self.step = step
        self.setFixedHeight(32)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(10)
        
        self.lbl_text = QLabel(label_text, self)
        self.lbl_text.setStyleSheet("color: #F0E6D2; font-size: 12px;")
        layout.addWidget(self.lbl_text)
        
        layout.addStretch()
        
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setFixedWidth(100)
        self.slider.setRange(int(min_val * 10), int(max_val * 10))
        self.slider.setValue(int(initial_value * 10))
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #1A283C;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #C8AA6E;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #F0E6D2;
                width: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
        """)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)
        
        self.lbl_val = QLabel(f"{initial_value:.1f}s", self)
        self.lbl_val.setStyleSheet("color: #C8AA6E; font-size: 11px; font-weight: bold; min-width: 30px;")
        layout.addWidget(self.lbl_val)

    def _on_slider_changed(self, val):
        real_val = val / 10.0
        self.lbl_val.setText(f"{real_val:.1f}s")
        if self.on_change:
            self.on_change(real_val)


class QtHotkeyRecorderButton(QPushButton):
    """A QPushButton that records global hotkey shortcuts on click."""
    
    def __init__(self, parent=None, config_key="", initial_value="", on_change=None):
        super().__init__(parent)
        self.config_key = config_key
        self.hotkey_value = initial_value
        self.on_change = on_change
        self.recording = False
        
        self.setText(initial_value or "Click to set")
        self.setFixedSize(110, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self.toggle_recording)
        
        self.setStyleSheet("""
            QPushButton {
                background-color: #0A1424;
                border: 1px solid #1E2D42;
                border-radius: 4px;
                color: #C8AA6E;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #142236;
                border-color: #C8AA6E;
            }
        """)

    def toggle_recording(self):
        if self.recording:
            self.stop_recording(cancel=True)
        else:
            self.start_recording()

    def start_recording(self):
        self.recording = True
        self.setText("Listening...")
        self.setStyleSheet("""
            QPushButton {
                background-color: #A88A4E;
                border: 1px solid #A88A4E;
                border-radius: 4px;
                color: #080E18;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.grabKeyboard()

    def stop_recording(self, success=False, cancel=False):
        self.recording = False
        self.releaseKeyboard()
        
        self.setStyleSheet("""
            QPushButton {
                background-color: #0A1424;
                border: 1px solid #1E2D42;
                border-radius: 4px;
                color: #C8AA6E;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #142236;
                border-color: #C8AA6E;
            }
        """)
        
        if success and self.on_change:
            self.on_change(self.hotkey_value)
            
        self.setText(self.hotkey_value or "Click to set")

    def keyPressEvent(self, event):
        if not self.recording:
            super().keyPressEvent(event)
            return
            
        key = event.key()
        if key == Qt.Key_Escape:
            self.stop_recording(cancel=True)
            return

        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return
            
        modifiers = event.modifiers()
        parts = []
        if modifiers & Qt.ControlModifier: parts.append("ctrl")
        if modifiers & Qt.AltModifier: parts.append("alt")
        if modifiers & Qt.ShiftModifier: parts.append("shift")
        
        key_str = self._map_key_to_str(key)
        if key_str:
            parts.append(key_str)
            self.hotkey_value = "+".join(parts)
            self.stop_recording(success=True)

    def _map_key_to_str(self, key):
        if Qt.Key_A <= key <= Qt.Key_Z:
            return chr(key).lower()
        if Qt.Key_0 <= key <= Qt.Key_9:
            return chr(key)
        if Qt.Key_F1 <= key <= Qt.Key_F12:
            return f"f{key - Qt.Key_F1 + 1}"
            
        key_map = {
            Qt.Key_Space: "space",
            Qt.Key_Tab: "tab",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Delete: "delete",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Minus: "-",
            Qt.Key_Plus: "+",
            Qt.Key_Equal: "=",
            Qt.Key_BracketLeft: "[",
            Qt.Key_BracketRight: "]",
            Qt.Key_Backslash: "\\",
            Qt.Key_Semicolon: ";",
            Qt.Key_Apostrophe: "'",
            Qt.Key_Comma: ",",
            Qt.Key_Period: ".",
            Qt.Key_Slash: "/",
            Qt.Key_Grave: "`",
        }
        return key_map.get(key, "")


class SettingsHotkeyRow(QWidget):
    """Horizontal hotkey configuration row."""
    
    def __init__(self, parent=None, label_text="", config_key="", default_val="", on_change=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        
        self.lbl = QLabel(label_text, self)
        self.lbl.setStyleSheet("color: #F0E6D2; font-size: 12px;")
        layout.addWidget(self.lbl)
        
        layout.addStretch()
        
        self.btn_hk = QtHotkeyRecorderButton(
            self,
            config_key=config_key,
            initial_value=default_val,
            on_change=on_change
        )
        layout.addWidget(self.btn_hk)


class SettingsPage(ScrollableList):
    """The PySide6 Settings Page containing grouped configuration cards."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        
        self.container_layout.setContentsMargins(14, 14, 14, 14)
        self.container_layout.setSpacing(10)
        
        self.setup_ui()

    def setup_ui(self):
        # ─── 1. LOBBY & MATCHMAKING ───
        card_lobby = make_card(title="LOBBY & MATCHMAKING")
        
        row_accept = SettingsToggleRow(
            self,
            label_text="Auto-Accept Ready Check",
            initial_state=self.config.get("auto_accept", True),
            on_toggle=lambda v: self._save_setting("auto_accept", v)
        )
        card_lobby.add_widget(row_accept)
        
        accept_delay = float(self.config.get("accept_delay", 2.0))
        row_delay = SettingsSliderRow(
            self,
            label_text="Accept Delay (Seconds)",
            initial_value=accept_delay,
            on_change=lambda v: self._save_setting("accept_delay", float(v))
        )
        card_lobby.add_widget(row_delay)
        
        row_requeue = SettingsToggleRow(
            self,
            label_text="Auto-Requeue After Dodge",
            initial_state=self.config.get("auto_requeue_after_dodge", True),
            on_toggle=lambda v: self._save_setting("auto_requeue_after_dodge", v)
        )
        card_lobby.add_widget(row_requeue)
        
        self.add_widget(card_lobby)
        
        # ─── 2. CHAMPION SELECT AUTOMATION ───
        card_champ = make_card(title="CHAMPION SELECT")
        
        row_pick = SettingsToggleRow(
            self,
            label_text="Auto-Pick Priority Champion",
            initial_state=self.config.get("auto_pick", True),
            on_toggle=lambda v: self._save_setting("auto_pick", v)
        )
        card_champ.add_widget(row_pick)
        
        row_ban = SettingsToggleRow(
            self,
            label_text="Auto-Ban Blacklist Champion",
            initial_state=self.config.get("auto_ban", False),
            on_toggle=lambda v: self._save_setting("auto_ban", v)
        )
        card_champ.add_widget(row_ban)
        
        row_runes = SettingsToggleRow(
            self,
            label_text="Auto-Import Optimal Runes",
            initial_state=self.config.get("auto_runes", True),
            on_toggle=lambda v: self._save_setting("auto_runes", v)
        )
        card_champ.add_widget(row_runes)
        
        row_skin = SettingsToggleRow(
            self,
            label_text="Auto-Equip Favorite Skin",
            initial_state=self.config.get("auto_skin", True),
            on_toggle=lambda v: self._save_setting("auto_skin", v)
        )
        card_champ.add_widget(row_skin)
        
        self.add_widget(card_champ)
        
        # ─── 3. APP & BEHAVIOR ───
        card_auto = make_card(title="APP PREFERENCES")
        
        row_autolaunch = SettingsToggleRow(
            self,
            label_text="Auto-Launch Client on Disconnect",
            initial_state=self.config.get("auto_launch_client", False),
            on_toggle=lambda v: self._save_setting("auto_launch_client", v)
        )
        card_auto.add_widget(row_autolaunch)
        
        row_tray = SettingsToggleRow(
            self,
            label_text="Minimize to System Tray",
            initial_state=self.config.get("run_in_tray", True),
            on_toggle=lambda v: self._save_setting("run_in_tray", v)
        )
        card_auto.add_widget(row_tray)
        

        self.add_widget(card_auto)

        # ─── 4. GLOBAL HOTKEYS ───
        card_hotkeys = make_card(title="GLOBAL HOTKEYS")
        
        hotkeys = [
            ("Toggle Automation", "hotkey_toggle_automation", "f3"),
            ("Trigger Matchmaking", "hotkey_find_match", "f4"),
        ]
        
        for label_text, config_key, default_val in hotkeys:
            current_val = self.config.get(config_key, default_val)
            row_hk = SettingsHotkeyRow(
                self,
                label_text=label_text,
                config_key=config_key,
                default_val=current_val,
                on_change=lambda val, k=config_key: self._save_setting(k, val)
            )
            card_hotkeys.add_widget(row_hk)
            
        self.add_widget(card_hotkeys)

    def _save_setting(self, key, val):
        self.config.set(key, val)
        from ui.qt.widgets.toast import ToastManager
        ToastManager.get_instance().show(f"Setting saved: {key}", icon="⚙️", theme="info")
