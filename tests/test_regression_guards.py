"""Regression guards for architecture constraints and recurring bug classes."""
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"


def _python_files():
    for root, _, files in os.walk(SRC):
        for f in files:
            if f.endswith(".py"):
                yield Path(root) / f


def test_no_live_client_data_api():
    """Never interact with Live Client Data API (port 2999)."""
    forbidden = ["2999", "liveclientdata", "Live Client Data"]
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in forbidden:
            assert token not in text, f"{path} contains forbidden token: {token}"


def test_no_direct_qt_from_threads_pattern():
    """Heuristic: avoid obvious background-thread GUI mutation patterns."""
    # Soft check — only flag known dangerous patterns if present without marshal
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "threading.Thread" in text and "QPixmap" in text and "QTimer.singleShot" not in text:
            pytest.fail(f"{path} may mutate Qt from background thread without QTimer.singleShot")


def test_client_detector_requires_credentials():
    """LCU-001: league_found only after port + token present."""
    detector = SRC / "utils" / "client_detector.py"
    assert detector.exists()
    text = detector.read_text(encoding="utf-8")
    # Ensure lockfile / token handling exists
    assert "remoting-auth-token" in text or "token" in text.lower()
    assert "app-port" in text or "port" in text.lower()


def test_architecture_constraints_doc_present():
    """Ensure hard constraints doc remains in repo."""
    doc = REPO_ROOT / ".agents" / "ARCHITECTURE_CONSTRAINTS.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "NEVER interacts with the running game process" in text


def test_asset_manager_never_calls_isdigit_on_raw_key():
    """ASSET-001: never call .isdigit() on a key that may be an LCU int."""
    text = (SRC / "services" / "asset_manager.py").read_text(encoding="utf-8")
    assert "_coerce_numeric_id" in text
    assert "_resolve_champion_key" in text
    for i, line in enumerate(text.splitlines(), 1):
        if ".isdigit()" not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("*") or '"""' in stripped:
            continue
        if "``" in stripped:  # docstring discussing the old bug
            continue
        if "isinstance(key, str)" in line or "isinstance(ver, str)" in line:
            continue
        if "all(p.isdigit()" in line:
            continue
        pytest.fail(f"unguarded .isdigit() at asset_manager.py:{i}: {stripped}")


def test_factory_unfocus_uses_safe_colors():
    """UI-001: CTk configure must not receive None colors."""
    factory = (SRC / "ui" / "components" / "factory.py").read_text(encoding="utf-8")
    colors = (SRC / "ui" / "components" / "color_utils.py").read_text(encoding="utf-8")
    assert "ctk_safe_color" in factory
    assert "def _on_unfocus" in factory
    assert "def ctk_safe_color" in colors


def test_color_utils_parses_without_raw_slice():
    """COLOR-001: do not slice hex_color[1:3] without validation."""
    text = (SRC / "ui" / "components" / "color_utils.py").read_text(encoding="utf-8")
    assert "def parse_hex_rgb" in text
    assert "int(hex_color[1:3], 16)" not in text
    assert "int(hex_color[3:5], 16)" not in text


def test_main_app_init_order_regression():
    """Ensure self.running is defined before _process_ui_queue is called in LeagueLoopApp."""
    main_py = SRC / "core" / "main.py"
    assert main_py.exists()
    text = main_py.read_text(encoding="utf-8")
    running_pos = text.find("self.running = True")
    ui_queue_pos = text.find("self._process_ui_queue()")
    assert running_pos != -1, "self.running = True missing from LeagueLoopApp"
    assert ui_queue_pos != -1, "self._process_ui_queue() missing from LeagueLoopApp"
    assert running_pos < ui_queue_pos, "self.running must be initialized before calling _process_ui_queue"


def test_client_window_tracker_invariants():
    """DOCK-001: ClientWindowTracker recognizes both League titles and guards iconic windows."""
    tracker_py = SRC / "services" / "client_window_tracker.py"
    assert tracker_py.exists()
    text = tracker_py.read_text(encoding="utf-8")
    assert '"league of legends"' in text
    assert '"league of legends (tm) client"' in text
    assert "IsIconic" in text
    assert "-30000" in text  # Guard against minimized off-screen coordinates
    assert "MIN_CLIENT_WIDTH" in text
    assert "MIN_CLIENT_HEIGHT" in text


