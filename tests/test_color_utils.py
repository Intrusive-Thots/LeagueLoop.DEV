import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock dependencies before importing the module under test
patch.dict(sys.modules, {
    'customtkinter': MagicMock(),
    'tkinter': MagicMock(),
    'PIL': MagicMock(),
    'PIL.Image': MagicMock(),
    'PIL.ImageTk': MagicMock()
}).start()

from ui.components.color_utils import hex_to_rgb, interpolate_color, lighten_color, darken_color

class TestColorUtils(unittest.TestCase):
    def test_hex_to_rgb_6_char(self):
        """Test with standard 6-character hex string with leading #"""
        self.assertEqual(hex_to_rgb("#FFFFFF"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("#000000"), (0, 0, 0))
        self.assertEqual(hex_to_rgb("#FF0000"), (255, 0, 0))
        self.assertEqual(hex_to_rgb("#00FF00"), (0, 255, 0))
        self.assertEqual(hex_to_rgb("#0000FF"), (0, 0, 255))
        self.assertEqual(hex_to_rgb("#1A2B3C"), (26, 43, 60))

    def test_hex_to_rgb_6_char_no_hash(self):
        """Test with 6-character hex string without leading #"""
        self.assertEqual(hex_to_rgb("FFFFFF"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("000000"), (0, 0, 0))
        self.assertEqual(hex_to_rgb("1A2B3C"), (26, 43, 60))

    def test_hex_to_rgb_3_char(self):
        """Test with 3-character hex string with leading #"""
        self.assertEqual(hex_to_rgb("#FFF"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("#000"), (0, 0, 0))
        self.assertEqual(hex_to_rgb("#F00"), (255, 0, 0))
        self.assertEqual(hex_to_rgb("#123"), (17, 34, 51))

    def test_hex_to_rgb_3_char_no_hash(self):
        """Test with 3-character hex string without leading #"""
        self.assertEqual(hex_to_rgb("FFF"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("000"), (0, 0, 0))
        self.assertEqual(hex_to_rgb("123"), (17, 34, 51))

    def test_hex_to_rgb_invalid_length(self):
        """Test with invalid hex string lengths"""
        with self.assertRaises(ValueError):
            hex_to_rgb("#FF") # Length 2
        with self.assertRaises(ValueError):
            hex_to_rgb("#FFFF") # Length 4
        with self.assertRaises(ValueError):
            hex_to_rgb("FFFFF") # Length 5
        with self.assertRaises(ValueError):
            hex_to_rgb("#FFFFFFF") # Length 7

    def test_hex_to_rgb_invalid_chars(self):
        """Test with invalid characters in hex string"""
        with self.assertRaises(ValueError):
            hex_to_rgb("#ZZZZZZ")
        with self.assertRaises(ValueError):
            hex_to_rgb("GHIJKL")

    def test_interpolate_color(self):
        """Test linear color interpolation between two hex colors."""
        # Midpoint between black (#000000) and white (#ffffff)
        self.assertEqual(interpolate_color("#000000", "#ffffff", 0.5), "#7f7f7f")
        # 0% factor should yield original color
        self.assertEqual(interpolate_color("#102030", "#ffffff", 0.0), "#102030")
        # 100% factor should yield target color
        self.assertEqual(interpolate_color("#102030", "#ffffff", 1.0), "#ffffff")
        # Transparent fallback
        self.assertEqual(interpolate_color("transparent", "#ffffff", 0.5), "transparent")
        self.assertEqual(interpolate_color("#000000", "transparent", 0.5), "#000000")
        # Invalid format fallback
        self.assertEqual(interpolate_color("invalid", "#ffffff", 0.5), "invalid")

    def test_lighten_color(self):
        """Test lightening hex colors by specified percentages."""
        self.assertEqual(lighten_color("#000000", 50), "#7f7f7f")
        self.assertEqual(lighten_color("#ffffff", 50), "#ffffff")
        self.assertEqual(lighten_color("transparent", 10), "transparent")
        self.assertEqual(lighten_color("invalid", 10), "invalid")

    def test_darken_color(self):
        """Test darkening hex colors by specified percentages."""
        self.assertEqual(darken_color("#ffffff", 50), "#7f7f7f")
        self.assertEqual(darken_color("#000000", 50), "#000000")
        self.assertEqual(darken_color("transparent", 10), "transparent")
        self.assertEqual(darken_color("invalid", 10), "invalid")

if __name__ == '__main__':
    unittest.main()
