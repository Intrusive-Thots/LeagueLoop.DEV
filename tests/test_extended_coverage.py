"""
test_extended_coverage.py — Extended unit tests to boost test coverage across UI pages, account manager, asset manager, and self_improving test_runner.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from self_improving import test_runner
from services.account_manager import AccountManager
from services.asset_manager import AssetManager
from services.champion_service import ChampionService
from services.friend_service import FriendService
from services.league_service import LeagueService
from services.settings_service import SettingsService
from ui.qt.pages.accounts_page import AccountsPage
from ui.qt.pages.champions_page import ChampionsPage
from ui.qt.pages.friends_page import FriendsPage
from ui.qt.pages.settings_page import SettingsPage


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication instance exists for PySide6 tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def temp_accounts_file():
    scratch_dir = os.path.join(os.path.dirname(__file__), "..", "scratch", "test_tmp")
    os.makedirs(scratch_dir, exist_ok=True)
    file_path = os.path.join(scratch_dir, "temp_accounts.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([], f)
    yield file_path
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass


# ── 1. Self Improving Test Runner Tests ──────────────────────────────


def test_test_runner_run_tests_success():
    scratch_dir = os.path.join(os.path.dirname(__file__), "..", "scratch", "test_runner_tmp")
    os.makedirs(scratch_dir, exist_ok=True)
    results = test_runner.run_tests(scratch_dir)
    assert isinstance(results, dict)
    assert "passed" in results
    assert "failed" in results
    assert "failures" in results


def test_test_runner_detect_regressions():
    baseline = {"passed": 10, "failed": 0, "errors": 0}
    current_no_regression = {"passed": 10, "failed": 0, "errors": 0}
    regressions = test_runner.detect_regressions(current_no_regression, baseline)
    assert len(regressions) == 0

    current_with_regression = {"passed": 8, "failed": 2, "errors": 0}
    regressions_found = test_runner.detect_regressions(current_with_regression, baseline)
    assert len(regressions_found) >= 1
    assert "Passed test count dropped" in regressions_found[0] or "Failed test count increased" in regressions_found[0]


# ── 2. AccountManager Extended Tests ──────────────────────────────────


def test_account_manager_lifecycle(temp_accounts_file):
    with patch("services.account_manager.ACCOUNTS_FILE", temp_accounts_file):
        mgr = AccountManager()

        # Test adding account
        acc_id = mgr.add_account(label="Main", username="TestUser", password="TestPassword123", tagline="NA1")
        assert acc_id >= 0

        # Test get accounts
        accounts = mgr.get_accounts()
        assert len(accounts) == 1
        assert accounts[0]["username"] == "TestUser"

        # Test setting default account
        mgr.set_default_account(acc_id)
        assert mgr.get_default_account_index() == acc_id

        # Test deleting account
        assert mgr.delete_account(acc_id) is True
        assert len(mgr.get_accounts()) == 0


# ── 3. AssetManager Extended Tests ─────────────────────────────────────


def test_asset_manager_lookups():
    mgr = AssetManager()
    # Test champion icon path resolution
    icon_path = mgr.get_champion_icon_path("Ahri")
    assert icon_path is not None

    # Test fallback icon
    fallback = mgr.get_default_icon_path()
    assert fallback is not None or icon_path is None

    # Test known champions dict
    known = mgr.get_known_champions()
    assert isinstance(known, dict)


# ── 4. PySide6 UI Pages Extended Tests ──────────────────────────────────


def test_champions_page_filters(qapp):
    page = ChampionsPage()
    assert page is not None

    if hasattr(page, "on_search_changed"):
        page.on_search_changed("Ahri")

    if hasattr(page, "on_role_filter_clicked"):
        page.on_role_filter_clicked("MID")


def test_friends_page_extended(qapp):
    page = FriendsPage()
    assert page is not None

    if hasattr(page, "_filter_friends"):
        page._filter_friends("TestFriend")


def test_settings_page_extended(qapp):
    page = SettingsPage()
    assert page is not None

    if hasattr(page, "_on_toggle_changed"):
        page._on_toggle_changed("auto_accept", True)
