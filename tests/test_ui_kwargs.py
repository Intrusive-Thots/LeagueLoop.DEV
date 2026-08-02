import sys
import unittest
from unittest.mock import MagicMock, patch

class TestUIKwargs(unittest.TestCase):
    def setUp(self):
        self.root = MagicMock()
        self.config_mock = MagicMock()
        self.config_mock.get.return_value = {}
        self.assets_mock = MagicMock()

    def test_priority_grid_instantiation(self):
        """Test that PriorityIconGrid instantiates without ValueError from unsupported kwargs."""
        mods_to_mock = {
            'customtkinter': MagicMock(),
            'tkinter': MagicMock(),
            'tkinterdnd2': MagicMock(),
            'tkinterdnd2.TkinterDnD': MagicMock(),
        }
        with patch.dict(sys.modules, mods_to_mock):
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith('ui.components.priority_grid') or mod_name.startswith('ui.components.factory'):
                    sys.modules.pop(mod_name, None)
            from ui.components.priority_grid import PriorityIconGrid
            try:
                grid = PriorityIconGrid(self.root, self.config_mock, self.assets_mock)
                self.assertIsNotNone(grid)
            except ValueError as e:
                self.fail(f"PriorityIconGrid instantiation failed with ValueError: {e}")

    def test_factory_make_input(self):
        """Test that factory.make_input instantiates without ValueError."""
        mods_to_mock = {
            'customtkinter': MagicMock(),
            'tkinter': MagicMock(),
        }
        with patch.dict(sys.modules, mods_to_mock):
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith('ui.components.factory'):
                    sys.modules.pop(mod_name, None)
            from ui.components.factory import make_input
            try:
                entry = make_input(self.root, placeholder="Test", cursor="hand2")
                self.assertIsNotNone(entry)
            except ValueError as e:
                self.fail(f"make_input instantiation failed with ValueError: {e}")

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
