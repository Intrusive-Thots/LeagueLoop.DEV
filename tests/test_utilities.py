"""
Consolidated unit tests for utility modules:
- Constants and version
- Path utilities  
- Token loader / theme
- Color utilities
- Logger
- Config manager
"""
import unittest
import json
import re
import os
import sys
from unittest.mock import patch, mock_open, MagicMock

# Import modules under test
from core import constants
from core.version import __version__
from utils.path_utils import get_asset_path
from ui.theme.token_loader import DesignTokens, DEFAULT_TOKENS
from utils.logger import Logger


class TestConstantsAndVersion(unittest.TestCase):
    def test_version_format(self):
        # Format: 1-{month}-{days_left_in_year}-{HHMM}
        pattern = r"^1-\d{2}-\d{1,3}-\d{4}$"
        assert re.match(pattern, __version__) is not None

    def test_queue_constants(self):
        assert constants.QUEUE_DRAFT == 400
        assert constants.QUEUE_RANKED_SOLO == 420
        assert constants.QUEUE_RANKED_FLEX == 440
        assert constants.QUEUE_ARAM == 450
        assert constants.QUEUE_ARENA == 1700
        assert constants.QUEUE_ARENA_3V6 == 1710

    def test_ui_and_timing_constants(self):
        assert constants.SIDEBAR_WIDTH > 0
        assert constants.SIDEBAR_HEIGHT > 0
        assert constants.DOCKING_POLL_INTERVAL > 0
        assert constants.LCU_REQUEST_TIMEOUT > 0


class TestPathUtils(unittest.TestCase):
    def test_get_asset_path_with_meipass(self):
        mock_meipass = "/tmp/_MEI123456"
        with patch.object(sys, '_MEIPASS', mock_meipass, create=True):
            result = get_asset_path("assets/image.png")
            expected = os.path.join(mock_meipass, "assets/image.png")
            self.assertEqual(result, expected)

    def test_get_asset_path_without_meipass(self):
        original_has_meipass = hasattr(sys, '_MEIPASS')
        if original_has_meipass:
            original_meipass = getattr(sys, '_MEIPASS')
            del sys._MEIPASS
        try:
            result = get_asset_path("assets/image.png")
            expected = os.path.join(os.path.abspath("."), "assets/image.png")
            self.assertEqual(result, expected)
        finally:
            if original_has_meipass:
                sys._MEIPASS = original_meipass


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


class TestLoggerGetLogs(unittest.TestCase):
    def setUp(self):
        self.original_logs = getattr(Logger, '_logs', None)
        self.original_prune = getattr(Logger, '_prune', None)
        Logger._logs = []
        Logger._prune = MagicMock()

    def tearDown(self):
        if self.original_logs is not None:
            Logger._logs = self.original_logs
        else:
            delattr(Logger, '_logs')
        if self.original_prune is not None:
            Logger._prune = self.original_prune
        else:
            delattr(Logger, '_prune')

    def test_get_logs_empty(self):
        if not hasattr(Logger, 'get_logs'):
            self.skipTest("Logger does not have get_logs attribute")
        logs = Logger.get_logs()
        self.assertEqual(logs, [])
        Logger._prune.assert_called_once()

    def test_get_logs_no_filter_no_limit(self):
        if not hasattr(Logger, 'get_logs'):
            self.skipTest("Logger does not have get_logs attribute")
        Logger._logs.extend([
            {"module": "core", "msg": "test1"},
            {"module": "ui", "msg": "test2"},
            {"module": "core", "msg": "test3"},
        ])
        logs = Logger.get_logs()
        self.assertEqual(len(logs), 3)

    def test_get_logs_with_limit(self):
        if not hasattr(Logger, 'get_logs'):
            self.skipTest("Logger does not have get_logs attribute")
        Logger._logs.extend([
            {"module": "core", "msg": "test1"},
            {"module": "ui", "msg": "test2"},
            {"module": "core", "msg": "test3"},
        ])
        logs = Logger.get_logs(limit=2)
        self.assertEqual(len(logs), 2)

    def test_get_logs_with_module_filter(self):
        if not hasattr(Logger, 'get_logs'):
            self.skipTest("Logger does not have get_logs attribute")
        Logger._logs.extend([
            {"module": "core", "msg": "test1"},
            {"module": "ui", "msg": "test2"},
            {"module": "core", "msg": "test3"},
        ])
        logs = Logger.get_logs(module="core")
        self.assertEqual(len(logs), 2)

    def test_logger_warn_alias(self):
        Logger._logs.clear()
        Logger.warn("TEST", "Warning message via warn alias")
        logs = Logger.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["level"], "WARNING")
        self.assertEqual(logs[0]["module"], "TEST")
        self.assertEqual(logs[0]["msg"], "Warning message via warn alias")



class TestConfigManager(unittest.TestCase):
    def test_load_default_config(self):
        from services.asset_manager import ConfigManager, DEFAULT_CONFIG
        with patch('os.path.exists', return_value=False):
            config = ConfigManager()
            self.assertEqual(config.cfg, DEFAULT_CONFIG)

    def test_load_existing_config(self):
        from services.asset_manager import ConfigManager, DEFAULT_CONFIG
        test_config = DEFAULT_CONFIG.copy()
        test_config["auto_accept"] = True
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(test_config))):
            config = ConfigManager()
            self.assertEqual(config.get("auto_accept"), True)

    def test_load_corrupted_config(self):
        from services.asset_manager import ConfigManager, DEFAULT_CONFIG
        corrupted_json = "{bad_json: true,"
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=corrupted_json)), \
             patch('services.asset_manager.Logger.error') as mock_logger:
            config = ConfigManager()
            self.assertEqual(config.cfg, DEFAULT_CONFIG)
            mock_logger.assert_called_once()

    def test_set_and_save(self):
        from services.asset_manager import ConfigManager, USER_CONFIG_FILE as CONFIG_FILE
        with patch('os.path.exists', return_value=False), \
             patch('os.makedirs'), \
             patch('os.replace') as mock_replace, \
             patch('builtins.open', mock_open()) as mocked_file:
            config = ConfigManager()
            config.set("auto_accept", True)
            self.assertEqual(config.get("auto_accept"), True)
            mocked_file.assert_called_with(CONFIG_FILE + ".tmp", "w", encoding="utf-8")
            mock_replace.assert_called_with(CONFIG_FILE + ".tmp", CONFIG_FILE)


class TestBuildValidator(unittest.TestCase):
    def test_verify_system_wide_health(self):
        from tools import build_validator
        health = build_validator.verify_system_wide_health()
        self.assertIn("status", health)
        self.assertIn("version", health)
        self.assertIn("files_ok", health)
        self.assertIn("test_environment_ok", health)
        self.assertIn("duration_ms", health)

    def test_get_build_validation_telemetry(self):
        from tools import build_validator
        telemetry = build_validator.get_build_validation_telemetry()
        self.assertIn("validation_cycles_count", telemetry)
        self.assertIn("passed_cycles_count", telemetry)
        self.assertIn("failed_cycles_count", telemetry)
        self.assertIn("pass_rate_pct", telemetry)

    @patch('tools.build_validator.validate_test_suite', return_value=True)
    def test_run_full_validation_cycle(self, mock_test_suite):
        from tools import build_validator
        res = build_validator.run_full_validation_cycle()
        self.assertIn("passed", res)
        self.assertIn("version", res)
        self.assertIn("files_ok", res)
        self.assertIn("tests_ok", res)
        self.assertIn("telemetry", res)
        self.assertTrue(res["tests_ok"])


if __name__ == '__main__':
    unittest.main()
