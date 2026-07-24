"""
repo_index — Fast repository intelligence scanner.

Walks the project tree once per cycle, caching:
  - file count by extension
  - total lines of code (Python only)
  - list of Python modules with line counts
  - TODO / FIXME / HACK comments found
  - files missing module-level docstrings
"""

import os
import re
import json
import time
from pathlib import Path
from typing import Dict, List, Any

# Directories to skip entirely
_SKIP_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", "dist", "build", "eggs",
    ".agents", "self_improving",
}

# Extensions counted in the file census
_CODE_EXTS = {".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".yaml", ".yml"}


def _is_python(p: Path) -> bool:
    return p.suffix == ".py"


def scan_repository(root: str) -> Dict[str, Any]:
    """Walk *root* and return a structured index of the codebase."""
    root_path = Path(root)
    start = time.perf_counter()

    ext_counts: Dict[str, int] = {}
    py_modules: List[Dict[str, Any]] = []
    todos: List[Dict[str, Any]] = []
    missing_docstrings: List[str] = []
    total_py_lines = 0
    total_files = 0

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune skip dirs in-place so os.walk doesn't descend
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            ext = fpath.suffix.lower()
            if ext not in _CODE_EXTS:
                continue

            total_files += 1
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

            if not _is_python(fpath):
                continue

            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue

            line_count = len(lines)
            total_py_lines += line_count

            rel = str(fpath.relative_to(root_path))
            py_modules.append({"path": rel, "lines": line_count})

            # Check for TODO / FIXME / HACK markers
            for i, line in enumerate(lines, 1):
                m = re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE)
                if m:
                    marker = m.group(1).upper()
                    todos.append({
                        "file": rel,
                        "line": i,
                        "marker": marker,
                        "text": line.strip()[:120],
                    })

            # Check for missing module docstring
            stripped = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
            if stripped and not (stripped[0].startswith('"""') or stripped[0].startswith("'''")):
                missing_docstrings.append(rel)

    elapsed = round(time.perf_counter() - start, 3)

    return {
        "root": str(root_path),
        "scan_time_sec": elapsed,
        "total_files": total_files,
        "ext_counts": ext_counts,
        "python_modules": sorted(py_modules, key=lambda m: -m["lines"]),
        "total_py_lines": total_py_lines,
        "todos": todos,
        "missing_docstrings": missing_docstrings,
    }


def save_index(index: Dict[str, Any], dest: str) -> None:
    """Persist the repo index to a JSON file."""
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    idx = scan_repository(root)
    print(json.dumps(idx, indent=2))
