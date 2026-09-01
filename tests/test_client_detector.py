import pytest
import psutil
from unittest.mock import patch, MagicMock
from utils.client_detector import scan_clients, _cached_results

@pytest.fixture(autouse=True)
def reset_cache():
    """Reset the scan_clients cache before each test."""
    from utils.client_detector import _cached_results
    _cached_results.update({
        "league": {"port": None, "token": None, "connected": False, "pid": None},
        "riot": {"port": None, "token": None, "connected": False, "pid": None}
    })
    yield

def _create_mock_proc(name, pid, cmdline_args, access_denied=False):
    mock_proc = MagicMock()
    mock_proc.info = {"name": name, "pid": pid}

    if access_denied:
        mock_proc.cmdline.side_effect = psutil.AccessDenied(pid=pid)
    else:
        mock_proc.cmdline.return_value = cmdline_args

    return mock_proc

@patch('utils.client_detector.psutil.process_iter')
def test_scan_clients_happy_path(mock_process_iter):
    """Test parsing of standard command line arguments."""
    mock_process_iter.return_value = [
        _create_mock_proc("LeagueClientUx.exe", 1234, ["--app-port=5555", "--remoting-auth-token=abc-123_def"]),
        _create_mock_proc("RiotClientServices.exe", 5678, ["--app-port=6666", "--remoting-auth-token=riot-token"])
    ]

    results = scan_clients(force=True)

    assert results["league"]["port"] == "5555"
    assert results["league"]["token"] == "abc-123_def"
    assert results["league"]["connected"] is True

    assert results["riot"]["port"] == "6666"
    assert results["riot"]["token"] == "riot-token"
    assert results["riot"]["connected"] is True

@patch('utils.client_detector.psutil.process_iter')
def test_scan_clients_joined_args(mock_process_iter):
    """Test parsing when command line arguments are joined into a single string."""
    # Sometimes WMI or other tools return the entire command line as a single string
    mock_process_iter.return_value = [
        _create_mock_proc("LeagueClientUx.exe", 1234, ['"C:\\Path\\LeagueClientUx.exe" --app-port=1111 --remoting-auth-token=test-token-1'])
    ]

    results = scan_clients(force=True)

    assert results["league"]["port"] == "1111"
    assert results["league"]["token"] == "test-token-1"
    assert results["league"]["connected"] is True

@patch('utils.client_detector.psutil.process_iter')
def test_scan_clients_unexpected_chars(mock_process_iter):
    """Test parsing when arguments contain extra quotes or formatting."""
    mock_process_iter.return_value = [
        _create_mock_proc("LeagueClientUx.exe", 1234, ['--app-port=2222"', '--remoting-auth-token=test-token-2"']),
        _create_mock_proc("RiotClientServices.exe", 5678, ["--app-port=3333", "--remoting-auth-token=riot_token_3"])
    ]

    results = scan_clients(force=True)

    # Regex should extract the numeric port even if quotes surround it (actually the current regex matches numbers, so it will extract just 2222)
    # The regex for token is [\w-]+ so it will extract test-token-2
    assert results["league"]["port"] == "2222"
    assert results["league"]["token"] == "test-token-2"

    assert results["riot"]["port"] == "3333"
    assert results["riot"]["token"] == "riot_token_3"

@patch('utils.client_detector.psutil.process_iter')
def test_scan_clients_missing_args(mock_process_iter):
    """Test behavior when port or token is missing from command line."""
    mock_process_iter.return_value = [
        # Missing token
        _create_mock_proc("LeagueClientUx.exe", 1234, ["--app-port=4444", "--other-arg=value"]),
        # Missing port
        _create_mock_proc("RiotClientServices.exe", 5678, ["--remoting-auth-token=riot-token", "--other-arg=value"])
    ]

    # We also mock lockfile fallbacks so they don't unexpectedly pass
    with patch('utils.client_detector.get_league_lockfile', return_value=(None, None)), \
         patch('utils.client_detector.get_riot_lockfile', return_value=(None, None)):

        results = scan_clients(force=True)

        assert results["league"]["port"] is None
        assert results["league"]["token"] is None
        assert results["league"]["connected"] is False

        assert results["riot"]["port"] is None
        assert results["riot"]["token"] is None
        assert results["riot"]["connected"] is False

@patch('utils.client_detector.psutil.process_iter')
def test_scan_clients_access_denied(mock_process_iter):
    """Test handling of psutil.AccessDenied when reading cmdline."""
    mock_process_iter.return_value = [
        _create_mock_proc("LeagueClientUx.exe", 1234, [], access_denied=True)
    ]

    with patch('utils.client_detector.get_league_lockfile', return_value=("7777", "fallback-token")):
        results = scan_clients(force=True)

        # Should gracefully handle AccessDenied and use fallback
        assert results["league"]["port"] == "7777"
        assert results["league"]["token"] == "fallback-token"
        assert results["league"]["connected"] is True
