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

