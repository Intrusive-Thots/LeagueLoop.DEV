"""
Config Page Component (Game Tools)
Manages the active game tool layout (ARAM Priority Grid, Arena Synergy, Draft Planner) in CustomTkinter.
"""
import customtkinter as ctk
from ui.components.game_tools.arena_tool import ArenaTool
from ui.components.game_tools.draft_tool import DraftTool
from ui.components.priority_grid import PriorityIconGrid

class ConfigPage(ctk.CTkFrame):
    def __init__(self, master, coordinator, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.coordinator = coordinator
        self.config = coordinator.config
        self.assets = coordinator.assets
        
        self.game_tool_container = ctk.CTkFrame(self, fg_color="transparent")
        self.game_tool_container.pack(fill="both", expand=True)

        self.priority_grid = PriorityIconGrid(self.game_tool_container, self.config, self.assets)
        self.arena_tool = ArenaTool(self.game_tool_container, self.config, self.assets)
        self.draft_tool = DraftTool(self.game_tool_container, self.config, self.assets)
        
        self.update_game_tool_visibility(self.config.get("aram_mode", "ARAM"))

    def update_game_tool_visibility(self, mode: str):
        """Toggle tool visibility based on active game mode/queue."""
        # Unpack everything first
        self.priority_grid.pack_forget()
        self.arena_tool.pack_forget()
        self.draft_tool.pack_forget()

        if mode == "Arena":
            self.arena_tool.pack(fill="x", pady=0)
        elif mode in ("Draft", "Solo/Flex"):
            self.draft_tool.pack(fill="x", pady=0)
        else: # Default is ARAM / Arena 3v6
            self.priority_grid.pack(fill="x", pady=0)
