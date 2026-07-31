"""
Coach ViewModel
Manages draft state, recommendations, and EventBus subscriptions for the Coach Page.
"""
from PySide6.QtCore import Signal
from ui.qt.viewmodels.base_viewmodel import BaseViewModel
from services.draft_service import get_draft_service
from services.settings_service import get_settings_service
from core.events import EventBus

class CoachViewModel(BaseViewModel):
    # Signals
    draft_state_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.draft_service = get_draft_service()
        self.config = get_settings_service()

        EventBus.on("draft_state_changed", self._on_draft_state_changed)

    def get_session(self):
        return self.draft_service.get_session()

    def get_team_comp_analysis(self):
        return self.draft_service.get_team_comp_analysis()

    def get_recommendations(self, role):
        return self.draft_service.get_recommendations(role=role)

    def _on_draft_state_changed(self, session_data):
        self.draft_state_changed.emit()
