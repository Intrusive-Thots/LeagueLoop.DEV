"""
Central event bus for cross-component communication.
Pure Python implementation to safely bridge Tkinter -> PySide6 migration.
Use EventBus (the singleton instance) globally.

Improvements:
- Thread-safe dispatch with copy-on-emit strategy
- Disposable subscription handles for clean unsubscribe
- Typed event constants for high-value events
- Listener exception isolation
"""
import threading
import weakref
from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    """Typed event constants for high-value events."""
    # LCU Connection
    LCU_CONNECTED = "lcu_connected"
    LCU_DISCONNECTED = "lcu_disconnected"
    
    # Gameflow Phase changes
    GAMEFLOW_PHASE = "gameflow_phase"
    
    # Automation state
    AUTOMATION_STARTED = "automation_started"
    AUTOMATION_STOPPED = "automation_stopped"
    AUTOMATION_PAUSED = "automation_paused"
    
    # Toast notifications
    TOAST_NOTIFICATION = "toast_notification"
    
    # Queue state
    QUEUE_FOUND = "queue_found"
    QUEUE_ACCEPTED = "queue_accepted"
    QUEUE_DECLINED = "queue_declined"
    
    # Champ Select
    CHAMP_SELECT_STARTED = "champ_select_started"
    CHAMP_SELECT_UPDATED = "champ_select_updated"
    CHAMP_SELECT_ENDED = "champ_select_ended"
    CHAMPION_SELECTED = "champion_selected"
    CHAMPION_BANNED = "champion_banned"
    
    # Lobby
    LOBBY_CREATED = "lobby_created"
    LOBBY_JOINED = "lobby_joined"
    LOBBY_LEFT = "lobby_left"

    # Automation error & diagnostics
    AUTOMATION_ERROR = "automation_error"
    ACCOUNT_CHANGED = "account_changed"
    STATS_UPDATED = "stats_updated"
    SETTINGS_CHANGED = "settings_changed"
    STATE_CHANGED = "state_changed"


@dataclass
class Event:
    """Structured event payload."""
    type: EventType
    data: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0
    
    def __post_init__(self):
        import time
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class SubscriptionHandle:
    """Disposable handle for unsubscribing from events."""
    
    def __init__(self, event_name: str, callback: Callable, bus: '_EventBus'):
        self._event_name = event_name
        self._callback = weakref.ref(callback) if callable(callback) else None
        self._bus = weakref.ref(bus)
        self._disposed = False
    
    def dispose(self):
        """Unsubscribe from the event."""
        if not self._disposed:
            bus = self._bus()
            if bus:
                callback = self._callback() if self._callback else None
                if callback:
                    bus.off(self._event_name, callback)
            self._disposed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()


class _EventBus:
    """
    Central event bus for cross-component communication.
    Thread-safe with copy-on-emit strategy and subscription handles.
    """
    
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
    
    def on(self, event_name: str, callback: Callable) -> SubscriptionHandle:
        """
        Subscribe to an event. Returns a disposable handle.
        
        Args:
            event_name: Name of the event (use EventType enum values when possible)
            callback: Function to call when event is emitted
            
        Returns:
            SubscriptionHandle that can be disposed to unsubscribe
        """
        handle = SubscriptionHandle(event_name, callback, self)
        
        with self._lock:
            if event_name not in self._listeners:
                self._listeners[event_name] = []
            if callback not in self._listeners[event_name]:
                self._listeners[event_name].append(callback)
        
        return handle
    
    def off(self, event_name: str, callback: Callable):
        """Unbind a listener from an event."""
        with self._lock:
            if event_name in self._listeners and callback in self._listeners[event_name]:
                self._listeners[event_name].remove(callback)
                if not self._listeners[event_name]:
                    del self._listeners[event_name]
    
    def emit(self, event_name: str, *args, **kwargs):
        """
        Emit an event to all listeners.
        
        Uses copy-on-emit strategy to avoid mutation during dispatch.
        Listener exceptions are isolated and logged without stopping other listeners.
        """
        from utils.logger import Logger
        import traceback
        
        # Copy listeners under lock to avoid mutation during dispatch
        with self._lock:
            if event_name not in self._listeners:
                return
            listeners_copy = list(self._listeners[event_name])
        
        # Dispatch outside lock to prevent deadlocks
        for cb in listeners_copy:
            try:
                cb(*args, **kwargs)
            except Exception as e:
                Logger.error("EVENTBUS", f"Error in {event_name}: {e}\n{traceback.format_exc()}")
    
    def emit_typed(self, event: Event):
        """Emit a typed event with structured payload."""
        self.emit(event.type.value, event)
    
    def invoke_thread_safe(self, widget, callback: Callable, *args):
        """
        Thread-safe UI update invocation.
        
        For CustomTkinter: uses widget.after() to marshal to main thread.
        For PySide6 (future): will use QMetaObject.invokeMethod().
        """
        if hasattr(widget, "after"):
            widget.after(0, lambda: callback(*args))
        else:
            callback(*args)
    
    def clear(self):
        """Clear all listeners (useful for testing or shutdown)."""
        with self._lock:
            self._listeners.clear()
    
    def listener_count(self, event_name: str) -> int:
        """Get count of listeners for an event (useful for debugging)."""
        with self._lock:
            return len(self._listeners.get(event_name, []))


# Global Singleton instance
EventBus = _EventBus()
