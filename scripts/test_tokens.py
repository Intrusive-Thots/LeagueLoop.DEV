import unittest
from src.ui.theme.token_loader import DesignTokens, TOKENS

class TestDesignTokens(unittest.TestCase):
    def test_get_simple(self):
        self.assertEqual(TOKENS.get("spacing"), {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32})
        self.assertEqual(TOKENS.get("spacing.md"), 12)
        self.assertEqual(TOKENS.get("spacing", "md"), 12)

    def test_get_nested(self):
        self.assertEqual(TOKENS.get("colors.background.app"), "#091428")
        self.assertEqual(TOKENS.get("colors", "background", "app"), "#091428")
        self.assertEqual(TOKENS.get("colors.background", "app"), "#091428")
        self.assertEqual(TOKENS.get("colors", "background.app"), "#091428")

    def test_get_default(self):
        self.assertEqual(TOKENS.get("nonexistent"), None)
        self.assertEqual(TOKENS.get("nonexistent", default="fallback"), "fallback")
        self.assertEqual(TOKENS.get("colors.nonexistent", default="fallback"), "fallback")

    def test_get_default_positional(self):
        self.assertEqual(TOKENS.get("colors.text.primary", "#FFFFFF"), "#F0E6D2")
        self.assertEqual(TOKENS.get("colors.text.nonexistent", "#FFFFFF"), "#FFFFFF")

if __name__ == '__main__':
    unittest.main()
