"""
Qt Theme Stylesheet Compiler
Retrieves colors, spacings, and styles from ThemeService to serve PySide6 layouts.
"""
from services.theme_service import get_theme_service

def apply_theme(app_or_widget):
    """Applies the compiled QSS stylesheet to a PySide6 QApp or QWidget."""
    theme = get_theme_service()
    qss = theme.get_stylesheet()
    app_or_widget.setStyleSheet(qss)

def get_theme_color(dot_path: str, default: str = "#000000") -> str:
    return get_theme_service().get_color(dot_path, default)

def get_theme_radius(size: str = "md", default: int = 8) -> int:
    return get_theme_service().get_radius(size, default)

def get_theme_spacing(multiplier: int = 1) -> int:
    return get_theme_service().get_spacing(multiplier)
