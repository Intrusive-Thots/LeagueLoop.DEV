"""
Unit Tests for PySide6 Pages (MatchPredictorPage, PatchNotesPage, etc.)
"""
import pytest
from unittest.mock import MagicMock, patch

try:
    from PySide6.QtWidgets import QApplication
    # Ensure headless QApplication instance for PySide6 UI tests
    app = QApplication.instance() or QApplication([])
except ImportError:
    app = None

@pytest.mark.skipif(app is None, reason="PySide6 GUI not available")
def test_match_predictor_page_instantiation():
    """Test MatchPredictorPage initializes cleanly with widgets."""
    from ui.qt.pages.match_predictor_page import MatchPredictorPage
    page = MatchPredictorPage()
    assert page is not None
    assert hasattr(page, "overview_card")
    assert hasattr(page, "synergy_card")
    assert hasattr(page, "wincon_card")

@pytest.mark.skipif(app is None, reason="PySide6 GUI not available")
def test_patch_notes_page_instantiation():
    """Test PatchNotesPage initializes cleanly with widgets."""
    from ui.qt.pages.patch_notes_page import PatchNotesPage
    page = PatchNotesPage()
    assert page is not None
    assert hasattr(page, "banner_card")
    assert hasattr(page, "balance_card")
    assert hasattr(page, "engine_card")

@pytest.mark.skipif(app is None, reason="PySide6 GUI not available")
def test_accounts_page_instantiation():
    """Test AccountsPage initializes cleanly with widgets."""
    from ui.qt.pages.accounts_page import AccountsPage
    page = AccountsPage()
    assert page is not None

@pytest.mark.skipif(app is None, reason="PySide6 GUI not available")
def test_champions_page_instantiation():
    """Test ChampionsPage initializes cleanly with widgets."""
    from ui.qt.pages.champions_page import ChampionsPage
    page = ChampionsPage()
    assert page is not None

@pytest.mark.skipif(app is None, reason="PySide6 GUI not available")
def test_coach_page_instantiation():
    """Test CoachPage initializes cleanly with widgets."""
    from ui.qt.pages.coach_page import CoachPage
    page = CoachPage()
    assert page is not None

@pytest.mark.skipif(app is None, reason="PySide6 GUI not available")
def test_dashboard_page_instantiation():
    """Test DashboardPage initializes cleanly with widgets."""
    from ui.qt.pages.dashboard_page import DashboardPage
    page = DashboardPage()
    assert page is not None

@pytest.mark.skipif(app is None, reason="PySide6 GUI not available")
def test_friends_page_instantiation():
    """Test FriendsPage initializes cleanly with widgets."""
    from ui.qt.pages.friends_page import FriendsPage
    page = FriendsPage()
    assert page is not None

@pytest.mark.skipif(app is None, reason="PySide6 GUI not available")
def test_play_page_instantiation():
    """Test PlayPage initializes cleanly with widgets."""
    from ui.qt.pages.play_page import PlayPage
    page = PlayPage()
    assert page is not None

@pytest.mark.skipif(app is None, reason="PySide6 GUI not available")
def test_settings_page_instantiation():
    """Test SettingsPage initializes cleanly with widgets."""
    from ui.qt.pages.settings_page import SettingsPage
    page = SettingsPage()
    assert page is not None

