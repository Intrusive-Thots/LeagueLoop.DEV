"""
Base ViewModel for LeagueLoop MVVM Architecture
"""
from PySide6.QtCore import QObject

class BaseViewModel(QObject):
    """
    Base class for all ViewModels.
    Inherits from QObject to allow for native Qt Signals which ensure 
    thread-safe cross-thread UI updates (essential since EventBus runs on background threads).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
