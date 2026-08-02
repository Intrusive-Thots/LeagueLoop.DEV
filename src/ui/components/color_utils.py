import functools
from typing import Tuple
from utils.logger import Logger
"""Color utility functions."""

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


# ⚡ Bolt: Memoize color interpolation.
# Caches intermediate gradient calculations to reduce main thread CPU overhead during UI rendering.
@functools.lru_cache(maxsize=128)
def interpolate_color(color1, color2, factor):
    """Interpolate between two hex colors."""
    if color1 == "transparent" or color2 == "transparent":
        return color1
    try:
        c1 = [int(color1[i : i + 2], 16) for i in (1, 3, 5)]
        c2 = [int(color2[i : i + 2], 16) for i in (1, 3, 5)]
        new_color = [int(c1[i] + (c2[i] - c1[i]) * factor) for i in range(3)]
        return f"#{new_color[0]:02x}{new_color[1]:02x}{new_color[2]:02x}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        Logger.error("color_utils.py", f"Handled exception: {e}")
        return color1


# ⚡ Bolt: Memoize color lightening.
# Speeds up hover state generation for CustomTkinter widgets by caching the string math operations.
@functools.lru_cache(maxsize=128)
def lighten_color(hex_color, percent=10):
    """Lighten a hex color by a percentage (0-100)."""
    if hex_color == "transparent":
        return hex_color
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = percent / 100
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        Logger.error("color_utils.py", f"Handled exception: {e}")
        return hex_color


# ⚡ Bolt: Memoize color darkening.
# Speeds up press state generation for UI buttons by caching the hex math operations.
@functools.lru_cache(maxsize=128)
def darken_color(hex_color, percent=10):
    """Darken a hex color by a percentage (0-100)."""
    if hex_color == "transparent":
        return hex_color
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = 1 - (percent / 100)
        r = max(0, int(r * factor))
        g = max(0, int(g * factor))
        b = max(0, int(b * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        Logger.error("color_utils.py", f"Handled exception: {e}")
        return hex_color
