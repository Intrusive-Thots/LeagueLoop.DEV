import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import unittest
from unittest.mock import MagicMock, patch

from tests.test_ui_components import DummyWidget, mock_ctk, mock_tk, _purge_ui_modules


_patcher = None


def setUpModule():
    global _patcher
    _purge_ui_modules()
    _patcher = patch.dict(sys.modules, {
        'customtkinter': mock_ctk,
        'tkinter': mock_tk,
    })
    _patcher.start()


def tearDownModule():
    global _patcher
    if _patcher:
        _patcher.stop()
    _purge_ui_modules()


class TestFriendListCollapse(unittest.TestCase):
    def setUp(self):
        sys.modules['customtkinter'] = mock_ctk
        sys.modules['tkinter'] = mock_tk
        self.mock_master = DummyWidget()
        self.mock_config = MagicMock()
        self.mock_config.get.return_value = []
        self.mock_lcu = MagicMock()

    @patch("ui.components.factory.make_card")
    @patch("ui.components.friend_list.EventBus")
    def test_friend_list_collapse_toggle(self, mock_eventbus, mock_make_card):
        from ui.components.friend_list import FriendPriorityList

        mock_card = DummyWidget()
        mock_toggle_ctrl = MagicMock()
        mock_toggle_ctrl.is_expanded = True
        mock_card._toggle_controller = mock_toggle_ctrl
        mock_card._header = DummyWidget()
        mock_make_card.return_value = mock_card

        fl = FriendPriorityList(self.mock_master, config=self.mock_config, lcu=self.mock_lcu)

        # Initial state should be expanded
        self.assertTrue(fl._expanded)

        # Toggle collapse
        fl._toggle_collapse()
        mock_toggle_ctrl.toggle.assert_called_once()

        # Simulate toggle controller state change to collapsed
        mock_toggle_ctrl.is_expanded = False
        self.assertFalse(fl._expanded)

        # Calling collapse when already collapsed should be a no-op
        mock_toggle_ctrl.toggle.reset_mock()
        fl.collapse()
        mock_toggle_ctrl.toggle.assert_not_called()

        # Calling expand should toggle back
        fl.expand()
        mock_toggle_ctrl.toggle.assert_called_once()

    @patch("ui.components.factory.make_card")
    @patch("ui.components.friend_list.EventBus")
    def test_friend_list_fallback_when_no_controller(self, mock_eventbus, mock_make_card):
        from ui.components.friend_list import FriendPriorityList

        mock_card = DummyWidget()
        mock_card._header = DummyWidget()
        mock_make_card.return_value = mock_card

        fl = FriendPriorityList(self.mock_master, config=self.mock_config, lcu=self.mock_lcu)
        self.assertTrue(fl._expanded)

        fl._toggle_collapse()
        self.assertFalse(fl._expanded)

        fl._toggle_collapse()
        self.assertTrue(fl._expanded)


if __name__ == "__main__":
    unittest.main()

