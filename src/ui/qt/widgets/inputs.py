"""
PySide6 Inputs Primitives
─────────────────────────
Implements QLineEdit inputs using QSS styling and native placeholders.
"""
from PySide6.QtWidgets import QLineEdit


def make_input(parent, placeholder="", width=None, **kw):
    """Create a standardized styled QLineEdit input field."""
    entry = QLineEdit(parent)
    if placeholder:
        entry.setPlaceholderText(placeholder)
    if width:
        entry.setFixedWidth(width)
    if "height" in kw:
        entry.setFixedHeight(kw["height"])
    
    # Enable standard styling
    entry.setObjectName("standardInput")
    return entry