def test_docking_loop_invariants():
    """DOCK-002: Companion physical repositioning (0x0014) and multi-monitor work area handling."""
    main_py = SRC / "core" / "main.py"
    assert main_py.exists()
    text = main_py.read_text(encoding="utf-8")
    # Verify physical repositioning for borderless windows with SWP_NOZORDER | SWP_NOACTIVATE (0x0014)
    assert "SetWindowPos" in text
    assert "0x0014" in text
    # Verify multi-monitor work area querying via MonitorFromRect and rcWork
    assert "MonitorFromRect" in text
    assert "rcWork" in text


def test_version_and_installer_alignment_invariants():
    """VER-001: Version bumping protocol guarantees strict alignment between version.py and installer.iss."""
    version_py = SRC / "core" / "version.py"
    installer_iss = REPO_ROOT / "installer.iss"
    assert version_py.exists(), "src/core/version.py must exist"
    assert installer_iss.exists(), "installer.iss must exist"

    from tools.bump_version import check_version_alignment, read_version, read_installer_versions, to_version_info
    ok, msg = check_version_alignment(str(version_py), str(installer_iss))
    assert ok, f"Version misalignment detected: {msg}"

    app_ver, info_ver = read_installer_versions(str(installer_iss))
    v = read_version(str(version_py))
    assert app_ver == v, f"AppVersion '{app_ver}' does not match version.py '{v}'"
    assert info_ver == to_version_info(v), f"VersionInfoVersion '{info_ver}' does not match '{to_version_info(v)}'"


def test_stats_scraper_daemon_executor_invariants():
    """THREAD-001: StatsScraper background thread pool workers must be daemon threads to prevent pytest hangs."""
    from services.stats_scraper import StatsScraper
    scraper = StatsScraper(mode="ARAM", fetch_live=False)
    try:
        assert hasattr(scraper, "shutdown"), "StatsScraper must expose a shutdown() method"
        scraper._executor.submit(lambda: None)
        for t in scraper._executor._threads:
            assert t.daemon is True, f"StatsScraper worker thread {t.name} must be daemon=True"
    finally:
        scraper.shutdown(wait=True)


def test_lcu_telemetry_expected_error_filtering_invariants():
    """LCU-002: LCUClient must suppress benign 405, 404, and 400 status codes on expected polling/probing endpoints."""
    from services.api_handler import LCUClient

    assert hasattr(LCUClient, "EXPECTED_405_ENDPOINTS"), "LCUClient must define EXPECTED_405_ENDPOINTS"
    assert hasattr(LCUClient, "EXPECTED_404_ENDPOINTS"), "LCUClient must define EXPECTED_404_ENDPOINTS"
    assert hasattr(LCUClient, "EXPECTED_400_ENDPOINTS"), "LCUClient must define EXPECTED_400_ENDPOINTS"

    # Verify key endpoints
    assert "/lol-loot/v1/ready" in LCUClient.EXPECTED_405_ENDPOINTS
    assert "/lol-champ-select/v1/session/actions" in LCUClient.EXPECTED_405_ENDPOINTS
    assert "/lol-gameflow/v1/gameflow-phase" in LCUClient.EXPECTED_405_ENDPOINTS

    # Verify _is_expected_absence filtering logic
    assert LCUClient._is_expected_absence(405, "/lol-loot/v1/ready") is True
    assert LCUClient._is_expected_absence(405, "/lol-champ-select/v1/session/actions/4") is True
    assert LCUClient._is_expected_absence(405, "/lol-gameflow/v1/gameflow-phase?foo=bar") is True
    assert LCUClient._is_expected_absence(404, "/lol-battle-pass/v1/rewards/claim") is True
    assert LCUClient._is_expected_absence(400, "/lol-ranked/v1/rewards/claim") is True

    # Verify unexpected endpoints are NOT suppressed
    assert LCUClient._is_expected_absence(405, "/lol-summoner/v1/current-summoner") is False
    assert LCUClient._is_expected_absence(404, "/lol-summoner/v1/current-summoner") is False
    assert LCUClient._is_expected_absence(500, "/lol-loot/v1/ready") is False


