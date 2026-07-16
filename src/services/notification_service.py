"""
Notification Service
Manages app-wide toast alerts, notification history, and broadcasts alerts to listening UI layers.
"""
from core.events import EventBus
from utils.logger import Logger

class NotificationService:
    def __init__(self):
        self._history = []
        self._max_history = 50

    def show(self, message: str, icon: str = "✨", theme: str = "primary", confetti: bool = False):
        """Dispatches a notification to all active UI notification views (CTk Toasts, Qt overlays)."""
        notification = {
            "message": message,
            "icon": icon,
            "theme": theme,
            "confetti": confetti,
            "timestamp": None # Will be set on emit or by listener
        }
        
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history.pop(0)
            
        Logger.info("NotificationService", f"Notification: {message} [{theme}]")
        
        # Emit to both CustomTkinter and PySide6 subscribers
        EventBus.emit("show_toast", message, icon, theme, confetti)
        EventBus.emit("notification_received", notification)

    def success(self, message: str, icon: str = "✓", confetti: bool = False):
        self.show(message, icon=icon, theme="success", confetti=confetti)

    def error(self, message: str, icon: str = "⚠️"):
        self.show(message, icon=icon, theme="error")

    def warning(self, message: str, icon: str = "⚠️"):
        self.show(message, icon=icon, theme="warning")

    def info(self, message: str, icon: str = "ℹ"):
        self.show(message, icon=icon, theme="primary")

    def get_history(self) -> list:
        return self._history

    def clear_history(self):
        self._history.clear()
        EventBus.emit("notification_history_cleared")

# Global singleton
_instance = None

def get_notification_service() -> NotificationService:
    global _instance
    if _instance is None:
        _instance = NotificationService()
    return _instance
