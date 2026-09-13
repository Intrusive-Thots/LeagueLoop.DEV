import pytest
from unittest.mock import MagicMock
from src.services.queue_manager import QueueManager, BASELINE_NAME_TO_ID, BASELINE_QUEUE_MAP

@pytest.fixture
def queue_manager():
    # We clear the singleton instance if any for test isolation
    QueueManager._instance = None
    return QueueManager.get_instance()

def test_resolve_queue_id_default(queue_manager):
    # Empty or None should resolve to 450 (ARAM)
    assert queue_manager.resolve_queue_id(None) == 450
    assert queue_manager.resolve_queue_id("") == 450

def test_resolve_queue_id_exact_match(queue_manager):
    assert queue_manager.resolve_queue_id("Ranked Solo/Duo") == 420
    assert queue_manager.resolve_queue_id("ARAM") == 450

def test_resolve_queue_id_case_insensitive(queue_manager):
    assert queue_manager.resolve_queue_id("aram") == 450
    assert queue_manager.resolve_queue_id("ranked solo/duo") == 420

def test_resolve_queue_id_fuzzy_match(queue_manager):
    assert queue_manager.resolve_queue_id("solo/duo") == 420

def test_resolve_queue_id_fallback(queue_manager):
    assert queue_manager.resolve_queue_id("Nonexistent Mode") == 450

def test_resolve_mode_name_exact(queue_manager):
    assert queue_manager.resolve_mode_name(450) == "ARAM"
    assert queue_manager.resolve_mode_name(420) == "Ranked Solo/Duo"

def test_resolve_mode_name_invalid_type(queue_manager):
    assert queue_manager.resolve_mode_name("invalid") == "ARAM"
    assert queue_manager.resolve_mode_name(None) == "ARAM"

def test_resolve_mode_name_fallback(queue_manager):
    assert queue_manager.resolve_mode_name(9999) == "Queue 9999"

def test_update_available_lobby_types_no_lcu(queue_manager):
    initial_groups = queue_manager.get_categorized_groups()
    assert queue_manager.update_available_lobby_types(None) == initial_groups

    lcu = MagicMock()
    lcu.is_connected = False
    assert queue_manager.update_available_lobby_types(lcu) == initial_groups

def test_update_available_lobby_types_failed_request(queue_manager):
    lcu = MagicMock()
    lcu.is_connected = True
    lcu.request.return_value = MagicMock(status_code=500)
    initial_groups = queue_manager.get_categorized_groups()
    assert queue_manager.update_available_lobby_types(lcu) == initial_groups

def test_update_available_lobby_types_success(queue_manager):
    lcu = MagicMock()
    lcu.is_connected = True
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = [
        {"id": 420, "name": "Ranked Solo/Duo", "queueAvailability": "Available", "isCustom": False, "isRanked": True},
        {"id": 450, "name": "ARAM", "queueAvailability": "Available", "isCustom": False, "gameMode": "ARAM"}
    ]
    lcu.request.return_value = mock_res

    updated_groups = queue_manager.update_available_lobby_types(lcu)

    group_names = [g[0] for g in updated_groups]
    assert "Ranked" in group_names
    assert "ARAM" in group_names

    assert queue_manager.resolve_queue_id("ARAM") == 450
    assert queue_manager.resolve_mode_name(450) == "ARAM"

def test_start_matchmaking_success(queue_manager):
    lcu = MagicMock()
    lcu.is_connected = True
    lcu.request.return_value = MagicMock(status_code=204)
    assert queue_manager.start_matchmaking(lcu) is True

def test_start_matchmaking_failure(queue_manager):
    lcu = MagicMock()
    lcu.is_connected = True
    lcu.request.return_value = MagicMock(status_code=500)
    assert queue_manager.start_matchmaking(lcu) is False

    lcu.request.side_effect = Exception("error")
    assert queue_manager.start_matchmaking(lcu) is False

def test_stop_matchmaking_success(queue_manager):
    lcu = MagicMock()
    lcu.is_connected = True
    lcu.request.return_value = MagicMock(status_code=204)
    assert queue_manager.stop_matchmaking(lcu) is True

def test_stop_matchmaking_failure(queue_manager):
    lcu = MagicMock()
    lcu.is_connected = True
    lcu.request.return_value = MagicMock(status_code=500)
    assert queue_manager.stop_matchmaking(lcu) is False

def test_create_lobby_success(queue_manager):
    lcu = MagicMock()
    lcu.is_connected = True
    lcu.request.return_value = MagicMock(status_code=200)
    assert queue_manager.create_lobby(lcu, 450) is True
    lcu.request.assert_called_with("POST", "/lol-lobby/v2/lobby", {"queueId": 450})

def test_create_lobby_failure(queue_manager):
    lcu = MagicMock()
    lcu.is_connected = True
    lcu.request.return_value = MagicMock(status_code=500)
    assert queue_manager.create_lobby(lcu, 450) is False