def test_lcu_telemetry_transient_retry_filtering_invariants():
    """LCU-003: Transient 5xx retries must be recorded in telemetry without triggering false positive terminal error warnings."""
    from services.api_handler import LCUClient

    client = LCUClient()
    assert hasattr(client, "_record_http_status_code")
    assert hasattr(client, "_http_transient_retry_count")

    initial_errors = len(client._recent_http_errors)
    # Record transient retry
    client._record_http_status_code(500, "POST", "/lol-lobby/v2/lobby", is_transient_retry=True)
    assert len(client._recent_http_errors) == initial_errors
    assert client._http_transient_retry_count == 1
    assert client._http_5xx_count == 1

    # Diagnostics and telemetry must expose http_transient_retry_count
    req_diag = client.get_request_diagnostics()
    assert "http_transient_retry_count" in req_diag
    assert req_diag["http_transient_retry_count"] == 1

    status_tel = client.get_http_status_telemetry()
    assert "http_transient_retry_count" in status_tel
    assert status_tel["http_transient_retry_count"] == 1





def test_lcu_http_5xx_sliding_window_threshold_invariants():
    """LCU-004: 5xx anomaly alert must not trip on isolated 1-4 failures; requires configured threshold."""
    from services.api_handler import LCUClient

    client = LCUClient()
    thresh = client._http_anomaly_5xx_count_threshold
    assert thresh >= 3

    # Ensure count < threshold does not trip anomaly active
    for _ in range(thresh - 1):
        client._record_http_status_code(503, "GET", "/lol-chat/v1/friends")
        tel = client.get_http_status_anomaly_telemetry()
        assert tel["http_status_anomaly_active"] is False
        assert tel["http_status_anomaly_count"] == 0

    # Crossing threshold trips anomaly active
    client._record_http_status_code(503, "GET", "/lol-chat/v1/friends")
    tel = client.get_http_status_anomaly_telemetry()
    assert tel["http_status_anomaly_active"] is True
    assert tel["http_status_anomaly_count"] == 1
    assert f"HTTP 5xx count {thresh} reached threshold" in tel["last_http_status_anomaly"]["reason"]


def test_lcu_http_transport_failure_sliding_window_threshold_invariants():
    """LCU-005: Transport failure (status 0) anomaly alert must not trip on isolated 1-2 failures; requires configured threshold."""
    from services.api_handler import LCUClient

    client = LCUClient()
    thresh = client._http_anomaly_transport_count_threshold
    assert thresh >= 3

    # 1. Verify telemetry exposes http_anomaly_transport_count_threshold
    tel = client.get_http_status_anomaly_telemetry()
    assert tel["http_anomaly_transport_count_threshold"] == thresh
    assert tel["http_status_anomaly_active"] is False

    # 2. Ensure transport failure count < threshold does not trip anomaly active
    for _ in range(thresh - 1):
        client._record_http_transport_failure("GET", "/lol-chat/v1/friends", "connection")
        tel = client.get_http_status_anomaly_telemetry()
        assert tel["http_status_anomaly_active"] is False
        assert tel["http_status_anomaly_count"] == 0

    # 3. Crossing threshold trips anomaly active
    client._record_http_transport_failure("GET", "/lol-chat/v1/friends", "connection")
    tel = client.get_http_status_anomaly_telemetry()
    assert tel["http_status_anomaly_active"] is True
    assert tel["http_status_anomaly_count"] == 1
    assert f"HTTP transport failure count {thresh} reached threshold" in tel["last_http_status_anomaly"]["reason"]
    assert "connection" in tel["last_http_status_anomaly"]["reason"]

    # 4. Success dilution or clearing window recovers anomaly state
    client._http_status_window.clear()
    with client._req_diag_lock:
        client._evaluate_http_status_anomaly(is_error=False, status_code=200, method="GET", endpoint="/lol-chat/v1/friends")
    tel_recovered = client.get_http_status_anomaly_telemetry()
    assert tel_recovered["http_status_anomaly_active"] is False


