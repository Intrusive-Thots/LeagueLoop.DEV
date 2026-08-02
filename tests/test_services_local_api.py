import json
import io
import pytest
from unittest.mock import MagicMock, patch
from services.local_api import LeagueLoopAPIHandler, get_local_ip, ensure_firewall_rule, start_api_server

class MockServer:
    def __init__(self, app_instance=None):
        self.app_instance = app_instance
        self._summoner_cache = None
        self._summoner_cache_time = 0

class DummyAPIHandler(LeagueLoopAPIHandler):
    def __init__(self, request_data=b"", path="/health", method="GET", headers=None, app_instance=None):
        self.rfile = io.BytesIO(request_data)
        self.wfile = io.BytesIO()
        self.path = path
        self.command = method
        self.headers = headers or {"Content-Length": str(len(request_data))}
        self.server = MockServer(app_instance)
        self.response_code = None
        self.response_headers = {}

    def send_response(self, code, message=None):
        self.response_code = code

    def send_header(self, keyword, value):
        self.response_headers[keyword] = value

    def end_headers(self):
        pass

class TestLocalAPI:
    def test_get_health(self):
        handler = DummyAPIHandler(path="/health", method="GET")
        handler.do_GET()
        assert handler.response_code == 200
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        assert data == {"status": "ok"}

    def test_get_healthz(self):
        mock_app = MagicMock()
        mock_app.automation.running = True
        mock_app.automation.last_phase = "Lobby"
        mock_app.automation.lcu.is_connected = True
        handler = DummyAPIHandler(path="/healthz", method="GET", app_instance=mock_app)
        handler.do_GET()
        assert handler.response_code == 200
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        assert data["status"] == "healthy"
        assert data["automation_running"] is True
        assert data["lcu_connected"] is True
        assert data["phase"] == "Lobby"
        assert "uptime_seconds" in data
        assert "timestamp" in data

    def test_get_telemetry(self):
        handler = DummyAPIHandler(path="/telemetry", method="GET")
        handler.do_GET()
        assert handler.response_code == 200
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        assert data["status"] == "ok"
        assert data["websocket"] is None

    def test_get_telemetry_with_lcu(self):
        mock_app = MagicMock()
        mock_app.automation.lcu.get_ws_telemetry.return_value = {"total_events": 10, "avg_latency_ms": 1.2}
        mock_app.automation.lcu.get_request_diagnostics.return_value = {"total_requests": 5, "rate_limit_throttles": 0}
        handler = DummyAPIHandler(path="/telemetry", method="GET", app_instance=mock_app)
        handler.do_GET()
        assert handler.response_code == 200
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        assert data["status"] == "ok"
        assert data["websocket"]["total_events"] == 10
        assert data["request_diagnostics"]["total_requests"] == 5

    def test_get_queue_modes(self):
        handler = DummyAPIHandler(path="/queue-modes", method="GET")
        handler.do_GET()
        assert handler.response_code == 200
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        assert "modes" in data
        assert data["modes"]["ARAM"] == 450

    def test_get_404(self):
        handler = DummyAPIHandler(path="/non-existent", method="GET")
        handler.do_GET()
        assert handler.response_code == 404

    def test_get_config(self):
        mock_app = MagicMock()
        mock_app.config.cfg = {"auto_accept": True, "accept_delay": 2}
        handler = DummyAPIHandler(path="/config", method="GET", app_instance=mock_app)
        handler.do_GET()
        assert handler.response_code == 200
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        assert data.get("auto_accept") is True

    def test_get_aram_list(self):
        mock_app = MagicMock()
        mock_app.config.cfg = {"priority_picker": {"list": ["Jinx", "Ezreal"]}}
        handler = DummyAPIHandler(path="/aram-list", method="GET", app_instance=mock_app)
        handler.do_GET()
        assert handler.response_code == 200
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        assert data["list"] == ["Jinx", "Ezreal"]

    def test_post_action_invalid_json(self):
        handler = DummyAPIHandler(request_data=b"invalid json", path="/action", method="POST")
        handler.do_POST()
        assert handler.response_code == 400
        data = json.loads(handler.wfile.getvalue().decode('utf-8'))
        assert data["status"] == "error"

    def test_post_action_unknown(self):
        body = json.dumps({"action": "unknown_action"}).encode('utf-8')
        handler = DummyAPIHandler(request_data=body, path="/action", method="POST")
        handler.do_POST()
        assert handler.response_code == 400

    def test_post_action_valid(self):
        mock_app = MagicMock()
        body = json.dumps({"action": "toggle_automation"}).encode('utf-8')
        handler = DummyAPIHandler(request_data=body, path="/action", method="POST", app_instance=mock_app)
        handler.do_POST()
        assert handler.response_code == 200
        mock_app.after.assert_called_once()

    def test_post_config_key_forbidden(self):
        body = json.dumps({"key": "secret_key", "value": "xyz"}).encode('utf-8')
        handler = DummyAPIHandler(request_data=body, path="/config", method="POST")
        handler.do_POST()
        assert handler.response_code == 403

    def test_post_config_key_allowed(self):
        mock_app = MagicMock()
        mock_app.config.cfg = {}
        body = json.dumps({"key": "auto_accept", "value": True}).encode('utf-8')
        handler = DummyAPIHandler(request_data=body, path="/config", method="POST", app_instance=mock_app)
        handler.do_POST()
        assert handler.response_code == 200
        assert mock_app.config.cfg.get("auto_accept") is True

    def test_get_local_ip(self):
        ip = get_local_ip()
        assert isinstance(ip, str)
        assert len(ip) > 0

    @patch("subprocess.run")
    def test_ensure_firewall_rule(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="LeagueLoop Remote")
        ensure_firewall_rule(8337)
        mock_run.assert_called_once()

    @patch("services.local_api.ThreadingHTTPServer")
    @patch("services.local_api.threading.Thread")
    @patch("services.local_api.ensure_firewall_rule")
    def test_start_api_server(self, mock_fw, mock_thread, mock_server):
        mock_app = MagicMock()
        ip, port = start_api_server(mock_app, 8337)
        assert port == 8337
        assert ip is not None

    def test_send_json_buffer_serialization(self):
        handler = DummyAPIHandler(path="/health", method="GET")
        handler._send_json(LeagueLoopAPIHandler._HEALTH_OK_BYTES)
        assert handler.wfile.getvalue() == b'{"status":"ok"}'

        handler2 = DummyAPIHandler(path="/custom", method="GET")
        handler2._send_json({"foo": "bar", "num": 123})
        assert handler2.wfile.getvalue() == b'{"foo":"bar","num":123}'

