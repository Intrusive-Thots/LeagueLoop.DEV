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
from ui.qt.theme import get_theme_color, get_theme_radius, get_theme_spacing
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
        
        # Smooth animation for switch knob
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
        super().setChecked(checked)
        self.anim.stop()
        self._knob_position = 16.0 if checked else 2.0
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
        
        # Track
        track_color = self.active_color if self.isChecked() else self.inactive_color
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 9, 9)
        
        # Knob
        painter.setBrush(QBrush(self.knob_color))
        painter.drawEllipse(QPoint(int(self._knob_position + 9), 9), 6, 6)
        
        # Focus Ring
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
        self.lbl_text.setStyleSheet(f"color: {get_theme_color('colors.text.primary', '#F0E6D2')}; font-size: 12px; font-weight: normal;")
        layout.addWidget(self.lbl_text, alignment=Qt.AlignVCenter)
        
        layout.addStretch()
        
        self.toggle = QtLolToggle(
            self,
            active_color="#A88A4E",
            inactive_color=get_theme_color("colors.background.card", "#1E2328"),
            knob_color=get_theme_color("colors.text.primary", "#F0E6D2")
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

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hasFocus():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor("#C8AA6E"), 1))
            painter.drawRect(0, 0, self.width()-1, self.height()-1)


class SettingsSliderRow(QWidget):
    """Horizontal setting row with label, slider and value label."""
    
    def __init__(self, parent=None, label_text="", initial_value=2.0, min_val=0, max_val=8, format_str="{:.1f}s", on_change=None):
        super().__init__(parent)
        self.format_str = format_str
        self.on_change = on_change
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_text = QLabel(label_text, self)
        self.lbl_text.setStyleSheet(f"color: {get_theme_color('colors.text.primary')}; font-size: 12px;")
        layout.addWidget(self.lbl_text)
        
        layout.addStretch()
        
        # Value Label
        self.lbl_value = QLabel(self.format_str.format(initial_value), self)
        self.lbl_value.setStyleSheet(f"color: {get_theme_color('colors.accent.gold', '#C8AA6E')}; font-weight: bold; font-size: 12px;")
        self.lbl_value.setFixedWidth(35)
        self.lbl_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Horizontal QSlider
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setFixedWidth(80)
        self.slider.setMinimum(int(min_val * 10))
        self.slider.setMaximum(int(max_val * 10))
        self.slider.setValue(int(initial_value * 10))
        
        # Premium Riot stylesheet for QSlider
        gold = get_theme_color("colors.accent.gold", "#C8AA6E")
        bg_app = get_theme_color("colors.background.app", "#010A13")
        knob = get_theme_color("colors.text.primary", "#F0E6D2")
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: 1px solid #1E2328;
                height: 4px;
                background: {bg_app};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {gold};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {knob};
                width: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #FFFFFF;
            }}
        """)
        
        self.slider.valueChanged.connect(self._on_value_changed)
        
        layout.addWidget(self.slider)
        layout.addWidget(self.lbl_value)

    def _on_value_changed(self, raw_val):
        val = raw_val / 10.0
        self.lbl_value.setText(self.format_str.format(val))
        if self.on_change:
            self.on_change(val)


class SettingsInputRow(QWidget):
    """Vertical row with label and QLineEdit."""
    
    def __init__(self, parent=None, label_text="", initial_value="", placeholder="", on_change=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.lbl_text = QLabel(label_text, self)
        self.lbl_text.setStyleSheet(f"color: {get_theme_color('colors.text.muted')}; font-size: 11px;")
        layout.addWidget(self.lbl_text)
        
        self.entry = QLineEdit(self)
        self.entry.setText(initial_value)
        self.entry.setPlaceholderText(placeholder)
        self.entry.setFixedHeight(26)
        
        # Stylesheet matching factory.py
        bg_card = get_theme_color("colors.background.card", "#141E28")
        border = get_theme_color("colors.border.subtle", "#1E2328")
        gold = get_theme_color("colors.accent.gold", "#C8AA6E")
        self.entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 4px;
                color: #F0E6D2;
                font-size: 12px;
                padding-left: 6px;
                padding-right: 6px;
            }}
            QLineEdit:focus {{
                border: 1px solid {gold};
            }}
        """)
        
        if on_change:
            self.entry.textChanged.connect(on_change)
            
        layout.addWidget(self.entry)


