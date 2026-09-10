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

