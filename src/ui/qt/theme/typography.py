"""
Typography Tokens for LeagueLoop UI (UI/UX Master Plan §35).

Defines the full type scale so hierarchy is expressed through typography
before borders and color are reached for. Each style is a `TextStyle` that
can emit a QSS fragment or a QFont, so widgets never hardcode font sizes.

Scale: Display > Page title > Section title > Body > Caption > Micro
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtGui import QFont

# Primary UI font stack. Segoe UI is the Windows system face and matches the
# League Client's density; the rest are fallbacks for dev on other platforms.
FONT_FAMILY = '"Segoe UI", "Inter", "Noto Sans", Arial, sans-serif'
FONT_FAMILY_PRIMARY = "Segoe UI"

# Monospace stack, used only for Diagnostics / Developer Mode surfaces (§58).
FONT_FAMILY_MONO = '"Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace'

# Weights (§35: avoid excessive font-weight variation — three is enough)
WEIGHT_REGULAR = 400
WEIGHT_MEDIUM = 500
WEIGHT_BOLD = 700


@dataclass(frozen=True)
class TextStyle:
    """A single step on the type scale."""

    size_px: int
    weight: int = WEIGHT_REGULAR
    letter_spacing_px: float = 0.0
    uppercase: bool = False
    family: str = FONT_FAMILY

    def qss(self, color: Optional[str] = None) -> str:
        """Return a QSS declaration block fragment for this style."""
        parts = [
            f"font-family: {self.family};",
            f"font-size: {self.size_px}px;",
            f"font-weight: {self.weight};",
        ]
        if self.letter_spacing_px:
            parts.append(f"letter-spacing: {self.letter_spacing_px}px;")
        if self.uppercase:
            parts.append("text-transform: uppercase;")
        if color:
            parts.append(f"color: {color};")
        return " ".join(parts)

    def font(self) -> QFont:
        """Return a QFont configured for this style."""
        f = QFont(FONT_FAMILY_PRIMARY)
        f.setPixelSize(self.size_px)
        f.setWeight(QFont.Weight(self.weight))
        if self.letter_spacing_px:
            f.setLetterSpacing(QFont.AbsoluteSpacing, self.letter_spacing_px)
        if self.uppercase:
            f.setCapitalization(QFont.AllUppercase)
        return f


# --- The scale -------------------------------------------------------------

TEXT_DISPLAY = TextStyle(size_px=24, weight=WEIGHT_BOLD, letter_spacing_px=0.2)
TEXT_PAGE_TITLE = TextStyle(size_px=20, weight=WEIGHT_BOLD)
TEXT_SECTION_TITLE = TextStyle(
    size_px=11, weight=WEIGHT_BOLD, letter_spacing_px=0.8, uppercase=True
)
TEXT_BODY = TextStyle(size_px=13, weight=WEIGHT_REGULAR)
TEXT_BODY_STRONG = TextStyle(size_px=13, weight=WEIGHT_MEDIUM)
TEXT_CAPTION = TextStyle(size_px=11, weight=WEIGHT_REGULAR)
TEXT_MICRO = TextStyle(size_px=10, weight=WEIGHT_MEDIUM, letter_spacing_px=0.4)

# Brand wordmark (header lockup)
TEXT_BRAND = TextStyle(
    size_px=14, weight=WEIGHT_BOLD, letter_spacing_px=1.5, uppercase=True
)

__all__ = [
    "FONT_FAMILY",
    "FONT_FAMILY_PRIMARY",
    "FONT_FAMILY_MONO",
    "WEIGHT_REGULAR",
    "WEIGHT_MEDIUM",
    "WEIGHT_BOLD",
    "TextStyle",
    "TEXT_DISPLAY",
    "TEXT_PAGE_TITLE",
    "TEXT_SECTION_TITLE",
    "TEXT_BODY",
    "TEXT_BODY_STRONG",
    "TEXT_CAPTION",
    "TEXT_MICRO",
    "TEXT_BRAND",
]