def test_riot_client_api_timeout_retry_invariants():
    """RCA-001: RiotClientAPI must retry transient timeouts and not raise unhandled errors."""
    from unittest.mock import MagicMock, patch
    import requests
    from services.account_manager import RiotClientAPI

    api = RiotClientAPI()
    api.is_connected = True
    api.port = "5555"
    api.base_url = "https://127.0.0.1:5555"

    # 1. Successful retry on ReadTimeout
    mock_ok = MagicMock()
    mock_ok.status_code = 200
    api.session = MagicMock()
    api.session.request.side_effect = [requests.exceptions.ReadTimeout("Timeout"), mock_ok]
    with patch("time.sleep"):
        res = api.request("GET", "/test", silent=True)
    assert res == mock_ok
    assert api.session.request.call_count == 2
    assert api.is_connected is True

    # 2. Graceful exhaustion on continuous timeouts
    api_exhaust = RiotClientAPI()
    api_exhaust.is_connected = True
    api_exhaust.port = "5555"
    api_exhaust.base_url = "https://127.0.0.1:5555"
    api_exhaust.session = MagicMock()
    api_exhaust.session.request.side_effect = requests.exceptions.ConnectTimeout("Connect timed out")
    with patch("time.sleep"):
        res = api_exhaust.request("GET", "/test", silent=False)
    assert res is None
    assert api_exhaust.session.request.call_count == 3
    assert api_exhaust.is_connected is False


def test_account_switcher_logging_hygiene_invariants():
    """ACC-001: AccountSwitcher._finish must use ASCII hyphens and treat SESSION_EXPIRED as warning."""
    from unittest.mock import MagicMock, patch
    from services.accounts.results import SwitchOutcome, SwitchPhase, SwitchResult
    from services.accounts.switcher import AccountSwitcher

    switcher = AccountSwitcher(
        session=MagicMock(),
        accounts_provider=lambda: [{"username": "test_user"}],
        vault=MagicMock(),
    )

    expired_result = SwitchResult(
        SwitchOutcome.SESSION_EXPIRED,
        SwitchPhase.VERIFYING,
        0,
        "test_user",
        "The Riot Client did not accept the saved session.",
    )

    with patch("utils.logger.Logger.warning") as mock_warn, patch("utils.logger.Logger.error") as mock_err:
        switcher._finish(expired_result)
        mock_warn.assert_called_once()
        mock_err.assert_not_called()
        args, _ = mock_warn.call_args
        msg = args[1]
        assert "switch failed for test_user: SESSION_EXPIRED - The Riot Client did not accept" in msg
        assert "â€”" not in msg
        assert "—" not in msg


def test_logger_no_em_dashes_in_log_statements():
    """LOG-002: Ensure no Logger.<level>, update_action_log, or _log calls in src/ contain literal em dashes."""
    import ast
    offenders = []
    log_names = {"Logger.info", "Logger.warning", "Logger.error", "Logger.debug", "Logger.critical", "self._log", "update_action_log", "_log"}
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        func_name = f"{node.func.value.id}.{node.func.attr}"
                    elif isinstance(node.func.value, ast.Attribute):
                        func_name = f"{node.func.attr}"
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id
                if func_name in log_names:
                    for arg in node.args:
                        for sub in ast.walk(arg):
                            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                                if "—" in sub.value:
                                    offenders.append(f"{path.name}:{node.lineno} [em-dash]: {sub.value.strip()}")
    assert not offenders, f"Logging calls with literal em dashes found:\n" + "\n".join(offenders)


def test_logger_ascii_hygiene_invariants():
    """LOG-003: Ensure all Logger.<level>, update_action_log, and _log string arguments in src/ are strict ASCII for CP1252 Windows terminal safety."""
    import ast
    offenders = []
    log_names = {"Logger.info", "Logger.warning", "Logger.error", "Logger.debug", "Logger.critical", "self._log", "update_action_log", "_log"}
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        func_name = f"{node.func.value.id}.{node.func.attr}"
                    elif isinstance(node.func.value, ast.Attribute):
                        func_name = f"{node.func.attr}"
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id
                if func_name in log_names:
                    for arg in node.args:
                        for sub in ast.walk(arg):
                            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                                non_ascii = [f"U+{ord(c):04X}" for c in sub.value if ord(c) > 127]
                                if non_ascii:
                                    offenders.append(f"{path.name}:{node.lineno} [{func_name}] {','.join(non_ascii)}: {ascii(sub.value.strip())}")
    assert not offenders, f"Logging calls with non-ASCII strings found:\n" + "\n".join(offenders)


