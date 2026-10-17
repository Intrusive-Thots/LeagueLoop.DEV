"""
test_queue_manager.py — Unit and integration tests for QueueManager service.
"""

from unittest.mock import MagicMock, patch
import pytest

from services.queue_manager import (
    QueueManager,
    BASELINE_QUEUE_MAP,
    BASELINE_NAME_TO_ID,
    BASELINE_GROUPS,
    resolve_queue_id,
    resolve_mode_name,
    update_available_lobby_types,
    get_categorized_lobby_types,
    start_matchmaking,
    stop_matchmaking,
    create_lobby,
)


def test_baseline_mappings_exist():
    """Verify default static baseline maps are populated with expected standard queues."""
    assert 420 in BASELINE_QUEUE_MAP
    assert BASELINE_QUEUE_MAP[420] == "Ranked Solo/Duo"
    assert 450 in BASELINE_QUEUE_MAP
    assert BASELINE_QUEUE_MAP[450] == "ARAM"
    assert BASELINE_NAME_TO_ID.get("ARAM") == 450
    assert BASELINE_NAME_TO_ID.get("Ranked Solo/Duo") == 420
    assert len(BASELINE_GROUPS) > 0


def test_resolve_queue_id_static():
    """Verify static resolution of standard modes."""
    mgr = QueueManager()
    assert mgr.resolve_queue_id("Ranked Solo/Duo") == 420
    assert mgr.resolve_queue_id("ARAM") == 450
    assert mgr.resolve_queue_id("Draft Pick") == 400
    assert mgr.resolve_queue_id("Arena") == 1700
    assert mgr.resolve_queue_id("Quickplay") == 490


def test_resolve_queue_id_fallback():
    """Verify fallback defaults to 450 (ARAM) for unknown or empty input."""
    mgr = QueueManager()
    assert mgr.resolve_queue_id("") == 450
    assert mgr.resolve_queue_id(None) == 450
    assert mgr.resolve_queue_id("NonExistentCustomGameMode123") == 450


def test_resolve_queue_id_case_insensitive_and_fuzzy():
    """Verify case insensitivity and partial substring matching."""
    mgr = QueueManager()
    assert mgr.resolve_queue_id("ranked solo/duo") == 420
    assert mgr.resolve_queue_id("aram") == 450
    assert mgr.resolve_queue_id("arena 3v6") == 1710


def test_resolve_mode_name():
    """Verify resolving numeric queue ID to display string."""
    mgr = QueueManager()
    assert mgr.resolve_mode_name(420) == "Ranked Solo/Duo"
    assert mgr.resolve_mode_name(450) == "ARAM"
    assert mgr.resolve_mode_name(99999) == "Queue 99999"
    assert mgr.resolve_mode_name("invalid") == "ARAM"


def test_update_available_lobby_types_dynamic():
    """Verify dynamic discovery of queues from LCU API."""
    mgr = QueueManager()
    mock_lcu = MagicMock()
    mock_lcu.is_connected = True

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "id": 420,
            "name": "Ranked Solo/Duo",
            "queueAvailability": "Available",
            "isCustom": False,
            "gameMode": "CLASSIC",
            "category": "pvp",
            "isRanked": True,
        },
        {
            "id": 450,
            "name": "ARAM",
            "queueAvailability": "Available",
            "isCustom": False,
            "gameMode": "ARAM",
            "category": "pvp",
            "isRanked": False,
        },
        {
            "id": 2400,
            "name": "ARAM: Mayhem Special",
            "queueAvailability": "Available",
            "isCustom": False,
            "gameMode": "ARAM",
            "category": "pvp",
            "isRanked": False,
        },
    ]
    mock_lcu.request.return_value = mock_resp

    groups = mgr.update_available_lobby_types(mock_lcu)
    assert len(groups) > 0
    assert mgr._last_updated > 0.0
    assert mgr.resolve_queue_id("ARAM: Mayhem Special") == 2400


def test_resolve_queue_id_triggers_dynamic_update_when_needed():
    """Verify resolve_queue_id calls update_available_lobby_types if connected and never updated."""
    mgr = QueueManager()
    assert mgr._last_updated == 0.0
    mock_lcu = MagicMock()
    mock_lcu.is_connected = True
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "id": 8888,
            "name": "Custom Dynamic Mode",
            "queueAvailability": "Available",
            "isCustom": False,
            "gameMode": "CLASSIC",
            "category": "pvp",
        }
    ]
    mock_lcu.request.return_value = mock_resp

    qid = mgr.resolve_queue_id("Custom Dynamic Mode", mock_lcu)
    assert qid == 8888
    assert mgr._last_updated > 0.0


def test_matchmaking_helpers():
    """Verify start_matchmaking, stop_matchmaking, and create_lobby."""
    mgr = QueueManager()
    mock_lcu = MagicMock()
    mock_lcu.is_connected = True
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_lcu.request.return_value = mock_resp

    assert mgr.start_matchmaking(mock_lcu) is True
    mock_lcu.request.assert_called_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

    assert mgr.stop_matchmaking(mock_lcu) is True
    mock_lcu.request.assert_called_with("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")

    assert mgr.create_lobby(mock_lcu, 420) is True
    mock_lcu.request.assert_called_with("POST", "/lol-lobby/v2/lobby", {"queueId": 420})


def test_disconnected_lcu_handling():
    """Verify graceful handling when LCU is not connected."""
    mgr = QueueManager()
    mock_lcu = MagicMock()
    mock_lcu.is_connected = False

    assert mgr.start_matchmaking(mock_lcu) is False
    assert mgr.stop_matchmaking(mock_lcu) is False
    assert mgr.create_lobby(mock_lcu, 420) is False
    assert mgr.update_available_lobby_types(mock_lcu) == mgr.get_categorized_groups()


def test_module_level_convenience_functions():
    """Verify module-level wrappers call singleton instance."""
    assert resolve_queue_id("ARAM") == 450
    assert resolve_mode_name(420) == "Ranked Solo/Duo"
    assert isinstance(get_categorized_lobby_types(), list)
