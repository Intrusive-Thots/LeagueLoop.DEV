import functools
import re
from typing import Optional, Tuple

"""Color utility functions."""

_TRANSPARENT_NAMES = frozenset({"transparent", "none", "null", ""})
_HEX_BODY = re.compile(r"^[0-9a-fA-F]{3}$|^[0-9a-fA-F]{6}$|^[0-9a-fA-F]{8}$")


def parse_hex_rgb(color) -> Optional[Tuple[int, int, int]]:
    """Parse a hex color, CTk (light, dark) pair, or named non-color into RGB.

    Returns None for transparent / invalid values instead of raising. The old
    slicer assumed ``color[1:3]`` was always hex, so strings like ``invalid``
    logged ``invalid literal for int() with base 16: 'nv'`` hundreds of times.
    """
    if color is None:
        return None
    if isinstance(color, (tuple, list)):
        for part in color:
            parsed = parse_hex_rgb(part)
            if parsed is not None:
                return parsed
        return None
    if not isinstance(color, str):
        return None
    body = color.strip().lstrip("#")
    if body.lower() in _TRANSPARENT_NAMES:
        return None
    if not _HEX_BODY.match(body):
        return None
    if len(body) == 3:
        body = "".join(ch * 2 for ch in body)
    else:
        body = body[:6]
    return (int(body[0:2], 16), int(body[2:4], 16), int(body[4:6], 16))


def ctk_safe_color(color, fallback: str = "transparent"):
    """Return a CustomTkinter-safe color. ``None`` is rejected by CTkEntry.

    CTk stores appearance-mode pairs as 2-tuples; a None component still
    raises ``ValueError: color is None, for transparency set color='transparent'``.
    """
    if color is None:
        return fallback
    if isinstance(color, (tuple, list)):
        if len(color) == 2:
            return (ctk_safe_color(color[0], fallback), ctk_safe_color(color[1], fallback))
        if len(color) == 1:
            return ctk_safe_color(color[0], fallback)
        return fallback
    if isinstance(color, str):
        if color.lower() in _TRANSPARENT_NAMES and color.lower() != "transparent":
            return fallback
        return color if color else fallback
    return fallback


# ⚡ Bolt: Memoize hex to RGB conversion.
# Avoids redundant string parsing for frequently used UI theme colors.
@functools.lru_cache(maxsize=128)
def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c + c for c in hex_color)
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color length: {len(hex_color)}")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


# ⚡ Bolt: Memoize color interpolation.
# Caches intermediate gradient calculations to reduce main thread CPU overhead during UI rendering.
@functools.lru_cache(maxsize=128)
def interpolate_color(color1, color2, factor):
    """Interpolate between two hex colors."""
    if color1 == "transparent" or color2 == "transparent":
        return color1
    c1 = parse_hex_rgb(color1)
    c2 = parse_hex_rgb(color2)
    if c1 is None or c2 is None:
        return color1
    new_color = [int(c1[i] + (c2[i] - c1[i]) * factor) for i in range(3)]
    return _rgb_to_hex((new_color[0], new_color[1], new_color[2]))


# ⚡ Bolt: Memoize color lightening.
# Speeds up hover state generation for CustomTkinter widgets by caching the string math operations.
@functools.lru_cache(maxsize=128)
def lighten_color(hex_color, percent=10):
    """Lighten a hex color by a percentage (0-100)."""
    if hex_color == "transparent":
        return hex_color
    rgb = parse_hex_rgb(hex_color)
    if rgb is None:
        return hex_color if hex_color is not None else "transparent"
    factor = percent / 100
    r = min(255, int(rgb[0] + (255 - rgb[0]) * factor))
    g = min(255, int(rgb[1] + (255 - rgb[1]) * factor))
    b = min(255, int(rgb[2] + (255 - rgb[2]) * factor))
    return _rgb_to_hex((r, g, b))


# ⚡ Bolt: Memoize color darkening.
# Speeds up press state generation for UI buttons by caching the hex math operations.
@functools.lru_cache(maxsize=128)
def darken_color(hex_color, percent=10):
    """Darken a hex color by a percentage (0-100)."""
    if hex_color == "transparent":
        return hex_color
    rgb = parse_hex_rgb(hex_color)
    if rgb is None:
        return hex_color if hex_color is not None else "transparent"
    factor = 1 - (percent / 100)
    r = max(0, int(rgb[0] * factor))
    g = max(0, int(rgb[1] * factor))
    b = max(0, int(rgb[2] * factor))
    return _rgb_to_hex((r, g, b))