def test_app_sidebar_queue_resolution_invariants():
    """QUEUE-001: Ensure AppSidebar._get_queue_id_for_mode delegates to QueueManager and does not maintain duplicate hardcoded dictionaries."""
    sidebar_file = SRC / "ui" / "app_sidebar.py"
    assert sidebar_file.exists()
    text = sidebar_file.read_text(encoding="utf-8")
    assert "from services.queue_manager import resolve_queue_id" in text
    assert "def _get_queue_id_for_mode" in text
    # Ensure no duplicate hardcoded mode dictionary in _get_queue_id_for_mode
    assert "mode_map = {" not in text


def test_stats_scraper_queue_resolution_invariants():
    """QUEUE-002: Ensure StatsScraper.set_mode_by_queue_id delegates to QueueManager and does not maintain duplicate hardcoded dictionaries."""
    scraper_file = SRC / "services" / "stats_scraper.py"
    assert scraper_file.exists()
    text = scraper_file.read_text(encoding="utf-8")
    assert "from services.queue_manager import resolve_mode_name" in text
    assert "def set_mode_by_queue_id" in text
    # Ensure no duplicate hardcoded mode dictionary in set_mode_by_queue_id
    assert "_QUEUE_MODE_NAMES = {" not in text


def test_app_sidebar_matchmaking_concurrency_invariants():
    """LOBBY-001: Ensure AppSidebar._find_match enforces in-flight concurrency protection and graceful transport logging."""
    sidebar_file = SRC / "ui" / "app_sidebar.py"
    assert sidebar_file.exists()
    text = sidebar_file.read_text(encoding="utf-8")
    assert "_find_match_in_flight" in text
    assert "getattr(self, \"_find_match_in_flight\", False)" in text
    assert "self._find_match_in_flight = True" in text
    assert "self._find_match_in_flight = False" in text
    assert "transport connection failure (no response from client)" in text

def test_app_sidebar_search_refusal_invariants():
    """LOBBY-002: Ensure AppSidebar._search_refusal_message extracts granular client refusal reasons and guards against generic failures."""
    sidebar_file = SRC / "ui" / "app_sidebar.py"
    assert sidebar_file.exists()
    text = sidebar_file.read_text(encoding="utf-8")
    assert "def _search_refusal_message" in text
    assert "_search_refusal_message(res" in text

    from ui.app_sidebar import SidebarWidget
    from unittest.mock import MagicMock

    # Test None response (transport failure)
    msg_none = SidebarWidget._search_refusal_message(None, "Ranked Solo/Duo")
    assert "no response from the League Client" in msg_none

    # Test JSON message payload
    mock_resp_json = MagicMock()
    mock_resp_json.status_code = 400
    mock_resp_json.json.return_value = {"message": "Position preferences required"}
    msg_json = SidebarWidget._search_refusal_message(mock_resp_json, "Ranked Solo/Duo")
    assert msg_json == "Matchmaking failed: Position preferences required"

    # Test 400 fallback
    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.json.side_effect = ValueError("Not JSON")
    msg_400 = SidebarWidget._search_refusal_message(mock_resp_400, "ARAM")
    assert "queue unavailable or requirements not met (ARAM)" in msg_400

    # Test 404 fallback
    mock_resp_404 = MagicMock()
    mock_resp_404.status_code = 404
    mock_resp_404.json.side_effect = ValueError("Not JSON")
    msg_404 = SidebarWidget._search_refusal_message(mock_resp_404)
    assert "lobby not found" in msg_404



def test_silent_excepts_default_path_invariants():
    """EXCEPT-001: Ensure scan_silent_handlers() without arguments defaults to project src and audits all files."""
    from tools.log_silent_excepts import scan_silent_handlers
    res = scan_silent_handlers()
    assert res["status"] in ("PASS", "FAIL")
    assert res["files_audited"] >= 90, f"Expected >= 90 audited files in src/, got {res['files_audited']}"


def test_fast_runner_summary_and_graph_invariants():
    """RUNNER-001: Ensure fast_test_runner supports --summary and --graph without passing invalid flags to pytest."""
    from tools.fast_test_runner import main as runner_main
    from unittest.mock import patch

    with patch("sys.stdout"):
        with pytest.raises(SystemExit) as exc_sum:
            runner_main(["--summary"])
        assert exc_sum.value.code == 0

        with pytest.raises(SystemExit) as exc_graph:
            runner_main(["--graph"])
        assert exc_graph.value.code == 0


