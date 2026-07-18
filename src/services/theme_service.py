"""
Theme Service
Computes design tokens and compiles them into standard Qt Stylesheets (QSS) for PySide6.
"""
from ui.theme.token_loader import TOKENS
from utils.logger import Logger

class ThemeService:
    def __init__(self):
        self.tokens = TOKENS

    def get_color(self, dot_path: str, default: str = "#000000") -> str:
        return self.tokens.get(*dot_path.split("."), default=default)

    def get_spacing(self, multiplier: int = 1) -> int:
        return 8 * multiplier

    def get_radius(self, size: str = "md", default: int = 8) -> int:
        return self.tokens.get("radius", size, default=default)

    def get_stylesheet(self) -> str:
        """Compiles design tokens into a comprehensive QSS stylesheet for PySide6 components."""
        # Retrieve primary color tokens
        bg_app = self.get_color("colors.background.app", "#091428")
        bg_panel = self.get_color("colors.background.panel", "#0A1428")
        bg_card = self.get_color("colors.background.card", "#0F1923")
        bg_card_hover = self.get_color("colors.background.card_hover", "#132030")
        bg_input = self.get_color("colors.background.input", "#0A1220")
        
        text_primary = self.get_color("colors.text.primary", "#F0E6D2")
        text_secondary = self.get_color("colors.text.secondary", "#C8AA6E")
        text_muted = self.get_color("colors.text.muted", "#6C757D")
        text_disabled = self.get_color("colors.text.disabled", "#3A4654")
        
        accent_gold = self.get_color("colors.accent.gold", "#C8AA6E")
        accent_blue = self.get_color("colors.accent.blue", "#0BC6E3")
        state_success = self.get_color("colors.state.success", "#2ECC71")
        state_danger = self.get_color("colors.state.danger", "#E74C3C")
        state_hover = self.get_color("colors.state.hover", "#1C2630")
        
        radius_md = self.get_radius("md", 8)
        radius_sm = self.get_radius("sm", 4)
        
        # Build stylesheet
        qss = f"""
        /* Global Defaults */
        QWidget {{
            background-color: transparent;
            color: {text_primary};
            font-family: "Segoe UI", "Spiegel", "Arial";
            font-size: 12px;
        }}
        
        /* Main Window App Frame */
        QMainWindow, QDialog {{
            background-color: {bg_app};
        }}
        
        /* Panel Container Frame */
        QFrame#panelFrame {{
            background-color: {bg_panel};
            border: 1px solid #1E2328;
            border-radius: {radius_md}px;
        }}
        
        /* Card Frame */
        QFrame#cardFrame {{
            background-color: {bg_card};
            border: 1px solid #1E2839;
            border-radius: {radius_md}px;
        }}
        
        QFrame#cardFrame:hover {{
            background-color: {bg_card_hover};
            border-color: {accent_gold};
        }}
        
        /* Standard Buttons */
        QPushButton {{
            border-radius: {radius_sm}px;
            font-weight: bold;
            padding: 6px 16px;
            outline: none;
        }}
        
        QPushButton#primaryBtn {{
            background-color: {accent_gold};
            color: {bg_app};
            border: 1px solid {accent_gold};
            min-height: 28px;
        }}
        
        QPushButton#primaryBtn:hover {{
            background-color: #D3B679;
            border-color: #D3B679;
        }}
        
        QPushButton#primaryBtn:pressed {{
            background-color: #9C824E;
            border-color: #9C824E;
        }}
        
        QPushButton#primaryBtn:focus {{
            border: 1px solid {accent_blue};
        }}
        
        QPushButton#secondaryBtn {{
            background-color: transparent;
            color: {accent_gold};
            border: 1px solid {accent_gold};
            min-height: 28px;
        }}
        
        QPushButton#secondaryBtn:hover {{
            background-color: {state_hover};
        }}
        
        QPushButton#secondaryBtn:pressed {{
            background-color: rgba(200, 170, 110, 0.2);
        }}
        
        QPushButton#secondaryBtn:focus {{
            border: 1px solid {accent_blue};
        }}
        
        QPushButton#dangerBtn {{
            background-color: transparent;
            color: {state_danger};
            border: 1px solid {state_danger};
            min-height: 28px;
        }}
        
        QPushButton#dangerBtn:hover {{
            background-color: rgba(231, 76, 60, 0.15);
        }}
        
        QPushButton#dangerBtn:pressed {{
            background-color: rgba(231, 76, 60, 0.3);
        }}
        
        QPushButton#dangerBtn:focus {{
            border: 1px solid {accent_blue};
        }}
        
        QPushButton:disabled {{
            color: {text_disabled};
            background-color: transparent;
            border-color: {text_disabled};
        }}
        
        /* Inputs & Entries */
        QLineEdit {{
            background-color: {bg_input};
            border: 1px solid #1E2328;
            border-radius: {radius_sm}px;
            color: {text_primary};
            padding: 6px 10px;
        }}
        
        QLineEdit:focus {{
            border: 1px solid {accent_blue};
            background-color: {bg_card};
        }}
        
        /* Scrollbars styling */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 6px;
            margin: 0px;
        }}
        
        QScrollBar::handle:vertical {{
            background: {text_disabled};
            min-height: 20px;
            border-radius: 3px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background: {text_muted};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0px;
        }}
        
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        
        /* Tooltips */
        QToolTip {{
            background-color: {bg_card};
            color: {text_primary};
            border: 1px solid {accent_gold};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
        }}
        
        /* Friend list headers and online badge */
        QLabel#onlineBadge {{
            background-color: {state_success};
            color: {bg_app};
            border-radius: 9px;
            font-weight: bold;
            font-size: 10px;
            padding: 1px 6px;
        }}

        /* Keyboard Accessibility Focus Outline */
        QPushButton:focus, QLineEdit:focus, QCheckBox:focus, QRadioButton:focus {{
            border: 1px solid {accent_gold};
        }}
        """
        return qss

# Global singleton
_instance = None

def get_theme_service() -> ThemeService:
    global _instance
    if _instance is None:
        _instance = ThemeService()
    return _instance
