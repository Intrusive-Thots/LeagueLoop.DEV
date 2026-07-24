from unittest.mock import MagicMock, patch
import pytest
from services.automation.dodge_requeue import handle_dodge_requeue, handle_auto_dodge
from services.automation.friend_lobby import check_friend_lobby

def test_handle_dodge_requeue_triggers_search():
    engine = MagicMock()
    engine.last_phase = "ChampSelect"
    engine._cached_search_state = None
    engine._last_search_state_time = 0.0

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"searchState": "Invalid"}
    engine.lcu.request.return_value = mock_resp

    handle_dodge_requeue(engine, "Lobby")

    engine.lcu.request.assert_any_call("POST", "/lol-lobby/v2/lobby/matchmaking/search")
    engine._log.assert_called_with("Dodge detected. Restarting Matchmaking...")

def test_handle_dodge_requeue_cached_searching():
    engine = MagicMock()
    engine.last_phase = "ChampSelect"
    engine._cached_search_state = {"searchState": "Searching"}
    engine._last_search_state_time = 9999999999.0

    handle_dodge_requeue(engine, "Lobby")

    # Should not trigger new search POST request if state is Searching
    assert not any(call[0] == ("POST", "/lol-lobby/v2/lobby/matchmaking/search") for call in engine.lcu.request.call_args_list)

def test_handle_auto_dodge_matches_blacklist():
    engine = MagicMock()
    engine._blacklist = {"trollplayer", "badplayer#na1"}

    session = {
        "localPlayerCellId": 1,
        "myTeam": [
            {"cellId": 1, "summonerId": 100},
            {"cellId": 2, "summonerId": 200}
        ]
    }

    mock_summoner_resp = MagicMock()
    mock_summoner_resp.status_code = 200
    mock_summoner_resp.json.return_value = {"gameName": "TrollPlayer", "tagLine": "NA1"}
    engine.lcu.request.return_value = mock_summoner_resp

    with patch("subprocess.run") as mock_run:
        handle_auto_dodge(engine, session)
        mock_run.assert_called_once()
        engine._log.assert_called_with("BLACKLIST MATCH: trollplayer#na1. Dodging immediately.")

def test_check_friend_lobby_auto_joins():
    engine = MagicMock()
    engine.config.get.side_effect = lambda key, default=None: {
        "auto_join_enabled": True,
        "auto_join_list": [{"enabled": True, "name": "BestFriend#1234"}]
    }.get(key, default)

    mock_friends = [
        {
            "gameName": "BestFriend",
            "gameTag": "1234",
            "lol": {
                "ptyType": "open",
                "pty": '{"partyId": "party-777"}'
            }
        }
    ]

    mock_lobby_resp = MagicMock()
    mock_lobby_resp.status_code = 200
    mock_lobby_resp.json.return_value = {"partyId": "party-999"}

    mock_join_resp = MagicMock()
    mock_join_resp.status_code = 200

    def mock_request(method, path, **kwargs):
        if "/lol-chat/v1/friends" in path:
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = mock_friends
            return r
        elif "/lol-lobby/v2/lobby" in path and method == "GET":
            return mock_lobby_resp
        elif "/lol-lobby/v2/party/party-777/join" in path:
            return mock_join_resp
        return MagicMock(status_code=404)

    engine.lcu.request.side_effect = mock_request

    with patch("core.state.State.friends", new=mock_friends):
        check_friend_lobby(engine, "Lobby")
        engine._log.assert_called_with("Auto-joined BestFriend's Party!")