def test_entropy_analyzer_default_path_invariants():
    """ENTROPY-001: Ensure run_entropy_summary() and get_top_entropy_files() default to project src and audit all files."""
    from tools.code_entropy_analyzer import run_entropy_summary, get_top_entropy_files
    res = run_entropy_summary()
    assert res["status"] in ("PASS", "WARN", "FAIL")
    assert res["total_files"] >= 90, f"Expected >= 90 audited files in src/, got {res['total_files']}"

    top = get_top_entropy_files(top_n=3)
    assert len(top) == 3
    assert all("entropy_score" in item for item in top)


def test_build_validator_health_and_telemetry_cli_invariants():
    """BUILD-001: Ensure build_validator supports --health/--preflight and --telemetry CLI flags without running full pytest suite."""
    from tools.build_validator import main as validator_main, verify_system_wide_health, get_build_validation_telemetry
    from unittest.mock import patch

    health = verify_system_wide_health()
    assert health["status"] in ("HEALTHY", "DEGRADED", "UNHEALTHY")
    assert "version_aligned" in health
    assert "files_ok" in health
    assert "test_environment_ok" in health
    assert health["duration_ms"] < 200.0

    telemetry = get_build_validation_telemetry()
    assert "validation_cycles_count" in telemetry
    assert "health_status" in telemetry

    with patch("sys.stdout"):
        with pytest.raises(SystemExit) as exc_health:
            validator_main(["--health", "--json"])
        assert exc_health.value.code == 0

        with pytest.raises(SystemExit) as exc_preflight:
            validator_main(["--preflight"])
        assert exc_preflight.value.code == 0

        with pytest.raises(SystemExit) as exc_tel:
            validator_main(["--telemetry", "--json"])
        assert exc_tel.value.code == 0

def test_app_sidebar_and_automation_play_again_invariants():
    """LOBBY-003: Ensure AppSidebar quick actions and AutomationEngine enforce in-flight concurrency protection and bounded play-again attempts."""
    sidebar_file = SRC / "ui" / "app_sidebar.py"
    assert sidebar_file.exists()
    s_text = sidebar_file.read_text(encoding="utf-8")

    assert "_requeue_in_flight" in s_text
    assert "_dodge_in_flight" in s_text
    assert "_play_again_in_flight" in s_text
    assert 'getattr(self, "_requeue_in_flight", False)' in s_text
    assert 'getattr(self, "_dodge_in_flight", False)' in s_text
    assert 'getattr(self, "_play_again_in_flight", False)' in s_text

    auto_file = SRC / "services" / "automation.py"
    assert auto_file.exists()
    a_text = auto_file.read_text(encoding="utf-8")

    assert "_play_again_attempts" in a_text
    assert "self._play_again_attempts >= 3" in a_text
    assert "[400, 404, 409]" in a_text

    # Functional validation of AutomationEngine bounded play-again behavior
    from services.automation import AutomationEngine
    from unittest.mock import MagicMock

    mock_lcu = MagicMock()
    mock_assets = MagicMock()
    mock_config = {
        "auto_honor_enabled": False,
        "skip_stats_enabled": True,
        "auto_save_replays": False,
    }
    engine = AutomationEngine(mock_lcu, mock_assets, mock_config)

    # 1. Immediate 400 refusal should be handled without looping
    mock_eog = MagicMock()
    mock_eog.status_code = 200
    mock_eog.json.return_value = {"gameId": 12345}

    mock_play_again_400 = MagicMock()
    mock_play_again_400.status_code = 400

    mock_lcu.request.side_effect = lambda method, endpoint, **kwargs: (
        mock_eog if endpoint == "/lol-end-of-game/v1/eog-stats-block"
        else mock_play_again_400 if endpoint == "/lol-lobby/v2/play-again"
        else None
    )

    engine._handle_end_of_game("EndOfGame")
    assert engine._play_again_handled is True
    assert engine._play_again_attempts == 0

    # 2. Transient failures bounded to 3 attempts
    engine._honor_handled = False
    engine._play_again_handled = False
    engine._play_again_attempts = 0

    mock_play_again_500 = MagicMock()
    mock_play_again_500.status_code = 500
    mock_lcu.request.side_effect = lambda method, endpoint, **kwargs: (
        mock_eog if endpoint == "/lol-end-of-game/v1/eog-stats-block"
        else mock_play_again_500 if endpoint == "/lol-lobby/v2/play-again"
        else None
    )

    engine._handle_end_of_game("EndOfGame")
    assert engine._play_again_handled is False
    assert engine._play_again_attempts == 1

    engine._honor_handled = False
    engine._handle_end_of_game("EndOfGame")
    assert engine._play_again_handled is False
    assert engine._play_again_attempts == 2

    engine._honor_handled = False
    engine._handle_end_of_game("EndOfGame")
    assert engine._play_again_handled is True
    assert engine._play_again_attempts == 0

