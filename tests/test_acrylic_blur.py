import unittest
from unittest.mock import MagicMock, patch

from utils.acrylic_blur import apply_acrylic_blur, remove_blur, _get_hwnd

class TestAcrylicBlur(unittest.TestCase):

    def setUp(self):
        self.mock_window = MagicMock()
        self.mock_window.winfo_id.return_value = 12345

    @patch("platform.system")
    def test_non_windows_skip(self, mock_system):
        mock_system.return_value = "Linux"
        result = apply_acrylic_blur(self.mock_window)
        self.assertFalse(result)

        result_remove = remove_blur(self.mock_window)
        self.assertFalse(result_remove)

    @patch("ctypes.windll.user32.GetParent")
    @patch("ctypes.windll.user32.SetWindowCompositionAttribute")
    @patch("platform.system")
    def test_windows_acrylic_success(self, mock_system, mock_set_attrib, mock_get_parent):
        mock_system.return_value = "Windows"
        mock_get_parent.return_value = 67890
        mock_set_attrib.return_value = 1

        res = apply_acrylic_blur(self.mock_window)
        self.assertTrue(res)
        self.assertTrue(mock_set_attrib.called)

    @patch("ctypes.windll.user32.GetParent")
    @patch("ctypes.windll.user32.SetWindowCompositionAttribute")
    @patch("platform.system")
    def test_windows_remove_blur(self, mock_system, mock_set_attrib, mock_get_parent):
        mock_system.return_value = "Windows"
        mock_get_parent.return_value = 67890
        mock_set_attrib.return_value = 1

        res = remove_blur(self.mock_window)
        self.assertTrue(res)
        self.assertTrue(mock_set_attrib.called)

if __name__ == '__main__':
    unittest.main()
