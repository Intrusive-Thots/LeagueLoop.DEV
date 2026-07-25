"""
PySide6 Automations Page Component
Version One design: dedicated tab for all automation toggles.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout
from ui.qt.widgets.components import SectionHeader, CleanSettingRow, MasterToggleRow
from ui.qt.widgets.scrollable_list import ScrollableList
from ui.qt.viewmodels.play_viewmodel import PlayViewModel

class AutomationsPage(QWidget):
    """Version One Automations page using PlayViewModel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewmodel = PlayViewModel(self)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)

        self.scroll.add_widget(SectionHeader("Automation", "Toggle individual features on or off"))

        self.master_toggle = MasterToggleRow("$ ALL ON", initial_state=True, parent=self)
        self.master_toggle.master_toggled.connect(self._on_master_toggled)
        self.scroll.add_widget(self.master_toggle)

        self.toggle_accept = CleanSettingRow("Auto-Accept", "", self.viewmodel.config.get("auto_accept", True), self)
        self.toggle_accept.toggled.connect(lambda v: self.viewmodel.set_automation_states({"auto_accept": v}))
        self.scroll.add_widget(self.toggle_accept)

        self.toggle_pick = CleanSettingRow("Auto-Pick", "", self.viewmodel.config.get("auto_pick", True), self)
        self.toggle_pick.toggled.connect(lambda v: self.viewmodel.set_automation_states({"auto_pick": v}))
        self.scroll.add_widget(self.toggle_pick)

        self.toggle_runes = CleanSettingRow("Auto-Runes", "", self.viewmodel.config.get("auto_runes", True), self)
        self.toggle_runes.toggled.connect(lambda v: self.viewmodel.set_automation_states({"auto_runes": v}))
        self.scroll.add_widget(self.toggle_runes)

        self.toggle_skin = CleanSettingRow("Auto-Skin", "", self.viewmodel.config.get("auto_skin", True), self)
        self.toggle_skin.toggled.connect(lambda v: self.viewmodel.set_automation_states({"auto_skin": v}))
        self.scroll.add_widget(self.toggle_skin)

        self.toggle_honor = CleanSettingRow("Auto-Honor", "", self.viewmodel.config.get("auto_honor", True), self)
        self.toggle_honor.toggled.connect(lambda v: self.viewmodel.set_automation_states({"auto_honor": v}))
        self.scroll.add_widget(self.toggle_honor)

    def _on_master_toggled(self, state: bool):
        self.toggle_accept.setChecked(state)
        self.toggle_pick.setChecked(state)
        self.toggle_runes.setChecked(state)
        self.toggle_skin.setChecked(state)
        self.toggle_honor.setChecked(state)
        self.viewmodel.set_automation_states({
            "auto_accept": state, "auto_pick": state, "auto_runes": state,
            "auto_skin": state, "auto_honor": state
        })