def test_dodge_requeue_invariants():
    """LOBBY-004: Ensure AutomationEngine enforces leader permissions, lobby readiness, and bounded attempts on dodge requeue."""
    from services.automation import AutomationEngine
    from unittest.mock import MagicMock

    auto_file = SRC / "services" / "automation.py"
    assert auto_file.exists()
    a_text = auto_file.read_text(encoding="utf-8")

    assert "_dodge_requeue_attempts" in a_text
    assert "self._dodge_requeue_attempts >= 3" in a_text
    assert "canStartActivity" in a_text

    mock_lcu = MagicMock()
    mock_assets = MagicMock()
    mock_config = {
        "auto_requeue": True,
        "auto_honor_enabled": False,
        "skip_stats_enabled": False,
    }
    engine = AutomationEngine(mock_lcu, mock_assets, mock_config)

    # 1. Non-200 (404/400) lobby response: does not attempt search
    mock_lobby_404 = MagicMock()
    mock_lobby_404.status_code = 404
    mock_lcu.request.return_value = mock_lobby_404
    engine._handle_dodge_requeue("Lobby", "ChampSelect")
    assert engine._dodge_requeue_attempts == 0
    mock_lcu.request.assert_called_once_with("GET", "/lol-lobby/v2/lobby", silent=True)

    # 2. Local player is not leader: does not attempt search
    mock_lcu.reset_mock()
    mock_lobby_not_leader = MagicMock()
    mock_lobby_not_leader.status_code = 200
    mock_lobby_not_leader.json.return_value = {
        "localMember": {"isLeader": False},
        "gameConfig": {"queueId": 420},
        "canStartActivity": True,
    }
    mock_lcu.request.return_value = mock_lobby_not_leader
    engine._handle_dodge_requeue("Lobby", "ChampSelect")
    assert engine._dodge_requeue_attempts == 0
    assert mock_lcu.request.call_count == 1

    # 3. Missing queueId or cannot start activity: does not attempt search
    mock_lcu.reset_mock()
    mock_lobby_no_queue = MagicMock()
    mock_lobby_no_queue.status_code = 200
    mock_lobby_no_queue.json.return_value = {
        "localMember": {"isLeader": True},
        "gameConfig": {"queueId": None},
        "canStartActivity": False,
    }
    mock_lcu.request.return_value = mock_lobby_no_queue
    engine._handle_dodge_requeue("Lobby", "ChampSelect")
    assert engine._dodge_requeue_attempts == 0
    assert mock_lcu.request.call_count == 1

    # 4. Valid lobby but search endpoint fails: bounded to 3 attempts
    mock_lcu.reset_mock()
    mock_lobby_valid = MagicMock()
    mock_lobby_valid.status_code = 200
    mock_lobby_valid.json.return_value = {
        "localMember": {"isLeader": True},
        "gameConfig": {"queueId": 420},
        "canStartActivity": True,
    }
    mock_search_state = MagicMock()
    mock_search_state.status_code = 200
    mock_search_state.json.return_value = {"searchState": "Invalid"}

    mock_search_fail = MagicMock()
    mock_search_fail.status_code = 400

    def mock_request_router(method, endpoint, *args, **kwargs):
        if endpoint == "/lol-lobby/v2/lobby":
            return mock_lobby_valid
        if endpoint == "/lol-lobby/v2/lobby/matchmaking/search-state":
            return mock_search_state
        if endpoint == "/lol-lobby/v2/lobby/matchmaking/search":
            return mock_search_fail
        return None

    mock_lcu.request.side_effect = mock_request_router

    # Attempt 1
    engine._handle_dodge_requeue("Lobby", "ChampSelect")
    assert engine._dodge_requeue_attempts == 1

    # Attempt 2
    engine._handle_dodge_requeue("Lobby", "ChampSelect")
    assert engine._dodge_requeue_attempts == 2

    # Attempt 3
    engine._handle_dodge_requeue("Lobby", "ChampSelect")
    assert engine._dodge_requeue_attempts == 3

    # Attempt 4: Should bail immediately without making search request
    mock_lcu.reset_mock()
    engine._handle_dodge_requeue("Lobby", "ChampSelect")
    assert engine._dodge_requeue_attempts == 3
    assert mock_lcu.request.call_count == 0

    # Phase transition out of Lobby resets attempt counter
    engine._handle_dodge_requeue("ChampSelect", "Lobby")
    assert engine._dodge_requeue_attempts == 0


