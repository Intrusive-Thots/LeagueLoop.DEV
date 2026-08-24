"""
The run record.

A log that cannot tell you *when* something happened, *what level* it was, or
*where one run ended and the next began* is not a record. The previous
formatter used `datefmt='%H:%M:%S'` — no date at all — and omitted the level
name entirely. These tests pin the shape of the replacement.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _run(script: str, log_dir: str) -> subprocess.CompletedProcess:
    """Run a snippet in a fresh interpreter with its own log directory.

    The logger configures handlers at import time, so a test that wants real
    files on disk has to be a separate process.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    env["LEAGUELOOP_LOG_DIR"] = log_dir
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True,
        cwd=str(ROOT), timeout=120,
    )


class TimestampTests(unittest.TestCase):
    def test_every_line_carries_a_full_date_and_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run(
                "from utils.logger import Logger\n"
                "Logger.info('T', 'hello')\n",
                tmp,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = (Path(tmp) / "debug.log").read_text(encoding="utf-8")
        # YYYY-MM-DD HH:MM:SS.mmm +ZZZZ
        self.assertRegex(
            text, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} [+-]\d{4}\s"
        )

    def test_the_level_name_is_in_the_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(
                "from utils.logger import Logger\n"
                "Logger.warning('T', 'careful')\n"
                "Logger.action('T', 'did a thing')\n",
                tmp,
            )
            text = (Path(tmp) / "debug.log").read_text(encoding="utf-8")
        self.assertIn("WARNING", text)
        self.assertIn("ACTION", text)


