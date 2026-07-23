"""
Typed Event System Module
Provides thread-safe event bus, strongly typed event payloads, and subscription handles.
"""
import threading
import traceback
from typing import Callable, Dict, List, Type, Union, Any


class Event:
    """Base class for all typed application events."""
    pass


class GamePhaseChangedEvent(Event):
    """Fired when LCU gameflow phase changes (e.g., Lobby, ChampSelect, InProgress)."""
    def __init__(self, phase: str):
        self.phase = phase


class ChampionSelectedEvent(Event):
    """Fired when a champion is hovered or selected in draft."""
    def __init__(self, champion_id: int, champion_name: str, is_intent: bool = False):
        self.champion_id = champion_id
        self.champion_name = champion_name
        self.is_intent = is_intent


class SettingsChangedEvent(Event):
    """Fired when configuration or settings are saved."""
    def __init__(self, section: str = "all"):
        self.section = section


class LCUConnectionEvent(Event):
    """Fired when LCU connection state changes."""
    def __init__(self, connected: bool, port: int = 0):
        self.connected = connected
        self.port = port


class MatchmakingEvent(Event):
    """Fired when matchmaking status changes."""
    def __init__(self, state: str, queue_id: int = 0):
        self.state = state
        self.queue_id = queue_id


class SubscriptionHandle:
    """Handle returned upon subscribing, allowing explicit unsubscription."""

    def __init__(self, event_bus: "_EventBus", key: Any, callback: Callable):
        self._event_bus = event_bus
        self._key = key
        self._callback = callback
        self._active = True

    def unsubscribe(self):
        """Unsubscribes the callback from the event bus."""
        if self._active:
            self._event_bus._remove_listener(self._key, self._callback)
            self._active = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unsubscribe()


class _EventBus:
    """Thread-safe event bus supporting both typed events and legacy string names."""

    def __init__(self):
        self._listeners: Dict[Any, List[Callable]] = {}
        self._lock = threading.RLock()

    def on(self, event_key: Union[str, Type[Event]], callback: Callable) -> SubscriptionHandle:
        """Subscribes a callback to a typed Event class or string event name."""
        with self._lock:
            if event_key not in self._listeners:
                self._listeners[event_key] = []
            if callback not in self._listeners[event_key]:
                self._listeners[event_key].append(callback)
        return SubscriptionHandle(self, event_key, callback)

    def subscribe(self, event_key: Union[str, Type[Event]], callback: Callable) -> SubscriptionHandle:
        """Alias for on()."""
        return self.on(event_key, callback)

    def _remove_listener(self, event_key: Any, callback: Callable):
        """Removes a listener callback under lock."""
        with self._lock:
            if event_key in self._listeners and callback in self._listeners[event_key]:
                self._listeners[event_key].remove(callback)
                if not self._listeners[event_key]:
                    del self._listeners[event_key]

    def _safe_invoke(self, cb, args, kwargs):
        from utils.logger import Logger
        try:
            cb(*args, **kwargs)
        except Exception as e:
            Logger.error("EVENTBUS", f"Error dispatching event (async Qt): {e}\n{traceback.format_exc()}")

    def emit(self, event_key: Union[str, Event], *args, **kwargs):
        """Dispatches an event instance or string event name to registered subscribers."""
        from utils.logger import Logger

        key = type(event_key) if isinstance(event_key, Event) else event_key
        payload_args = (event_key,) if isinstance(event_key, Event) and not args else args

        callbacks_to_invoke = []
        with self._lock:
            if key in self._listeners:
                callbacks_to_invoke = list(self._listeners[key])

        for cb in callbacks_to_invoke:
            try:
                try:
                    from PySide6.QtWidgets import QApplication
                    from PySide6.QtCore import QTimer, QThread
                    app_inst = QApplication.instance()
                    if app_inst and QThread.currentThread() != app_inst.thread():
                        QTimer.singleShot(0, lambda c=cb, a=payload_args, k=kwargs: self._safe_invoke(c, a, k))
                        continue
                except Exception:
                    pass

                cb(*payload_args, **kwargs)
            except Exception as e:
                Logger.error("EVENTBUS", f"Error dispatching {key}: {e}\n{traceback.format_exc()}")

    def publish(self, event_instance: Event):
        """Publishes a typed Event instance."""
        self.emit(event_instance)


# Global singleton instance for backward compatibility
EventBus = _EventBus()
