"""
UI Design Tokens Loader Module for LeagueLoop.

Loads design tokens (colors, typography, radii, spacing) from design_tokens.json.
"""

import json
import os
import sys
import functools

def _resolve_token_path():
    """Resolve design_tokens.json for both dev and PyInstaller frozen builds."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Frozen: Try common locations in _MEIPASS
        candidates = [
            os.path.join(sys._MEIPASS, "ui", "theme", "design_tokens.json"),
            os.path.join(sys._MEIPASS, "design_tokens.json"),
            os.path.join(os.path.dirname(sys.executable), "ui", "theme", "design_tokens.json"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
    
    # Dev or fallback
    base = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base, "design_tokens.json")

TOKEN_PATH = _resolve_token_path()

# Sensible fallbacks for critical layout tokens to prevent NoneType scaling errors
DEFAULT_TOKENS = {
    "spacing": {
        "xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32
    },
    "radius": {
        "xs": 2, "sm": 4, "md": 8, "lg": 12, "xl": 16, "pill": 999
    },
    "colors": {
        "background": {"app": "#091428", "panel": "#0A1428", "card": "#141E28"},
        "text": {"primary": "#F0E6D2", "secondary": "#C8AA6E", "muted": "#6C757D"},
        "accent": {"primary": "#C8AA6E", "gold": "#C8AA6E", "blue": "#0BC6E3"}
    }
}

class DesignTokens:
    def __init__(self):
        try:
            if os.path.exists(TOKEN_PATH):
                with open(TOKEN_PATH, "r") as f:
                    self.tokens = json.load(f)
            else:
                self.tokens = DEFAULT_TOKENS
        except (FileNotFoundError, json.JSONDecodeError):
            self.tokens = DEFAULT_TOKENS


    @staticmethod
    @functools.lru_cache(maxsize=1024)
    def _parse_keys(keys):
        """Helper to parse and flatten dot-separated string keys."""
        parsed = []
        for k in keys:
            if isinstance(k, str) and "." in k:
                parsed.extend(k.split("."))
            else:
                parsed.append(k)
        return tuple(parsed)

    @functools.lru_cache(maxsize=1024)
    def _get_memoized(self, keys):
        """Memoized helper to avoid repeated dict traversal and string splitting overhead."""
        data = self.tokens
        try:
            for k in self._parse_keys(keys):
                data = data[k]
            return data
        except (KeyError, TypeError, IndexError):
            return None

    def get(self, *keys, default=None):
        if not keys:
            return default

        # Handle cases where developers mistakenly pass the default as a positional argument
        last = keys[-1]
        if isinstance(last, str):
            if last and last[0] == "#" or last in ("transparent", "left", "right", "center", "bold", "normal", "medium"):
                default = last
                keys = keys[:-1]
        elif isinstance(last, (int, float, bool)):
            default = last
            keys = keys[:-1]

        if not keys:
            return default

        val = self._get_memoized(keys)
        if val is None:
            return default
        return val

    def get_shadow(self, name: str, default: str = "") -> str:
        return self.get("shadows", name, default=default)

    def get_animation(self, name: str, default: dict = None) -> dict:
        return self.get("animations", name, default=default or {})

    def get_gradient(self, name: str, default: list = None) -> list:
        return self.get("gradients", name, default=default or [])

    def spacing(self, multiplier: int = 1) -> int:
        """Returns 8px based spacing value (e.g. spacing(2) -> 16px)."""
        return 8 * multiplier

TOKENS = DesignTokens()