class FileRoutingTests(unittest.TestCase):
    def test_error_log_holds_problems_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(
                "from utils.logger import Logger\n"
                "Logger.debug('T', 'noise')\n"
                "Logger.info('T', 'ordinary')\n"
                "Logger.warning('T', 'careful')\n",
                tmp,
            )
            errors = (Path(tmp) / "error.log").read_text(encoding="utf-8")
            debug = (Path(tmp) / "debug.log").read_text(encoding="utf-8")
        self.assertIn("careful", errors)
        self.assertNotIn("ordinary", errors)
        self.assertNotIn("noise", errors)
        self.assertIn("noise", debug)
        self.assertIn("careful", debug)

    def test_a_traceback_is_recorded_not_just_the_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(
                "from utils.logger import Logger\n"
                "try:\n"
                "    raise ValueError('the actual cause')\n"
                "except ValueError as exc:\n"
                "    Logger.error('T', 'it broke', exc=exc)\n",
                tmp,
            )
            errors = (Path(tmp) / "error.log").read_text(encoding="utf-8")
        self.assertIn("Traceback", errors)
        self.assertIn("ValueError: the actual cause", errors)

    def test_the_jsonl_stream_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(
                "from utils.logger import Logger\n"
                "Logger.action('Draft', 'locked in Ahri', champion_id=103)\n",
                tmp,
            )
            lines = [
                json.loads(line)
                for line in (Path(tmp) / "session.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
        self.assertTrue(lines)
        record = lines[-1]
        for field in ("ts", "level", "tag", "thread", "session", "elapsed_s", "msg"):
            self.assertIn(field, record)
        self.assertEqual(record["level"], "ACTION")
        self.assertEqual(record["detail"]["champion_id"], 103)


class SessionRecordTests(unittest.TestCase):
    def test_a_run_is_bracketed_by_a_banner_and_a_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run(
                "from utils.session_log import session_banner, session_summary\n"
                "session_banner(shell='test', argv=['--flag'])\n"
                "session_summary(reason='test over')\n",
                tmp,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = (Path(tmp) / "debug.log").read_text(encoding="utf-8")
        self.assertIn("LeagueLoop session started", text)
        self.assertIn("LeagueLoop session ended", text)
        self.assertIn("test over", text)
        # The things you need to reproduce a report.
        for field in ("version", "python", "platform", "log dir", "shell"):
            self.assertIn(field, text)

    def test_the_summary_is_written_once_however_often_it_is_called(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(
                "from utils.session_log import session_summary\n"
                "session_summary('first')\n"
                "session_summary('second')\n",
                tmp,
            )
            text = (Path(tmp) / "debug.log").read_text(encoding="utf-8")
        self.assertEqual(text.count("LeagueLoop session ended"), 1)
        self.assertIn("first", text)

    def test_secrets_never_reach_the_log(self):
        from utils.session_log import config_snapshot

        class Config:
            def __init__(self):
                self.config = {
                    "auto_accept": True,
                    "password": "hunter2",
                    "riot_id": "Somebody#NA1",
                    "api_token": "abcdef",
                    "priority_list": [1, 2, 3, 4],
                }

        snapshot = config_snapshot(Config())
        self.assertEqual(snapshot["auto_accept"], True)
        self.assertEqual(snapshot["password"], "<redacted>")
        self.assertEqual(snapshot["riot_id"], "<redacted>")
        self.assertEqual(snapshot["api_token"], "<redacted>")
        # Long lists are summarised, not dumped.
        self.assertEqual(snapshot["priority_list"], "<4 items>")


class CrashCaptureTests(unittest.TestCase):
    def test_an_unhandled_exception_is_logged_before_the_process_dies(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run(
                "from utils.session_log import install_crash_handlers\n"
                "install_crash_handlers()\n"
                "raise RuntimeError('died on the main thread')\n",
                tmp,
            )
            self.assertNotEqual(proc.returncode, 0)
            errors = (Path(tmp) / "error.log").read_text(encoding="utf-8")
        self.assertIn("died on the main thread", errors)
        self.assertIn("Unhandled RuntimeError", errors)

    def test_a_worker_thread_crash_is_logged(self):
        """Most of this app's work happens off the GUI thread, where an
        unhandled exception is printed to a stderr nobody sees."""
        with tempfile.TemporaryDirectory() as tmp:
            _run(
                "import threading\n"
                "from utils.session_log import install_crash_handlers\n"
                "install_crash_handlers()\n"
                "def boom():\n"
                "    raise ValueError('died on a worker')\n"
                "t = threading.Thread(target=boom, name='Worker')\n"
                "t.start(); t.join()\n",
                tmp,
            )
            errors = (Path(tmp) / "error.log").read_text(encoding="utf-8")
        self.assertIn("died on a worker", errors)
        self.assertIn("Worker", errors)


class InMemoryTests(unittest.TestCase):
    def setUp(self):
        from utils.logger import Logger

        Logger.reset_for_tests()

    def test_records_carry_a_timestamp_and_a_thread(self):
        from utils.logger import Logger

        Logger.info("Tag", "something happened")
        entry = Logger.get_logs()[-1]
        self.assertRegex(entry["ts"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(entry["level"], "INFO")
        self.assertEqual(entry["module"], "Tag")   # legacy key, still present
        self.assertEqual(entry["tag"], "Tag")
        self.assertIn("thread", entry)

    def test_counts_and_problem_count(self):
        from utils.logger import Logger

        Logger.info("T", "a")
        Logger.warning("T", "b")
        Logger.error("T", "c")
        Logger.action("T", "d")
        counts = Logger.counts()
        self.assertEqual(counts["WARNING"], 1)
        self.assertEqual(counts["ERROR"], 1)
        self.assertEqual(counts["ACTION"], 1)
        self.assertEqual(Logger.problem_count(), 2)

    def test_the_buffer_is_bounded(self):
        from utils.logger import Logger

        for i in range(Logger.MAX_LOGS + 50):
            Logger.debug("T", i)
        self.assertEqual(len(Logger.get_logs()), Logger.MAX_LOGS)

    def test_filtering(self):
        from utils.logger import Logger

        Logger.info("A", "one")
        Logger.error("B", "two")
        self.assertEqual(len(Logger.get_logs(module="A")), 1)
        self.assertEqual(len(Logger.get_logs(level="ERROR")), 1)
        self.assertEqual(Logger.get_logs(limit=0), [])

    def test_logging_a_value_that_cannot_be_serialised_does_not_raise(self):
        from utils.logger import Logger

        class Awkward:
            def __repr__(self):
                raise RuntimeError("no repr for you")

        Logger.info("T", "fine", thing=Awkward())  # must not raise


class SilentHandlerTests(unittest.TestCase):
    """A swallowed exception is the most common reason this app looks like it
    is working while doing nothing. New ones must not be added."""

    #: Files where a bare `pass` is still legitimate.
    ALLOWED = {"logger.py", "session_log.py"}

    def test_no_new_silent_exception_handlers(self):
        import ast

        offenders = []
        for path in SRC.rglob("*.py"):
            if path.name in self.ALLOWED:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                body = [
                    b for b in node.body
                    if not (isinstance(b, ast.Expr)
                            and isinstance(b.value, ast.Constant)
                            and isinstance(b.value.value, str))
                ]
                if len(body) != 1 or not isinstance(body[0], ast.Pass):
                    continue
                names = set()
                target = node.type
                parts = target.elts if isinstance(target, ast.Tuple) else [target]
                for part in parts:
                    if isinstance(part, ast.Name):
                        names.add(part.id)
                    elif isinstance(part, ast.Attribute):
                        names.add(part.attr)
                    elif part is None:
                        names.add("bare")
                if names & {"Exception", "BaseException", "bare"}:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{body[0].lineno}"
                    )
        self.assertEqual(
            offenders, [],
            "These handlers discard a broad exception with no record. Use "
            "`except Exception as exc: Logger.debug(tag, ..., exc=exc)` — or "
            "run `python tools/log_silent_excepts.py --write`.\n"
            + "\n".join(offenders),
        )


class NoPrintToStderrTests(unittest.TestCase):
    """Startup failures used to print to a stderr that is invisible when the
    app is launched from a shortcut or a .bat that closes on exit."""

    def test_startup_reports_through_the_logger(self):
        """`run.py` and `core/main.py` are the two files that run before the
        window exists, so they are the two that can only report through the
        log."""
        for path in (SRC.parent / "run.py", SRC / "core" / "main.py"):
            body = path.read_text(encoding="utf-8-sig")
            self.assertNotIn(
                "file=sys.stderr", body,
                "%s writes to a stderr nobody sees when launched from a "
                "shortcut" % path.name,
            )


if __name__ == "__main__":
    unittest.main()
