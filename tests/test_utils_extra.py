from unittest.mock import MagicMock, patch
import pytest
import sys
from PySide6.QtWidgets import QApplication, QWidget, QScrollArea, QAbstractScrollArea

from utils.acrylic_blur import apply_acrylic_blur, remove_blur, _get_hwnd
from utils.smooth_scroll import apply_smooth_scroll
from utils.focus_states import apply_focus_ring, scroll_to_widget

@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])

def test_get_hwnd():
    assert _get_hwnd(12345) == 12345

    mock_widget = MagicMock()
    mock_widget.winId.return_value = 99999
    assert _get_hwnd(mock_widget) == 99999

def test_acrylic_blur_non_windows(qapp):
    with patch("platform.system", return_value="Linux"):
        widget = QWidget()
        assert apply_acrylic_blur(widget) is False
        assert remove_blur(widget) is False

def test_acrylic_blur_windows(qapp):
    with patch("platform.system", return_value="Windows"):
        with patch("ctypes.windll.user32.SetWindowCompositionAttribute", return_value=1):
            widget = QWidget()
            assert apply_acrylic_blur(widget) is True
            assert remove_blur(widget) is True

def test_smooth_scroll(qapp):
    scroll_area = QScrollArea()
    apply_smooth_scroll(scroll_area)
    assert scroll_area.viewport() is not None

def test_focus_states(qapp):
    widget = QWidget()
    apply_focus_ring(widget)
    assert "#C8AA6E" in widget.styleSheet()

    scroll_area = QScrollArea()
    scroll_to_widget(scroll_area, widget)
