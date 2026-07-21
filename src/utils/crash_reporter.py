"""
Crash Reporter Module
Generates structured JSON crash dumps for uncaught application exceptions.
"""
import datetime
import json
import os
import platform
import sys
import traceback
from typing import Optional

import psutil
from core.version import __version__


class CrashReporter:
    """Captures application crashes and writes structured JSON crash reports."""

    @classmethod
    def get_crash_dir(cls) -> str:
        """Returns the path to the crash dump directory."""
        appdata = os.environ.get("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local"))
        crash_dir = os.path.join(appdata, "LeagueLoop", "crashes")
        os.makedirs(crash_dir, exist_ok=True)
        return crash_dir

    @classmethod
    def generate_report(
        cls,
        exc_type: type,
        exc_value: BaseException,
        exc_tb: Optional[object],
        thread_name: str = "MainThread",
    ) -> str:
        """Generates and writes a JSON crash dump file."""
        crash_dir = cls.get_crash_dir()
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        report_path = os.path.join(crash_dir, f"crash_{timestamp_str}.json")

        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        formatted_tb = "".join(tb_lines)

        mem_info = psutil.virtual_memory()

        report_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "app_version": __version__,
            "python_version": sys.version,
            "platform": platform.platform(),
            "os_name": platform.system(),
            "os_release": platform.release(),
            "thread_name": thread_name,
            "exception": {
                "type": exc_type.__name__ if exc_type else "UnknownException",
                "message": str(exc_value),
                "traceback": formatted_tb,
            },
            "system_metrics": {
                "total_memory_mb": round(mem_info.total / (1024 * 1024), 2),
                "available_memory_mb": round(mem_info.available / (1024 * 1024), 2),
                "cpu_percent": psutil.cpu_percent(),
            },
        }

        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=4)
        except Exception:
            pass

        return report_path
