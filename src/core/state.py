class AppState:
    """
    Central state manager. Single source of truth for the application.
    UI elements should only read from this state when an event fires.
    """
    def __init__(self):
        self.connected = False
        self.phase = "None"
        
        self.queue = None
        self.friends = []
        self.champs = []
        
        self.session = None
        self.lobby = None
        self.search_state = None
        
        self.settings = {}
        self.auto_accept = True
        self.arena_synergy_enabled = True
        self.assets = None

# Global Singleton instance
State = AppState()
