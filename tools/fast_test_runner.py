#!/usr/bin/env python3
"""
fast_test_runner.py — High-Performance Targeted Test Runner for LeagueLoop.DEV

Reduces test execution time from >20s to <2s by intelligently mapping modified
source and test files to their respective pytest targets using AST dependency analysis.
"""

import os
import ast
import re
import sys
import time
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Set, Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"
SRC_DIR = PROJECT_ROOT / "src"


class ASTTestDependencyGraph:
    """Builds and queries an AST-based module dependency graph for test suites."""

    def __init__(self, tests_dir: Path):
        self.tests_dir = tests_dir
        self.module_to_tests: Dict[str, Set[str]] = {}
        self._build_graph()

    def _build_graph(self):
        if not self.tests_dir.exists():
            return

        for test_file in self.tests_dir.glob("test_*.py"):
            try:
                tree = ast.parse(
                    test_file.read_text(encoding="utf-8", errors="replace"),
                    filename=str(test_file)
                )
            except Exception:
                continue

            test_path_str = str(test_file.resolve())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self._register_module(alias.name, test_path_str)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self._register_module(node.module, test_path_str)

    def _register_module(self, mod_name: str, test_path_str: str):
        # Register full module string, e.g. "src.core.events"
        self.module_to_tests.setdefault(mod_name, set()).add(test_path_str)
        # Register relative forms without "src." prefix, e.g. "core.events"
        if mod_name.startswith("src."):
            self.module_to_tests.setdefault(mod_name[4:], set()).add(test_path_str)
        # Register the leaf stem for direct matching
        leaf = mod_name.split(".")[-1]
        self.module_to_tests.setdefault(leaf, set()).add(test_path_str)

    def find_tests_for_source(self, source_rel_path: str) -> Set[str]:
        """Finds all test suites that import the given source file."""
        p = Path(source_rel_path)
        matching: Set[str] = set()

        # Generate candidates from path, e.g. "src/core/events.py"
        # -> ["src.core.events", "core.events", "events"]
        parts = list(p.with_suffix("").parts)
        if not parts:
            return matching

        # 1. Full dotted path
        dotted_full = ".".join(parts)
        if dotted_full in self.module_to_tests:
            matching.update(self.module_to_tests[dotted_full])

        # 2. Stripped "src." or "tools." prefix
        if parts[0] in ("src", "tools") and len(parts) > 1:
            dotted_rel = ".".join(parts[1:])
            if dotted_rel in self.module_to_tests:
                matching.update(self.module_to_tests[dotted_rel])

        # 3. Stem name matching
        stem = p.stem.lower()
        if stem in self.module_to_tests:
            matching.update(self.module_to_tests[stem])

        return matching


def get_git_modified_files(staged_only: bool = False) -> Set[str]:
    """Retrieve all untracked, unstaged, or staged modified files."""
    modified = set()
    try:
        git_args = ["git", "status", "--porcelain"]
        if staged_only:
            git_args.append("--untracked-files=no")

        res = subprocess.run(
            git_args,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True
        )
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                if staged_only and not line.startswith(("M ", "A ", "R ")):
                    continue
                modified.add(parts[-1].replace("\\", "/"))
    except Exception:
        pass

    # Also check latest commit if working tree is clean and not requesting staged only
    if not modified and not staged_only:
        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if line.strip():
                        modified.add(line.strip().replace("\\", "/"))
        except Exception:
            pass

    return modified


def map_source_to_tests(target_files: Set[str], graph: Optional[ASTTestDependencyGraph] = None) -> List[str]:
    """Maps modified files in src/ or tests/ to relevant test file paths."""
    if graph is None:
        graph = ASTTestDependencyGraph(TESTS_DIR)

    test_targets: Set[str] = set()

    for path_str in target_files:
        p = Path(path_str)

        # 0. Pytest node ID reference (e.g., tests/test_foo.py::TestClass::test_method)
        if "::" in path_str:
            file_part, *selector_parts = path_str.split("::")
            fp = Path(file_part)
            full_test_path = None
            if fp.parts and fp.parts[0] == "tests":
                cand = PROJECT_ROOT / fp
                if cand.exists():
                    full_test_path = cand
            elif fp.name.startswith("test_") or fp.suffix == ".py":
                cand = TESTS_DIR / fp.name
                if cand.exists():
                    full_test_path = cand
            elif (PROJECT_ROOT / fp).exists():
                full_test_path = PROJECT_ROOT / fp

            if full_test_path:
                selector = "::".join(selector_parts)
                test_targets.add(f"{full_test_path.resolve()}::{selector}")
                continue

        # 1. Direct test file reference
        if p.parts and p.parts[0] == "tests" and p.suffix == ".py":
            if p.name == "conftest.py":
                # conftest affects shared fixtures; trigger full test suite
                return []
            if p.name.startswith("test_"):
                full = PROJECT_ROOT / p
                if full.exists():
                    test_targets.add(str(full.resolve()))
            continue

        if p.name.startswith("test_") and p.suffix == ".py":
            full = TESTS_DIR / p.name
            if full.exists():
                test_targets.add(str(full.resolve()))
            continue

        # 2. AST dependency mapping
        ast_matches = graph.find_tests_for_source(path_str)
        test_targets.update(ast_matches)

        # 3. Direct pattern fallback: test_{stem}.py
        stem = p.stem.lower()
        direct_match = TESTS_DIR / f"test_{stem}.py"
        if direct_match.exists():
            test_targets.add(str(direct_match.resolve()))

        # 4. Specialized service mappings for composite components
        if "account" in stem:
            for cand in ["test_account_detection.py", "test_account_switching.py", "test_account_identity.py", "test_account_session_vault.py"]:
                t = TESTS_DIR / cand
                if t.exists():
                    test_targets.add(str(t.resolve()))

        if "api_handler" in stem:
            for cand in ["test_api_handler.py", "test_ws_telemetry.py", "test_api_performance_control.py"]:
                t = TESTS_DIR / cand
                if t.exists():
                    test_targets.add(str(t.resolve()))

        if "automation" in stem:
            for cand in ["test_automation.py", "test_automation_draft.py", "test_automation_wiring.py"]:
                t = TESTS_DIR / cand
                if t.exists():
                    test_targets.add(str(t.resolve()))

        if "loot" in stem:
            t = TESTS_DIR / "test_loot_service.py"
            if t.exists():
                test_targets.add(str(t.resolve()))

    return sorted(list(test_targets))