class QtHotkeyRecorderButton(QPushButton):
    """A QPushButton that records global hotkey shortcuts on click."""
    
    def __init__(self, parent=None, config_key="", initial_value="", on_change=None):
        super().__init__(parent)
        self.config_key = config_key
        self.hotkey_value = initial_value
        self.on_change = on_change
        self.recording = False
        
        self.setText(initial_value or "Click to set")
        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self.toggle_recording)
        
        self._focus_border = get_theme_color("colors.accent.primary", "#0AC8B9")
        self._unfocus_border = get_theme_color("colors.border.subtle", "#1E2328")
        
        # Stylesheet matching factory.py QSS
        bg_card = get_theme_color("colors.background.card", "#141E28")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_card};
                border: 1px solid {self._unfocus_border};
                border-radius: 4px;
                color: #F0E6D2;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #1E2B38;
            }}
        """)

        # Pulse timer
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.animate_pulse)
        self.pulse_state = False

    def toggle_recording(self):
        if self.recording:
            self.stop_recording(cancel=True)
        else:
            self.start_recording()

    def start_recording(self):
        self.recording = True
        self.setText("⏺ Listening...")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #A88A4E;
                border: 1px solid #A88A4E;
                border-radius: 4px;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
            }}
        """)
        self.grabKeyboard()
        self.pulse_timer.start(600)

    def stop_recording(self, success=False, cancel=False):
        self.recording = False
        self.releaseKeyboard()
        self.pulse_timer.stop()
        
        bg_card = get_theme_color("colors.background.card", "#141E28")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_card};
                border: 1px solid {self._unfocus_border};
                border-radius: 4px;
                color: #F0E6D2;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #1E2B38;
            }}
        """)
        
        if success and self.on_change:
            self.on_change(self.hotkey_value)
            
        self.setText(self.hotkey_value or "Click to set")

    def animate_pulse(self):
        self.pulse_state = not self.pulse_state
        if self.pulse_state:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #8C723E;
                    border: 1px solid #8C723E;
                    border-radius: 4px;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #A88A4E;
                    border: 1px solid #A88A4E;
                    border-radius: 4px;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)

    def keyPressEvent(self, event):
        if not self.recording:
            super().keyPressEvent(event)
            return
            
        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return
            
        modifiers = event.modifiers()
        parts = []
        if modifiers & Qt.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.AltModifier:
            parts.append("alt")
        if modifiers & Qt.MetaModifier:
            parts.append("win")
            
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
            
        key_map = {
            Qt.Key_Space: "space",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Escape: "esc",
            Qt.Key_Tab: "tab",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Delete: "delete",
            Qt.Key_Insert: "insert",
            Qt.Key_Home: "home",
            Qt.Key_End: "end",
            Qt.Key_PageUp: "page up",
            Qt.Key_PageDown: "page down",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_F1: "f1", Qt.Key_F2: "f2", Qt.Key_F3: "f3", Qt.Key_F4: "f4",
            Qt.Key_F5: "f5", Qt.Key_F6: "f6", Qt.Key_F7: "f7", Qt.Key_F8: "f8",
            Qt.Key_F9: "f9", Qt.Key_F10: "f10", Qt.Key_F11: "f11", Qt.Key_F12: "f12",
        }
        return key_map.get(key, "")


class SettingsHotkeyRow(QWidget):
    """Hotkey row with vertical label and QtHotkeyRecorderButton."""
    
    def __init__(self, parent=None, label_text="", config_key="", default_val="", on_change=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.lbl_text = QLabel(label_text, self)
        self.lbl_text.setStyleSheet(f"color: {get_theme_color('colors.text.primary')}; font-size: 12px;")
        layout.addWidget(self.lbl_text)
        
        self.recorder = QtHotkeyRecorderButton(self, config_key, default_val, on_change)
        layout.addWidget(self.recorder)


class SettingsPage(ScrollableList):
    """The PySide6 Settings Page containing collapsible configuration groups."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_settings_service()
        
        # Setup margins and spacing
        self.container_layout.setContentsMargins(16, 16, 16, 16)
        self.container_layout.setSpacing(12)
        
        self.setup_ui()

    def setup_ui(self):
        # ─── LOBBY & QUEUE ───
        card_lobby = make_card(self.container, title="LOBBY & QUEUE")
        self.add_widget(card_lobby.parentWidget()) # make_card adds a RiotCard frame
        
        lobby_layout = QVBoxLayout(card_lobby)
        lobby_layout.setContentsMargins(0, 0, 0, 0)
        lobby_layout.setSpacing(8)
        
        accept_delay = float(self.config.get("accept_delay", 2.0))
        row_delay = SettingsSliderRow(
            self,
            label_text="Accept Delay",
            initial_value=accept_delay,
            on_change=self._save_accept_delay
        )
        lobby_layout.addWidget(row_delay)
        
        # ─── AUTOMATION & BEHAVIOR ───
        card_auto = make_card(self.container, title="AUTOMATION & BEHAVIOR")
        self.add_widget(card_auto.parentWidget())
        
        auto_layout = QVBoxLayout(card_auto)
        auto_layout.setContentsMargins(0, 0, 0, 0)
        auto_layout.setSpacing(8)
        
        run_in_tray = bool(self.config.get("run_in_tray", True))
        row_tray = SettingsToggleRow(
            self,
            label_text="Run in Tray",
            initial_state=run_in_tray,
            on_toggle=self._save_run_in_tray
        )
        auto_layout.addWidget(row_tray)
        
        # ─── SOCIAL & IDENTITY ───
        card_social = make_card(self.container, title="SOCIAL & IDENTITY")
        self.add_widget(card_social.parentWidget())
        
        social_layout = QVBoxLayout(card_social)
        social_layout.setContentsMargins(0, 0, 0, 0)
        social_layout.setSpacing(8)
        
        discord_rpc = bool(self.config.get("discord_rpc_enabled", True))
        row_discord = SettingsToggleRow(
            self,
            label_text="Discord RPC",
            initial_state=discord_rpc,
            on_toggle=self._save_discord_rpc
        )
        social_layout.addWidget(row_discord)
        
        vip_only = bool(self.config.get("auto_join_vip_only", False))
        row_vip_only = SettingsToggleRow(
            self,
            label_text="VIP Invites Only",
            initial_state=vip_only,
            on_toggle=self._save_vip_only
        )
        social_layout.addWidget(row_vip_only)
        
        vip_list = self.config.get("vip_invite_list", "")
        row_vip_list = SettingsInputRow(
            self,
            label_text="VIP Invite List",
            initial_value=vip_list,
            placeholder="Enter summoner names, comma separated...",
            on_change=self._save_vip_list
        )
        social_layout.addWidget(row_vip_list)

        # ─── HOTKEYS ───
        card_hotkeys = make_card(self.container, title="HOTKEYS")
        self.add_widget(card_hotkeys.parentWidget())
        
        hotkeys_layout = QVBoxLayout(card_hotkeys)
        hotkeys_layout.setContentsMargins(0, 0, 0, 0)
        hotkeys_layout.setSpacing(8)
        
        hotkeys = [
            ("Client Launch", "hotkey_launch_client", "ctrl+shift+l"),
            ("Toggle Auto", "hotkey_toggle_automation", "ctrl+shift+a"),
            ("Find Match", "hotkey_find_match", "ctrl+shift+f"),
        ]
        
        for label_text, config_key, default_val in hotkeys:
            current_val = self.config.get(config_key, default_val)
            row_hk = SettingsHotkeyRow(
                self,
                label_text=label_text,
                config_key=config_key,
                default_val=current_val,
                on_change=lambda val, k=config_key: self._save_hotkey(k, val)
            )
            hotkeys_layout.addWidget(row_hk)

        # ─── ABOUT ───
        card_about = make_card(self.container, title="ABOUT")
        self.add_widget(card_about.parentWidget())
        
        about_layout = QVBoxLayout(card_about)
        about_layout.setContentsMargins(0, 0, 0, 0)
        about_layout.setSpacing(6)
        
        lbl_app = QLabel("League Loop", self)
        lbl_app.setStyleSheet(f"color: {get_theme_color('colors.text.primary')}; font-weight: bold; font-size: 13px;")
        about_layout.addWidget(lbl_app)
        
        lbl_ver = QLabel(f"Version {__version__}", self)
        lbl_ver.setStyleSheet(f"color: {get_theme_color('colors.text.muted')}; font-size: 11px;")
        about_layout.addWidget(lbl_ver)
        
        btn_about = QPushButton("Info & Legal", self)
        btn_about.setCursor(Qt.PointingHandCursor)
        btn_about.setFixedSize(100, 24)
        btn_about.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {get_theme_color('colors.accent.primary', '#0AC8B9')};
                font-weight: bold;
                font-size: 11px;
                text-align: left;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
            }}
        """)
        btn_about.clicked.connect(self._open_about)
        about_layout.addWidget(btn_about)
        
        btn_mobile = make_button(self, text="Link Mobile Device", style="primary", width=150, height=24)
        btn_mobile.clicked.connect(self._open_mobile_qr)
        about_layout.addWidget(btn_mobile)

        # ─── PROFILE (Collapsible) ───
        # Retrieve content frame inside RiotCard
        profile_content = make_card(self.container, title="PROFILE", collapsible=True, start_collapsed=True)
        self.add_widget(profile_content.parentWidget())
        
        profile_layout = QVBoxLayout(profile_content)
        profile_layout.setContentsMargins(0, 4, 0, 0)
        profile_layout.setSpacing(6)
        
        lbl_status = QLabel("Custom Status", self)
        lbl_status.setStyleSheet(f"color: {get_theme_color('colors.text.muted')}; font-size: 11px;")
        profile_layout.addWidget(lbl_status)
        
        self.entry_status = QLineEdit(self)
        self.entry_status.setPlaceholderText("Set your status...")
        self.entry_status.setFixedHeight(30)
        
        bg_card = get_theme_color("colors.background.card", "#141E28")
        border = get_theme_color("colors.border.subtle", "#1E2328")
        gold = get_theme_color("colors.accent.gold", "#C8AA6E")
        self.entry_status.setStyleSheet(f"""
            QLineEdit {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 4px;
                color: #F0E6D2;
                font-size: 12px;
                padding-left: 8px;
                padding-right: 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid {gold};
            }}
        """)
        self.entry_status.returnPressed.connect(self._on_status_submit)
        profile_layout.addWidget(self.entry_status)
        
        # Presets Buttons
        presets_widget = QWidget(self)
        presets_layout = QHBoxLayout(presets_widget)
        presets_layout.setContentsMargins(0, 0, 0, 0)
        presets_layout.setSpacing(4)
        
        presets = [
            ("🚀", "Grinding Ranked"),
            ("🎮", "LeagueLoop ⚙️ https://github.com/Intrusive-Thots/LeagueLoop-Installer"),
            ("🌮", "Eating / Brb"),
            ("💤", "AFK"),
        ]
        
        radius_sm = get_theme_radius("sm")
        for emoji, text in presets:
            btn = QPushButton(emoji, self)
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"Set status to: {text}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_theme_color('colors.background.panel')};
                    border: 1px solid {border};
                    border-radius: {radius_sm}px;
                    font-size: 16px;
                }}
                QPushButton:hover {{
                    background-color: {get_theme_color('colors.state.hover')};
                }}
            """)
            btn.clicked.connect(lambda checked=False, em=emoji, tx=text: self._on_quick_status(em, tx))
            presets_layout.addWidget(btn)
            
        presets_layout.addStretch()
        profile_layout.addWidget(presets_widget)

    # ─── Settings Save Handlers ───
    def _save_accept_delay(self, val):
        self.config.set("accept_delay", round(val, 1))
        EventBus.emit("settings_saved")

    def _save_run_in_tray(self, val):
        self.config.set("run_in_tray", val)
        EventBus.emit("settings_saved")

    def _save_discord_rpc(self, val):
        self.config.set("discord_rpc_enabled", val)
        EventBus.emit("settings_saved")

    def _save_vip_only(self, val):
        self.config.set("auto_join_vip_only", val)
        EventBus.emit("settings_saved")

    def _save_vip_list(self, val):
        self.config.set("vip_invite_list", val.strip())
        EventBus.emit("settings_saved")

    def _save_hotkey(self, key, val):
        self.config.set(key, val)
        EventBus.emit("settings_saved")

    def _open_about(self):
        # Open a beautiful styled QDialog with Info & Legal details
        dialog = QDialog(self.window())
        dialog.setWindowTitle("Info & Legal")
        dialog.setMinimumSize(250, 180)
        dialog.setStyleSheet(f"background-color: {get_theme_color('colors.background.panel')}; color: #F0E6D2;")
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 15, 15, 15)
        
        lbl_title = QLabel("LeagueLoop Info & Legal", dialog)
        lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #C8AA6E;")
        layout.addWidget(lbl_title)
        
        lbl_text = QLabel(
            "LeagueLoop is an independent companion app and is not endorsed or affiliated with Riot Games.\n\n"
            "All game assets, trademarks, and copyrights belong to their respective owners.",
            dialog
        )
        lbl_text.setWordWrap(True)
        lbl_text.setStyleSheet("font-size: 11px; color: #8F908F;")
        layout.addWidget(lbl_text)
        
        btn_close = make_button(dialog, text="Close", style="primary", width=80, height=24)
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignCenter)
        
        dialog.exec()

    def _open_mobile_qr(self):
        parent_win = self.window()
        if hasattr(parent_win, "_show_mobile_qr"):
            parent_win._show_mobile_qr()

    def _on_status_submit(self):
        text = self.entry_status.text().strip()
        if text:
            EventBus.emit("action:set_status", text)
            
            # Show Toast
            ToastManager.get_instance().show(
                f"Status set: {text}",
                icon="💬",
                theme="success",
                duration=2000
            )

    def _on_quick_status(self, emoji, text):
        status_text = f"{emoji} {text}" if emoji else text
        self.entry_status.setText(status_text)
        self._on_status_submit()
