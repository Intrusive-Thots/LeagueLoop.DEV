"""
Friends ViewModel
Manages friend list state, online presence, and EventBus subscriptions.
"""
from PySide6.QtCore import Signal
from ui.qt.viewmodels.base_viewmodel import BaseViewModel
from services.friend_service import get_friend_service
from core.events import EventBus

class FriendsViewModel(BaseViewModel):
    # Signals
    friends_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.friend_service = get_friend_service()
        
        EventBus.on("friends_state_changed", self._on_friends_state_changed)

    def get_friends(self):
        return self.friend_service.get_friends()
        
    def fetch_friends(self):
        self.friend_service.fetch_friends()

    def toggle_auto_join(self, name):
        self.friend_service.toggle_auto_join(name)
        
    def get_auto_join_status(self, name):
        return self.friend_service.get_auto_join_status(name)
        
    def invite_friend(self, name):
        self.friend_service.invite_friend(name)

    def _on_friends_state_changed(self):
        self.friends_updated.emit()
