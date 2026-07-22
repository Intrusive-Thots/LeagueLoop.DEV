import json
from io import BytesIO
from unittest.mock import MagicMock
import pytest

from services.api.routes.status import handle_status, handle_health
from services.api.routes.accounts import handle_get_accounts, handle_login, handle_logout
from services.api.routes.config import handle_get_config, handle_post_config

def create_mock_handler(body_dict=None, app_instance=None):
    handler = MagicMock()
    handler.app_instance = app_instance or MagicMock()
    handler.server = MagicMock()
    handler.send_json = MagicMock()

    if body_dict is not None:
        raw_body = json.dumps(body_dict).encode('utf-8')
        handler.headers = {'Content-Length': str(len(raw_body))}
        handler.rfile = BytesIO(raw_body)
    else:
        handler.headers = {'Content-Length': '0'}
        handler.rfile = BytesIO(b'')

    return handler

def test_handle_health():
    handler = create_mock_handler()
    handle_health(handler)
    handler.send_json.assert_called_once_with({"status": "ok"})

def test_handle_get_accounts():
    app = MagicMock()
    app.account_manager.get_accounts.return_value = [
        {"label": "Main", "username": "player1", "tagline": "NA1", "region": "NA1", "wallet": {"be": 5000, "rp": 100}}
    ]
    app.account_manager.get_active_index.return_value = 0

    handler = create_mock_handler(app_instance=app)
    handle_get_accounts(handler)

    handler.send_json.assert_called_once_with({
        "accounts": [
            {"label": "Main", "username": "player1", "tagline": "NA1", "region": "NA1", "wallet": {"be": 5000, "rp": 100}}
        ],
        "active_index": 0
    })

def test_handle_login_valid():
    app = MagicMock()
    handler = create_mock_handler(body_dict={"index": 1}, app_instance=app)
    handle_login(handler)

    app.account_manager.login_account.assert_called_once_with(1, log_func=None, completion_func=None)
    handler.send_json.assert_called_once_with({"status": "success", "message": "Login initiated"})

def test_handle_login_invalid_json():
    handler = MagicMock()
    handler.headers = {'Content-Length': '5'}
    handler.rfile = BytesIO(b'badjson')
    handler.send_json = MagicMock()

    handle_login(handler)
    handler.send_json.assert_called_once_with({'status': 'error', 'message': 'Invalid JSON or index'}, 400)

def test_handle_logout():
    app = MagicMock()
    handler = create_mock_handler(app_instance=app)
    handle_logout(handler)

    app.account_manager.sign_out.assert_called_once_with(log_func=None, completion_func=None)
    handler.send_json.assert_called_once_with({"status": "success", "message": "Logout initiated"})

def test_handle_get_config():
    app = MagicMock()
    app.config.cfg = {
        "auto_accept": True,
        "auto_pick": "Ahri",
        "auto_ban": "Zed",
        "auto_lock_in": True,
        "aram_mode": "ARAM"
    }

    handler = create_mock_handler(app_instance=app)
    handle_get_config(handler)

    response_data = handler.send_json.call_args[0][0]
    assert response_data["auto_accept"] is True
    assert response_data["auto_pick"] == "Ahri"
    assert response_data["auto_ban"] == "Zed"
    assert response_data["aram_mode"] == "ARAM"

def test_handle_post_config_valid():
    app = MagicMock()
    app.config.cfg = {"auto_accept": False}

    handler = create_mock_handler(body_dict={"key": "auto_accept", "value": True}, app_instance=app)
    handle_post_config(handler)

    assert app.config.cfg["auto_accept"] is True
    app.config.save.assert_called_once()
    handler.send_json.assert_called_once_with({'status': 'success', 'key': 'auto_accept', 'value': True})

def test_handle_post_config_unwritable_key():
    app = MagicMock()
    handler = create_mock_handler(body_dict={"key": "secret_key", "value": "val"}, app_instance=app)
    handle_post_config(handler)

    handler.send_json.assert_called_once_with({'status': 'error', 'message': 'Key not writable: secret_key'}, 403)

def test_handle_get_champ_select():
    from services.api.routes.champ_select import handle_get_champ_select
    app = MagicMock()
    app.automation.lcu.is_connected = True
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        'localPlayerCellId': 1,
        'myTeam': [{'cellId': 1, 'championId': 103, 'assignedPosition': 'MIDDLE'}],
        'theirTeam': [{'cellId': 6, 'championId': 238, 'assignedPosition': 'MIDDLE'}],
        'actions': [[{'id': 10, 'actorCellId': 1, 'type': 'pick', 'isInProgress': True, 'completed': False}]],
        'bannedChampions': [{'championId': 157}],
        'benchChampions': [{'championId': 222}]
    }
    app.automation.lcu.request.return_value = mock_resp
    app.automation.assets.get_champ_name.side_effect = lambda cid: "Ahri" if cid == 103 else ("Zed" if cid == 238 else ("Yasuo" if cid == 157 else "Jinx"))

    handler = create_mock_handler(app_instance=app)
    handle_get_champ_select(handler)

    handler.send_json.assert_called_once()
    res = handler.send_json.call_args[0][0]
    assert res['active'] is True
    assert res['myTeam'][0]['championName'] == 'Ahri'

def test_handle_action_find_match():
    from services.api.routes.matchmaking import handle_action
    app = MagicMock()
    handler = create_mock_handler(body_dict={'action': 'find_match'}, app_instance=app)
    handle_action(handler)

    assert handler.send_json.called
    res = handler.send_json.call_args[0][0]
    assert res['status'] == 'success'

def test_handle_action_invalid():
    from services.api.routes.matchmaking import handle_action
    handler = create_mock_handler(body_dict={'action': 'invalid_action'}, app_instance=MagicMock())
    handle_action(handler)

    assert handler.send_json.called
    assert handler.send_json.call_args[0][1] == 400

def test_handle_status_route():
    from services.api.routes.status import handle_status
    app = MagicMock()
    handler = create_mock_handler(app_instance=app)
    handle_status(handler)

    res = handler.send_json.call_args[0][0]
    assert 'phase' in res
    assert 'automation_enabled' in res


