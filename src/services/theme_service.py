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

    def get_radius(self, size: str = "md", default: int = 12) -> int:
        return self.tokens.get("radius", size, default=default)

    def get_stylesheet(self) -> str:
        """Compiles design tokens into a comprehensive QSS stylesheet for PySide6 components."""
        bg_app = self.get_color("colors.background.app", "#080E18")
        bg_panel = self.get_color("colors.background.panel", "#0B1524")
        bg_card = self.get_color("colors.background.card", "#0F1A2A")
        bg_card_hover = self.get_color("colors.background.card_hover", "#142236")
        bg_input = self.get_color("colors.background.input", "#0A1220")
        
        text_primary = self.get_color("colors.text.primary", "#F8F6F0")
        text_secondary = self.get_color("colors.text.secondary", "#F0C674")
        text_muted = self.get_color("colors.text.muted", "#A8B8CC")
        text_disabled = self.get_color("colors.text.disabled", "#708090")
        
        accent_gold = self.get_color("colors.accent.gold", "#C8AA6E")
        accent_blue = self.get_color("colors.accent.blue", "#0BC6E3")
        state_success = self.get_color("colors.state.success", "#2ECC71")
        state_danger = self.get_color("colors.state.danger", "#E74C3C")
        state_hover = self.get_color("colors.state.hover", "#1C2630")
        
        radius_md = 12
        radius_sm = 6
        
        qss = f"""
        /* Global Defaults */
        QWidget {{
            background-color: transparent;
            color: {text_primary};
            font-family: "Inter", "Segoe UI", "SF Pro Text", Arial, sans-serif;
            font-size: 12px;
        }}
        
        /* Main Window App Frame */
        QMainWindow, QDialog {{
            background-color: {bg_app};
        }}
        
        /* Panel Container Frame */
        QFrame#panelFrame {{
            background-color: {bg_panel};
            border: 1px solid #182536;
            border-radius: {radius_md}px;
        }}
        
        /* Card Frame */
        QFrame#cardFrame {{
            background-color: {bg_card};
            border: 1px solid #1E2D42;
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
            padding: 6px 14px;
            outline: none;
        }}
        
        QPushButton#primaryBtn {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #DCC186, stop:1 #C8AA6E);
            color: #080E18;
            border: 1px solid #EADBBA;
            min-height: 32px;
            border-radius: 6px;
        }}
        
        QPushButton#primaryBtn:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EBE0C2, stop:1 #DCC186);
            border-color: #FFF2D6;
        }}
        
        QPushButton#primaryBtn:pressed {{
            background-color: #9C824E;
            border-color: #9C824E;
        }}
        
        QPushButton#secondaryBtn {{
            background-color: rgba(200, 170, 110, 0.08);
            color: {accent_gold};
            border: 1px solid rgba(200, 170, 110, 0.3);
            min-height: 30px;
            border-radius: 6px;
        }}
        
        QPushButton#secondaryBtn:hover {{
            background-color: rgba(200, 170, 110, 0.18);
            border-color: {accent_gold};
        }}
        
        QPushButton#secondaryBtn:pressed {{
            background-color: rgba(200, 170, 110, 0.28);
        }}
        
        QPushButton#dangerBtn {{
            background-color: rgba(231, 76, 60, 0.1);
            color: {state_danger};
            border: 1px solid rgba(231, 76, 60, 0.4);
            min-height: 30px;
            border-radius: 6px;
        }}
        
        QPushButton#dangerBtn:hover {{
            background-color: rgba(231, 76, 60, 0.25);
            border-color: {state_danger};
        }}
        
        QPushButton:disabled {{
            color: {text_disabled};
            background-color: transparent;
            border-color: {text_disabled};
        }}
        
        /* Inputs & Entries */
        QLineEdit {{
            background-color: {bg_input};
            border: 1px solid #1E2D42;
            border-radius: {radius_sm}px;
            color: {text_primary};
            padding: 6px 12px;
        }}
        
        QLineEdit:focus {{
            border: 1px solid {accent_gold};
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
            background: #203048;
            min-height: 24px;
            border-radius: 3px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background: {accent_gold};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0px;
        }}
        
        /* Tooltips */
        QToolTip {{
            background-color: #0A1424;
            color: {text_primary};
            border: 1px solid {accent_gold};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
        }}
        
        QPushButton:focus, QLineEdit:focus, QCheckBox:focus, QRadioButton:focus {{
            border: 1px solid {accent_gold};
        }}
        """
        return qss

_instance = None

def get_theme_service() -> ThemeService:
    global _instance
    if _instance is None:
        _instance = ThemeService()
    return _instance
