"""
memory — Read/write persistent memory files (episodic, failures, procedural, etc.)

Provides a unified interface over the two memory locations:
  - Global:    C:\\Users\\Administrator\\.gemini\\antigravity\\memory\\
  - Workspace: <project>\\.agents\\memory\\

The loop reads from both, and writes new entries to the workspace memory.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


GLOBAL_MEMORY = Path(r"C:\Users\Administrator\.gemini\antigravity\memory")
IMPROVEMENTS_BACKLOG = Path(r"C:\Users\Administrator\.gemini\antigravity\improvements\backlog.md")
ARTIFACT_REGISTRY = Path(r"C:\Users\Administrator\.gemini\antigravity\tools\artifact_registry.json")


def _load_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = []
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        return json.loads(text) if text else default
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class MemoryStore:
    """Unified read/write interface for workspace + global memory."""

    def __init__(self, workspace_root: str):
        self.workspace_memory = Path(workspace_root) / ".agents" / "memory"
        self.workspace_memory.mkdir(parents=True, exist_ok=True)

    # ── Readers ──────────────────────────────────────────────────────

    def load_episodic(self) -> List[Dict]:
        """Load episodic memory from workspace."""
        return _load_json(self.workspace_memory / "episodic.json", [])

    def load_failures(self) -> List[Dict]:
        """Load known failure patterns from workspace."""
        return _load_json(self.workspace_memory / "failures.json", [])

    def load_procedural(self) -> List[Dict]:
        """Load procedural memory from workspace."""
        return _load_json(self.workspace_memory / "procedural.json", [])

    def load_optimizations(self) -> List[Dict]:
        """Load optimizations log from workspace."""
        return _load_json(self.workspace_memory / "optimizations.json", [])

    def load_semantic(self) -> List[Dict]:
        """Load semantic memory from workspace."""
        return _load_json(self.workspace_memory / "semantic.json", [])

    def load_global_metrics(self) -> Dict:
        """Load metrics from the global memory store."""
        return _load_json(GLOBAL_MEMORY / "metrics.json", {"runs": [], "averages": {}})

    def load_artifact_registry(self) -> Dict:
        """Load the artifact registry."""
        return _load_json(ARTIFACT_REGISTRY, {"assets": []})

    # ── Writers ──────────────────────────────────────────────────────

    def append_episodic(self, entry: Dict) -> None:
        """Append an episodic memory entry (with auto-timestamp)."""
        entries = self.load_episodic()
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        entries.append(entry)
        _save_json(self.workspace_memory / "episodic.json", entries)

    def append_failure(self, entry: Dict) -> None:
        """Append a failure pattern."""
        entries = self.load_failures()
        # Deduplicate by error_pattern
        existing = {e.get("error_pattern", "") for e in entries}
        if entry.get("error_pattern", "") not in existing:
            entries.append(entry)
            _save_json(self.workspace_memory / "failures.json", entries)

    def append_optimization(self, entry: Dict) -> None:
        """Append an optimization record."""
        entries = self.load_optimizations()
        entries.append(entry)
        _save_json(self.workspace_memory / "optimizations.json", entries)

    def save_loop_state(self, state: Dict) -> None:
        """Persist the loop's latest state (baseline, run count, etc.)."""
        _save_json(self.workspace_memory / "loop_state.json", state)

    def load_loop_state(self) -> Dict:
        """Load the loop's persisted state."""
        return _load_json(self.workspace_memory / "loop_state.json", {})

    # ── Global writes (metrics + backlog) ────────────────────────────

    def update_global_metrics(self, run_metrics: Dict) -> None:
        """Append a metrics run to the global metrics store."""
        data = self.load_global_metrics()
        run_metrics["timestamp"] = datetime.now(timezone.utc).isoformat()
        data.setdefault("runs", []).append(run_metrics)
        _save_json(GLOBAL_MEMORY / "metrics.json", data)

    def append_backlog_item(self, description: str, priority: str = "Medium") -> None:
        """Append an item to the improvements backlog.md."""
        IMPROVEMENTS_BACKLOG.parent.mkdir(parents=True, exist_ok=True)
        if not IMPROVEMENTS_BACKLOG.exists():
            IMPROVEMENTS_BACKLOG.write_text(
                "# Continuous Self-Improvement Backlog\n\n"
                "| Priority | Description | Status |\n"
                "| :--- | :--- | :--- |\n",
                encoding="utf-8",
            )
        content = IMPROVEMENTS_BACKLOG.read_text(encoding="utf-8")
        if description in content:
            return  # Already logged
        row = f"| {priority} | {description} | Planned |\n"
        if not content.endswith("\n"):
            content += "\n"
        content += row
        IMPROVEMENTS_BACKLOG.write_text(content, encoding="utf-8")
