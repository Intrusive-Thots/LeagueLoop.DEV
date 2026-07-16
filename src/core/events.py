"""
Events Module
Provides the central _EventBus singleton for decoupled, app-wide pub/sub communication
between services, tasks, and CustomTkinter/PySide6 UI views.
"""

class _EventBus:
    """
    Central event bus for cross-component communication.
    Pure Python implementation to safely bridge Tkinter -> PySide6 migration.
    Use EventBus (the singleton instance) globally.
    """
    def __init__(self):
        self._listeners = {}

    def on(self, event_name, callback):
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        if callback not in self._listeners[event_name]:
            self._listeners[event_name].append(callback)

    def emit(self, event_name, *args, **kwargs):
        if event_name in self._listeners:
            for cb in self._listeners[event_name]:
                try:
                    cb(*args, **kwargs)
                except Exception as e:
                    from utils.logger import Logger
                    import traceback
                    Logger.error("EVENTBUS", f"Error in {event_name}: {e}\n{traceback.format_exc()}")

    def invoke_thread_safe(self, widget, callback, *args):
        """Phase 5 Thread Safety: UI updates must run on the main thread."""
        # Using tk.after for now. During PySide6 migration, this will become QMetaObject.invokeMethod
        if hasattr(widget, "winfo_toplevel"):
            try:
                root = widget.winfo_toplevel()
                if root and hasattr(root, "after"):
                    root.after(0, lambda: callback(*args))
                    return
            except Exception:
                pass
        if hasattr(widget, "after"):
            widget.after(0, lambda: callback(*args))
        else:
            callback(*args)

# Global Singleton instance
EventBus = _EventBus()
