import os
import unittest

from utils.crash_reporter import CrashReporter


class TestCrashReporter(unittest.TestCase):

    def test_generate_report_creates_valid_json_file(self):
        try:
            raise ValueError("Test crash exception for CrashReporter")
        except ValueError as e:
            exc_type, exc_val, exc_tb = sys.exc_info() if 'sys' in globals() else (type(e), e, e.__traceback__)
            report_path = CrashReporter.generate_report(type(e), e, exc_tb, thread_name="TestThread")

            self.assertTrue(os.path.exists(report_path))
            self.assertTrue(report_path.endswith(".json"))

            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("Test crash exception for CrashReporter", content)
                self.assertIn("ValueError", content)
                self.assertIn("TestThread", content)

            # Cleanup test report file
            try:
                os.remove(report_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
