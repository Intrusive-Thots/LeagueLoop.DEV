import unittest
from unittest.mock import MagicMock, patch
from services.theme_service import ThemeService

class TestThemeService(unittest.TestCase):
    def setUp(self):
        self.mock_tokens = MagicMock()
        
    def test_get_color(self):
        service = ThemeService()
        service.tokens = self.mock_tokens
        
        self.mock_tokens.get.return_value = "#ff0000"
        color = service.get_color("colors.accent.gold", "#ffffff")
        
        self.mock_tokens.get.assert_called_once_with("colors", "accent", "gold", default="#ffffff")
        self.assertEqual(color, "#ff0000")

    def test_get_spacing(self):
        service = ThemeService()
        self.assertEqual(service.get_spacing(1), 8)
        self.assertEqual(service.get_spacing(3), 24)

    def test_get_radius(self):
        service = ThemeService()
        service.tokens = self.mock_tokens
        
        self.mock_tokens.get.return_value = 12
        radius = service.get_radius("md", 8)
        
        self.mock_tokens.get.assert_called_once_with("radius", "md", default=8)
        self.assertEqual(radius, 12)

    def test_get_stylesheet(self):
        service = ThemeService()
        service.tokens = self.mock_tokens
        
        self.mock_tokens.get.return_value = "dummy_val"
        qss = service.get_stylesheet()
        
        self.assertIn("dummy_val", qss)
        self.assertIn("QWidget", qss)
