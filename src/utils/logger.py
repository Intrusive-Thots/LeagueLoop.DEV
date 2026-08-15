"""
Logger Module
Handles application logging to file and console using standard logging module.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

import tempfile

# Resolve a writable log directory — prefer %LOCALAPPDATA%/LeagueLoop, fall back to TEMP
_appdata = os.environ.get("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local"))
_log_dir = os.path.join(_appdata, "LeagueLoop")

try:
    os.makedirs(_log_dir, exist_ok=True)
    # Quick write-test
    _test_path = os.path.join(_log_dir, ".logtest")
    with open(_test_path, "w") as _f:
        _f.write("ok")
    os.remove(_test_path)
except Exception:
    _log_dir = os.path.join(tempfile.gettempdir(), "LeagueLoop")
    os.makedirs(_log_dir, exist_ok=True)

# Set up the Python rotating file logger
_log_format = '[%(asctime)s.%(msecs)03d] [%(threadName)s] %(message)s'
_date_format = '%H:%M:%S'

formatter = logging.Formatter(_log_format, datefmt=_date_format)

# Main Logger
_logger = logging.getLogger("LeagueLoop")
# Honor LOG_LEVEL env var (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default DEBUG.
_log_level_name = os.environ.get("LOG_LEVEL", "DEBUG").upper()
_log_level = getattr(logging, _log_level_name, logging.DEBUG)
_logger.setLevel(_log_level)

if not _logger.handlers:
    # File Handler - ALL Logs (5MB max size, keeps 3 backups)
    file_handler = RotatingFileHandler(
        os.path.join(_log_dir, 'debug.log'), maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Error File Handler - ERROR/CRITICAL Logs Only
    error_handler = RotatingFileHandler(
        os.path.join(_log_dir, 'error.log'), maxBytes=2*1024*1024, backupCount=2, encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    
    _logger.addHandler(file_handler)
    _logger.addHandler(error_handler)
    _logger.addHandler(console_handler)

class Logger:
    """Provides standard logging access."""
    
    _logs = []
    MAX_LOGS = 1000

    @classmethod
    def _prune(cls):
        """Prunes the in-memory logs list if it exceeds MAX_LOGS."""
        if len(cls._logs) > cls.MAX_LOGS:
            cls._logs = cls._logs[-cls.MAX_LOGS:]

    @classmethod
    def _add_log(cls, level, tag, msg):
        """Helper to append a log to the in-memory list."""
        cls._logs.append({
            "level": level,
            "module": tag,
            "msg": msg
        })
        cls._prune()

    @classmethod
    def get_logs(cls, module=None, limit=None):
        """Retrieves in-memory logs, optionally filtered by module and/or limited."""
        cls._prune()
        filtered = cls._logs
        if module is not None:
            filtered = [log for log in filtered if log.get("module") == module]
        if limit is not None:
            if limit <= 0:
                return []
            filtered = filtered[-limit:]
        return filtered

    @classmethod
    def debug(cls, tag, msg):
        """Log a debug message."""
        _logger.debug(f"[{tag}] {msg}")
        cls._add_log("DEBUG", tag, msg)

    @classmethod
    def error(cls, tag, msg):
        """Log an error message."""
        _logger.error(f"[{tag}] {msg}")
        cls._add_log("ERROR", tag, msg)

    @classmethod
    def info(cls, tag, msg):
        """Log an info message."""
        _logger.info(f"[{tag}] {msg}")
        cls._add_log("INFO", tag, msg)

    @classmethod
    def warning(cls, tag, msg):
        """Log a warning message."""
        _logger.warning(f"[{tag}] {msg}")
        cls._add_log("WARNING", tag, msg)
