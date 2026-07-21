import unittest
from unittest.mock import MagicMock

from services.login_automation import LoginAutomation


class TestLoginAutomation(unittest.TestCase):

    def setUp(self):
        self.riot_client_mock = MagicMock()
        self.riot_client_mock.is_riot_client_running.return_value = True
        self.riot_client_mock.connect.return_value = True
        self.riot_client_mock.get_session.return_value = {"type": "authenticated"}

        self.login_auto = LoginAutomation(self.riot_client_mock)

    def test_find_riot_client_window_type(self):
        # Handle lookup returns int HWND (0 if not found)
        hwnd = self.login_auto._find_riot_client_window(timeout=1)
        self.assertIsInstance(hwnd, int)

    def test_login_incomplete_credentials(self):
        logged_msgs = []

        def log_cb(msg):
            logged_msgs.append(msg)

        self.login_auto.login("", "", "TestAccount", 0, log_func=log_cb)
        self.assertIn("Account credentials incomplete.", logged_msgs)


if __name__ == "__main__":
    unittest.main()