def test_post_game_requeue_can_start_activity_preflight():
    """LOOP-005: Ensure _handle_post_game_requeue verifies canStartActivity before attempting matchmaking search."""
    from services.automation import AutomationEngine
    from unittest.mock import MagicMock

    mock_lcu = MagicMock()
    mock_assets = MagicMock()
    mock_config = {
        "auto_requeue": False,
        "auto_honor_enabled": False,
        "skip_stats_enabled": True,
    }
    engine = AutomationEngine(mock_lcu, mock_assets, mock_config)
    engine._post_game_requeue_pending = True

    mock_search_state = MagicMock(status_code=200)
    mock_search_state.json.return_value = {"searchState": "Invalid"}

    mock_lobby = MagicMock(status_code=200)
    mock_lobby.json.return_value = {
        "localMember": {"isLeader": True},
        "gameConfig": {"queueId": 420},
        "canStartActivity": False,
    }

    def mock_request(method, endpoint, *args, **kwargs):
        if endpoint == "/lol-lobby/v2/lobby/matchmaking/search-state":
            return mock_search_state
        if endpoint == "/lol-lobby/v2/lobby":
            return mock_lobby
        if endpoint == "/lol-lobby/v2/lobby/matchmaking/search":
            raise AssertionError("Should not attempt search when canStartActivity is False")
        return None

    mock_lcu.request.side_effect = mock_request
    engine._handle_post_game_requeue("Lobby", "EndOfGame")
    assert engine._post_game_requeue_pending is True
    assert getattr(engine, "_post_game_requeue_attempts", 0) == 0


def test_queue_manager_start_matchmaking_readiness_preflight():
    """QUEUE-002: Ensure QueueManager.start_matchmaking respects canStartActivity and avoids sending invalid search requests."""
    from services.queue_manager import QueueManager
    from unittest.mock import MagicMock

    mgr = QueueManager.get_instance()
    mock_lcu = MagicMock()
    mock_lcu.is_connected = True

    mock_lobby_not_ready = MagicMock(status_code=200)
    mock_lobby_not_ready.json.return_value = {"canStartActivity": False}

    mock_lcu.request.return_value = mock_lobby_not_ready
    res = mgr.start_matchmaking(mock_lcu, check_readiness=True)
    assert res is False
    mock_lcu.request.assert_called_once_with("GET", "/lol-lobby/v2/lobby", silent=True)

    # When canStartActivity is True, should proceed to post search
    mock_lcu.reset_mock()
    mock_lobby_ready = MagicMock(status_code=200)
    mock_lobby_ready.json.return_value = {"canStartActivity": True}
    mock_search_ok = MagicMock(status_code=200)

    def mock_request(method, endpoint, *args, **kwargs):
        if endpoint == "/lol-lobby/v2/lobby":
            return mock_lobby_ready
        if endpoint == "/lol-lobby/v2/lobby/matchmaking/search":
            return mock_search_ok
        return None

    mock_lcu.request.side_effect = mock_request
    res = mgr.start_matchmaking(mock_lcu, check_readiness=True)
    assert res is True
    assert mock_lcu.request.call_count == 2


def test_app_sidebar_find_match_lobby_readiness_invariants():
    """LOBBY-003: Ensure AppSidebar._find_match checks lobby readiness before initiating search."""
    sidebar_file = SRC / "ui" / "app_sidebar.py"
    assert sidebar_file.exists()
    text = sidebar_file.read_text(encoding="utf-8")
    assert "lobby_check = self.lcu.request(\"GET\", \"/lol-lobby/v2/lobby\")" in text
    assert "canStartActivity" in text
    assert "Cannot start matchmaking" in text


