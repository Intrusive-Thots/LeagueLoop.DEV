"""
Base Component
Standardizes lifecycle hooks (mount, unmount, update) and EventBus bindings for CTk components.
"""
import customtkinter as ctk
from core.events import EventBus

class BaseComponent(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._mounted = False
        self._event_bindings = [] # List of tuples (event_name, callback)

    def bind_event(self, event_name, callback):
        """Bind an event to EventBus and track it for auto-unsubscribing on destruction."""
        EventBus.on(event_name, callback)
        self._event_bindings.append((event_name, callback))

    def mount(self):
        self._mounted = True
        self.on_mount()

    def unmount(self):
        self._mounted = False
        self.on_unmount()
        # Unsubscribe all EventBus listeners registered by this component
        # to prevent memory leaks.
        for event_name, callback in self._event_bindings:
            if event_name in EventBus._listeners:
                if callback in EventBus._listeners[event_name]:
                    EventBus._listeners[event_name].remove(callback)
        self._event_bindings.clear()

    def on_mount(self):
        pass

    def on_unmount(self):
        pass

    def update_view(self):
        if self._mounted and self.winfo_exists():
            self.on_update()

    def on_update(self):
        pass

    def destroy(self):
        self.unmount()
        super().destroy()
