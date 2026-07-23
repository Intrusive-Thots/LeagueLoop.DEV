import unittest
from utils.color_utils import hex_to_rgb

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

if __name__ == '__main__':
    unittest.main()
