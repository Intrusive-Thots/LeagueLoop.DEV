import unittest
from unittest.mock import patch, MagicMock
import platform
import ctypes

from utils.acrylic_blur import apply_acrylic_blur, remove_blur, _get_hwnd

class TestAcrylicBlur(unittest.TestCase):
    def setUp(self):
        self.mock_tk_window = MagicMock()
        self.mock_tk_window.winfo_id.return_value = 12345

    @patch('utils.acrylic_blur.platform.system')
    def test_apply_acrylic_blur_non_windows(self, mock_system):
        mock_system.return_value = "Linux"
        result = apply_acrylic_blur(self.mock_tk_window)
        self.assertFalse(result)

    @patch('utils.acrylic_blur.platform.system')
    @patch('utils.acrylic_blur._get_hwnd')
    @patch('utils.acrylic_blur.ctypes.windll', create=True)
    def test_apply_acrylic_blur_success(self, mock_windll, mock_get_hwnd, mock_system):
        mock_system.return_value = "Windows"
        mock_get_hwnd.return_value = 54321

        mock_user32 = MagicMock()
        mock_user32.SetWindowCompositionAttribute.return_value = 1
        mock_windll.user32 = mock_user32

        result = apply_acrylic_blur(self.mock_tk_window)
        self.assertTrue(result)
        mock_user32.SetWindowCompositionAttribute.assert_called_once()

    @patch('utils.acrylic_blur.platform.system')
    @patch('utils.acrylic_blur._get_hwnd')
    @patch('utils.acrylic_blur.ctypes.windll', create=True)
    def test_apply_acrylic_blur_fallback_success(self, mock_windll, mock_get_hwnd, mock_system):
        mock_system.return_value = "Windows"
        mock_get_hwnd.return_value = 54321

        mock_user32 = MagicMock()
        mock_user32.SetWindowCompositionAttribute.side_effect = [0, 1]
        mock_windll.user32 = mock_user32

        result = apply_acrylic_blur(self.mock_tk_window, fallback_blur=True)
        self.assertTrue(result)
        self.assertEqual(mock_user32.SetWindowCompositionAttribute.call_count, 2)

    @patch('utils.acrylic_blur.platform.system')
    @patch('utils.acrylic_blur._get_hwnd')
    @patch('utils.acrylic_blur.ctypes.windll', create=True)
    def test_apply_acrylic_blur_all_fail(self, mock_windll, mock_get_hwnd, mock_system):
        mock_system.return_value = "Windows"
        mock_get_hwnd.return_value = 54321

        mock_user32 = MagicMock()
        mock_user32.SetWindowCompositionAttribute.return_value = 0
        mock_windll.user32 = mock_user32

        result = apply_acrylic_blur(self.mock_tk_window, fallback_blur=True)
        self.assertFalse(result)

    @patch('utils.acrylic_blur.platform.system')
    @patch('utils.acrylic_blur._get_hwnd')
    def test_apply_acrylic_blur_exception(self, mock_get_hwnd, mock_system):
        mock_system.return_value = "Windows"
        mock_get_hwnd.side_effect = Exception("Test Exception")

        result = apply_acrylic_blur(self.mock_tk_window)
        self.assertFalse(result)

    @patch('utils.acrylic_blur.platform.system')
    def test_remove_blur_non_windows(self, mock_system):
        mock_system.return_value = "Linux"
        result = remove_blur(self.mock_tk_window)
        self.assertFalse(result)

    @patch('utils.acrylic_blur.platform.system')
    @patch('utils.acrylic_blur._get_hwnd')
    @patch('utils.acrylic_blur.ctypes.windll', create=True)
    def test_remove_blur_success(self, mock_windll, mock_get_hwnd, mock_system):
        mock_system.return_value = "Windows"
        mock_get_hwnd.return_value = 54321

        mock_user32 = MagicMock()
        mock_user32.SetWindowCompositionAttribute.return_value = 1
        mock_windll.user32 = mock_user32

        result = remove_blur(self.mock_tk_window)
        self.assertTrue(result)
        mock_user32.SetWindowCompositionAttribute.assert_called_once()

    @patch('utils.acrylic_blur.platform.system')
    @patch('utils.acrylic_blur._get_hwnd')
    def test_remove_blur_exception(self, mock_get_hwnd, mock_system):
        mock_system.return_value = "Windows"
        mock_get_hwnd.side_effect = Exception("Test Exception")

        result = remove_blur(self.mock_tk_window)
        self.assertFalse(result)

    @patch('utils.acrylic_blur.ctypes.windll', create=True)
    def test_get_hwnd(self, mock_windll):
        mock_user32 = MagicMock()
        mock_user32.GetParent.return_value = 54321
        mock_windll.user32 = mock_user32

        hwnd = _get_hwnd(self.mock_tk_window)
        self.assertEqual(hwnd, 54321)
        self.mock_tk_window.winfo_id.assert_called_once()
        mock_user32.GetParent.assert_called_once_with(12345)

if __name__ == '__main__':
    unittest.main()