def run_tests(targets: List[str], extra_args: List[str] = None) -> int:
    python_exe = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    if not Path(python_exe).exists():
        python_exe = sys.executable

    cmd = [python_exe, "-m", "pytest", "-q", "--no-cov"]
    if extra_args:
        cmd.extend(extra_args)
    if targets:
        cmd.extend(targets)

    print(f"Executing: {' '.join(cmd)}")
    start = time.perf_counter()
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    duration = time.perf_counter() - start
    print(f"\nExecution finished in {duration:.2f}s (Exit code: {res.returncode})")
    return res.returncode


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if "-h" in argv or "--help" in argv:
        parser = argparse.ArgumentParser(description="LeagueLoop Fast Targeted Test Runner with AST Analysis")
        parser.add_argument("--all", action="store_true", help="Run full test suite unconditionally")
        parser.add_argument("--staged", action="store_true", help="Only map git staged changes")
        parser.add_argument("--graph", action="store_true", help="Print module AST dependency summary")
        parser.add_argument("targets", nargs="*", help="Optional source files, test files, or pytest flags")
        parser.print_help()
        sys.exit(0)

    graph = ASTTestDependencyGraph(TESTS_DIR)

    option_with_arg = {"-k", "-m", "-o", "-c", "-W", "--override-ini", "--ignore", "--capture"}

    run_all = False
    staged = False
    show_graph = False
    explicit_files = set()
    pytest_extra = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--all":
            run_all = True
        elif arg == "--staged":
            staged = True
        elif arg == "--graph":
            show_graph = True
        elif arg in option_with_arg:
            pytest_extra.append(arg)
            if i + 1 < len(argv):
                i += 1
                pytest_extra.append(argv[i])
        elif any(arg.startswith(f"{opt}=") for opt in option_with_arg) or arg.startswith("-"):
            pytest_extra.append(arg)
        else:
            explicit_files.add(arg.replace("\\", "/"))
        i += 1

    if show_graph:
        print(f"[AST Graph] Indexed {len(graph.module_to_tests)} module keys across {len(list(TESTS_DIR.glob('test_*.py')))} test files.")
        for k in sorted(graph.module_to_tests.keys())[:20]:
            print(f"  {k} -> {len(graph.module_to_tests[k])} test suites")
        sys.exit(0)

    if run_all:
        print("[Fast Runner] Running full test suite...")
        sys.exit(run_tests([], pytest_extra))

    if explicit_files:
        print(f"[Fast Runner] Explicit targets requested ({len(explicit_files)}):")
        for f in sorted(explicit_files):
            print(f"  - {f}")
        selected_targets = map_source_to_tests(explicit_files, graph)
    else:
        modified = get_git_modified_files(staged_only=staged)
        print(f"[Fast Runner] Detected modified files in git ({len(modified)}):")
        for m in sorted(modified):
            print(f"  - {m}")
        selected_targets = map_source_to_tests(modified, graph)

    if not selected_targets:
        has_python_changes = any(
            f.endswith(".py") or ".py::" in f for f in (explicit_files or modified)
        )
        if (explicit_files or modified) and not has_python_changes:
            print("[Fast Runner] Only non-code/memory files modified. Running targeted regression guards...")
            smoke_targets = []
            for guard in [
                "test_regression_guards.py",
                "test_autonomous_improvement_runner.py",
                "test_leagueloop_diagnostics.py",
                "test_code_entropy_analyzer.py",
                "test_fast_test_runner.py",
            ]:
                guard_path = TESTS_DIR / guard
                if guard_path.exists():
                    smoke_targets.append(str(guard_path.resolve()))
            if smoke_targets:
                sys.exit(run_tests(smoke_targets, pytest_extra))

        print("[Fast Runner] No targeted tests found for specified files. Running full test suite...")
        sys.exit(run_tests([], pytest_extra))

    print(f"\n[Fast Runner] Selected targeted test suites ({len(selected_targets)}):")
    for t in selected_targets:
        print(f"  - {Path(t.split('::')[0]).name if '::' in t else Path(t).name}")

    sys.exit(run_tests(selected_targets, pytest_extra))


if __name__ == "__main__":
    main()
