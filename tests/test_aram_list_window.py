import unittest
from unittest.mock import MagicMock, patch

from ui.components.aram_list_window import _get_league_client_rect, AramListWindow


class TestAramListWindow(unittest.TestCase):
    def test_get_league_client_rect_no_user32(self):
        with patch('ctypes.windll') as mock_windll:
            del mock_windll.user32
            res = _get_league_client_rect()
            self.assertIsNone(res)

    def test_open_window_singleton(self):
        mock_master = MagicMock()
        mock_config = MagicMock()
        mock_assets = MagicMock()

        mock_inst = MagicMock()
        mock_inst.winfo_exists.return_value = True
        AramListWindow._instance = mock_inst

        res = AramListWindow.open_window(mock_master, mock_config, mock_assets)
        self.assertEqual(res, mock_inst)
        mock_inst.lift.assert_called_once()
        mock_inst.focus_force.assert_called_once()

        # Reset singleton state
        AramListWindow._instance = None


if __name__ == '__main__':
    unittest.main()
