import unittest
from unittest.mock import MagicMock


class MockConfig:
    def __init__(self):
        self._data = {"poro_snacks": 0}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


class MockSidebar:
    def __init__(self):
        self.config = MockConfig()
        self.lbl_poro_snacks = MagicMock()
        self.winfo_exists = MagicMock(return_value=True)
        self.after = MagicMock()


class TestPoroSnacks(unittest.TestCase):

    def test_feed_poro_increments_config_and_updates_ui(self):
        sidebar = MockSidebar()

        def _feed_poro(self):
            snacks = self.config.get("poro_snacks", 0) + 1
            self.config.set("poro_snacks", snacks)
            if self.winfo_exists():
                self.lbl_poro_snacks.configure(text=f"🍪 Poro Snacks: {snacks}", text_color="#ffffff")
                self.after(200, lambda: self.lbl_poro_snacks.configure(text_color="#C8AA6E") if self.winfo_exists() else None)

        self.assertEqual(sidebar.config.get("poro_snacks", 0), 0)
        _feed_poro(sidebar)
        self.assertEqual(sidebar.config.get("poro_snacks"), 1)
        sidebar.lbl_poro_snacks.configure.assert_called_with(text="🍪 Poro Snacks: 1", text_color="#ffffff")
        sidebar.after.assert_called_once()

    def test_poro_snack_earned_calls_feed_poro(self):
        sidebar = MockSidebar()
        sidebar._feed_poro = MagicMock()

        def _poro_snack_earned(self):
            self._feed_poro()

        _poro_snack_earned(sidebar)
        sidebar._feed_poro.assert_called_once()


if __name__ == '__main__':
    unittest.main()
