"""
Sidebar Navigation Component
Wraps the TabBar component and bridges tab changes.
"""
import customtkinter as ctk
from ui.components.tab_bar import TabBar

class NavigationWidget(ctk.CTkFrame):
    def __init__(self, master, tabs, on_tab_switch, **kwargs):
        super().__init__(master, fg_color="transparent", height=28, **kwargs)
        self.pack_propagate(False)
        self.on_tab_switch = on_tab_switch

        self.tab_bar = TabBar(
            self,
            tabs=tabs,
            default_tab=None,
            command=self._on_tab_switch
        )
        self.tab_bar.pack(fill="x")

    def _on_tab_switch(self, tab_name):
        if self.on_tab_switch:
            self.on_tab_switch(tab_name)
            
    def select_tab(self, tab_name):
        self.tab_bar.select_tab(tab_name)
