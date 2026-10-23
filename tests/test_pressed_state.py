import unittest
from ui.components.pressed_state import pressed_color, PRESSED_FALLBACK


class PressedColorTests(unittest.TestCase):
    def test_darkens_hover(self):
        self.assertNotEqual(pressed_color("#C8AA6E", "#D8BC82").lower(), "#d8bc82")

    def test_transparent_hover_uses_fg(self):
        self.assertNotEqual(pressed_color("#0F1923", "transparent"), PRESSED_FALLBACK)

    def test_transparent_everything_falls_back(self):
        self.assertEqual(pressed_color("transparent", "transparent"), PRESSED_FALLBACK)

    def test_tuple_uses_dark_mode(self):
        self.assertTrue(pressed_color(("#FFFFFF", "#C8AA6E"), None).startswith("#"))
