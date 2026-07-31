"""
PySide6 Toast Notifications System
──────────────────────────────────
Implements holographic, non-intrusive animated feedback overlay widgets.
Fully thread-safe via Qt Signal/Slot communication.
"""
from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QObject, Signal, Slot, QEvent
from ui.qt.theme import get_theme_color, get_theme_radius
from core.events import EventBus


class Toast(QFrame):
    """A single overlay toast notification with slide-in animation."""

    def __init__(self, message, icon="✨", duration=3000, theme="primary", parent=None):
        super().__init__(parent)
        self.duration = duration
        self._is_dismissing = False

        # Cursor & Styling
        self.setCursor(Qt.PointingHandCursor)

        # Color definitions based on token themes
        border_c = "#1A2332"
        if theme == "success":
            border_c = get_theme_color("colors.state.success", "#2ECC71")
        elif theme == "error":
            border_c = get_theme_color("colors.state.danger", "#E74C3C")
        else:
            border_c = get_theme_color("colors.accent.gold", "#C8AA6E")

        bg_hex = get_theme_color("colors.background.panel", "#0A1428")
        text_color = get_theme_color("colors.text.primary", "#F0E6D2")
        radius = get_theme_radius("md", 8)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_hex};
                border: 1px solid {border_c};
                border-radius: {radius}px;
            }}
            QLabel {{
                border: none;
                background: transparent;
                color: {text_color};
            }}
        """)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Icon Label
        self.lbl_icon = QLabel(icon, self)
        self.lbl_icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.lbl_icon)

        # Message Label
        self.lbl_msg = QLabel(message, self)
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.lbl_msg)

        # Auto-dismiss timer
        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self.dismiss)
        self.dismiss_timer.start(self.duration)

    def mousePressEvent(self, event):
        """Dismiss immediately on click."""
        self.dismiss()
        event.accept()

    def dismiss(self):
        """Starts dismissal fade out / destruction."""
        if self._is_dismissing:
            return
        self._is_dismissing = True

        # Simple Qt property animation for smooth opacity fade out
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(200)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.destroy_toast)
        self.anim.start()

    def destroy_toast(self):
        self.setParent(None)
        self.deleteLater()


class ToastSignalEmitter(QObject):
    """Helper QObject to dispatch toast creation safely onto the Qt main thread."""
    show_toast = Signal(str, str, int, str, bool)


class ToastManager(QWidget):
    """Manages the overlay layout, stack, and positioning of active Toast widgets."""

    _instance = None
    MAX_TOASTS = 5

    @classmethod
    def get_instance(cls, root=None):
        """Gets or creates the singleton ToastManager instance."""
        if cls._instance is None:
            if root is None:
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance()
                active_win = app.activeWindow() if app else None
                if active_win:
                    cls._instance = cls(active_win)
                else:
                    return None
            else:
                cls._instance = cls(root)
        return cls._instance

    def __init__(self, root):
        super().__init__(root)
        self.root = root

        # Overlay settings
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(Qt.SubWindow)

        # Stack Layout (Bottom-Up)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(6)
        self.main_layout.addStretch()  # Forces toasts to pile at bottom

        self._toasts = []

        # Thread-safe emitter setup
        self.emitter = ToastSignalEmitter()
        self.emitter.show_toast.connect(self._on_show_toast)

        # Listen on the core EventBus
        EventBus.on("show_toast", self.trigger_toast)

        # Monitor size / moves of parent to align correctly
        self.root.installEventFilter(self)
        self.update_geometry()

    def show(self, message=None, icon="✨", duration=3000, theme="primary", confetti=False):
        """Show toast message or call QWidget.show()."""
        if message is None or not isinstance(message, str):
            super().show()
            return
        self.trigger_toast(message, icon=icon, duration=duration, theme=theme, confetti=confetti)

    def trigger_toast(self, message, icon="✨", duration=3000, theme="primary", confetti=False):
        """EventBus thread-safe entry point."""
        self.emitter.show_toast.emit(message, icon, duration, theme, confetti)

    @Slot(str, str, int, str, bool)
    def _on_show_toast(self, message, icon, duration, theme, confetti):
        # Evict oldest if limit reached
        while len(self._toasts) >= self.MAX_TOASTS:
            oldest = self._toasts.pop(0)
            try:
                oldest.dismiss()
            except Exception:
                pass

        # Create Toast widget
        toast = Toast(message, icon, duration, theme, self)

        # Add to stacked layout (inserted before the spacer)
        self.main_layout.insertWidget(self.main_layout.count() - 1, toast)
        self._toasts.append(toast)

        # Auto clean list on destruction
        toast.destroyed.connect(lambda: self._on_toast_destroyed(toast))
        self.update_geometry()

    def _on_toast_destroyed(self, toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
        self.update_geometry()

    def update_geometry(self):
        """Align ToastManager container to the bottom-right of root parent."""
        if not self.root:
            return

        parent_w = self.root.width()
        parent_h = self.root.height()

        # Margin and bounds
        margin = 10
        width = 250
        height = min(300, parent_h - 40)

        x = parent_w - width - margin
        y = parent_h - height - 32 - margin  # Offset bottom status bar

        self.setGeometry(x, y, width, height)

    def eventFilter(self, watched, event):
        """Syncs positioning when main window is resized."""
        if watched == self.root and event.type() in (QEvent.Resize, QEvent.Move):
            self.update_geometry()
        return super().eventFilter(watched, event)
