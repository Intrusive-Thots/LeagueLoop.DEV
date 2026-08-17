"""
View-models for the LeagueLoop Qt shell.

Views bind to these instead of reading services directly, so presentation
logic stays testable and the UI has a single path from
`core.state.ApplicationState` to the screen (UI/UX Master Plan §2.1).
"""
from ui.qt.viewmodels.shell_viewmodel import (
    PHASE_LABELS,
    QUEUE_NAMES,
    ShellViewModel,
    phase_label,
    queue_label,
)

__all__ = [
    "ShellViewModel",
    "phase_label",
    "queue_label",
    "PHASE_LABELS",
    "QUEUE_NAMES",
]
