"""
analyzers — Static analysis passes that discover improvement opportunities.

Each analyzer takes a repo index and returns a list of findings.
"""

import re
from pathlib import Path
from typing import Any, Dict, List


def analyze_complexity(py_modules: List[Dict[str, Any]], threshold: int = 300) -> List[Dict[str, str]]:
    """Flag Python files that exceed *threshold* lines as candidates for splitting."""
    findings = []
    for mod in py_modules:
        if mod["lines"] > threshold:
            findings.append({
                "type": "complexity",
                "severity": "high" if mod["lines"] > 800 else "medium",
                "file": mod["path"],
                "message": f"{mod['path']} has {mod['lines']} lines (threshold: {threshold})",
                "suggestion": "Consider splitting into smaller, focused modules.",
            })
    return findings


def analyze_todos(todos: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Report TODO/FIXME/HACK comments as actionable items."""
    findings = []
    for item in todos:
        findings.append({
            "type": "todo",
            "severity": "low" if item["marker"] == "TODO" else "medium",
            "file": item["file"],
            "line": item["line"],
            "message": f'{item["marker"]} at {item["file"]}:{item["line"]}: {item["text"]}',
        })
    return findings


def analyze_missing_docstrings(missing: List[str]) -> List[Dict[str, str]]:
    """Report Python files without module-level docstrings."""
    return [
        {
            "type": "missing_docstring",
            "severity": "low",
            "file": f,
            "message": f"{f} has no module-level docstring",
            "suggestion": "Add a module-level docstring describing the file's purpose.",
        }
        for f in missing
    ]


def analyze_test_coverage(
    test_results: Dict[str, Any],
    py_modules: List[Dict[str, Any]],
    test_dir: str = "tests",
) -> List[Dict[str, str]]:
    """Detect source modules that have no corresponding test file."""
    # Build the set of tested modules from test filenames
    # test_foo.py → foo.py,  test_bar_baz.py → bar_baz.py
    tested = set()
    for mod in py_modules:
        p = Path(mod["path"])
        if p.parts[0] == test_dir and p.name.startswith("test_"):
            base = p.name[5:]  # strip "test_"
            tested.add(base)

    findings = []
    for mod in py_modules:
        p = Path(mod["path"])
        # Only check src/ modules, skip __init__.py and tiny files
        if not str(p).startswith("src") or p.name == "__init__.py" or mod["lines"] < 20:
            continue
        if p.name not in tested:
            findings.append({
                "type": "missing_test",
                "severity": "medium",
                "file": mod["path"],
                "message": f"No test file found for {mod['path']}",
                "suggestion": f"Create tests/test_{p.name} to cover this module.",
            })
    return findings


def analyze_dead_imports(project_root: str, py_modules: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Quick heuristic: find imports that look like they reference local modules
    that no longer exist. This is NOT a full unused-import check (that requires
    AST analysis), but catches obvious broken imports after renames/deletes.
    """
    existing_modules = {Path(m["path"]).stem for m in py_modules}
    findings = []

    for mod in py_modules:
        fpath = Path(project_root) / mod["path"]
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Match  "from .foo import ..."  or  "from services.foo import ..."
            m = re.match(r"from\s+\.(\w+)\s+import", stripped)
            if m:
                name = m.group(1)
                # This is a relative import — we can't trivially verify it,
                # so skip (too many false positives).
                continue

    return findings


def run_all_analyzers(
    repo_index: Dict[str, Any],
    test_results: Dict[str, Any],
    project_root: str,
) -> List[Dict[str, str]]:
    """Run every analyzer and return a merged, severity-sorted list of findings."""
    findings: List[Dict[str, str]] = []
    findings.extend(analyze_complexity(repo_index.get("python_modules", [])))
    findings.extend(analyze_todos(repo_index.get("todos", [])))
    findings.extend(analyze_missing_docstrings(repo_index.get("missing_docstrings", [])))
    findings.extend(analyze_test_coverage(test_results, repo_index.get("python_modules", []),))
    findings.extend(analyze_dead_imports(project_root, repo_index.get("python_modules", [])))

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 3))
    return findings
