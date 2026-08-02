import unittest
import json
from unittest.mock import mock_open, patch

from ui.theme.token_loader import DesignTokens, DEFAULT_TOKENS

class TestTokenLoader(unittest.TestCase):

    @patch('builtins.open', new_callable=mock_open, read_data='{"colors": {"primary": "#ffffff"}}')
    def test_load_tokens_success(self, mock_file):
        tokens = DesignTokens()
        self.assertEqual(tokens.tokens, {"colors": {"primary": "#ffffff"}})
        mock_file.assert_called_once()

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_load_tokens_file_not_found(self, mock_file):
        tokens = DesignTokens()
        self.assertEqual(tokens.tokens, DEFAULT_TOKENS)
        mock_file.assert_called_once()

    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    def test_load_tokens_invalid_json(self, mock_file):
        tokens = DesignTokens()
        self.assertEqual(tokens.tokens, DEFAULT_TOKENS)
        mock_file.assert_called_once()

    def test_theme_memory_optimization(self):
        tokens = DesignTokens()
        tokens.get("colors", "background", "app")
        diag = tokens.optimize_theme_memory()
        self.assertTrue(diag["memory_optimized"])
        self.assertEqual(diag["lru_get_memoized_currsize"], 0)

    def test_get_theme_memory_footprint(self):
        tokens = DesignTokens()
        tokens.get("colors.background.panel")
        diag = tokens.get_theme_memory_footprint()
        self.assertIn("lru_get_memoized_currsize", diag)
        self.assertIn("lru_get_memoized_hits", diag)
        self.assertIn("lru_parse_keys_currsize", diag)
        self.assertTrue(diag["memory_optimized"])

if __name__ == '__main__':
    unittest.main()
