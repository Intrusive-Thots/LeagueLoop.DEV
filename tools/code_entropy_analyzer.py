#!/usr/bin/env python3
"""
code_entropy_analyzer.py — Static Code Entropy & Quality Auditor for LeagueLoop.DEV

Audits Python codebases for technical debt, cyclomatic complexity, bare excepts,
and oversized functions.
"""

import os
import sys
import ast
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class PythonEntropyAuditor(ast.NodeVisitor):
    def __init__(self):
        self.complexity = 0
        self.functions = 0
        self.classes = 0
        self.unclosed_resources = []
        self.bare_excepts = []
        self.large_functions = []

    def visit_FunctionDef(self, node):
        self.functions += 1
        fn_lines = node.end_lineno - node.lineno if hasattr(node, "end_lineno") else 0
        if fn_lines > 50:
            self.large_functions.append({"name": node.name, "lines": fn_lines, "line_no": node.lineno})
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node):
        self.classes += 1
        self.generic_visit(node)

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.type is None:
            self.bare_excepts.append(node.lineno)
        self.generic_visit(node)


def analyze_python_file(filepath: Union[str, Path]) -> Dict[str, Any]:
    file_str = str(filepath)
    try:
        with open(file_str, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()

        tree = ast.parse(code)
        auditor = PythonEntropyAuditor()
        auditor.visit(tree)

        lines = code.splitlines()
        loc = len(lines)
        empty_lines = sum(1 for line in lines if not line.strip())
        comment_lines = sum(1 for line in lines if line.strip().startswith("#"))

        # Entropy score: complexity * 2 + bare_excepts * 10 + large_functions * 5
        entropy_score = (auditor.complexity * 2) + (len(auditor.bare_excepts) * 10) + (len(auditor.large_functions) * 5)

        return {
            "file": file_str,
            "loc": loc,
            "code_lines": loc - empty_lines - comment_lines,
            "comment_lines": comment_lines,
            "classes": auditor.classes,
            "functions": auditor.functions,
            "cyclomatic_complexity": auditor.complexity,
            "bare_excepts": auditor.bare_excepts,
            "large_functions": auditor.large_functions,
            "entropy_score": round(entropy_score, 2),
            "status": "PASS" if entropy_score < 30 else "WARN" if entropy_score < 60 else "FAIL",
        }
    except Exception as e:
        return {"file": file_str, "error": str(e), "status": "ERROR"}


DEFAULT_SRC = PROJECT_ROOT / "src"


def _resolve_target_dir(target_dir: Optional[Union[str, Path]] = None) -> str:
    """Resolves target directory, prioritizing PROJECT_ROOT / 'src' on defaults."""
    if target_dir is None or target_dir == "src" or target_dir == Path("src"):
        return str(DEFAULT_SRC if DEFAULT_SRC.exists() else "src")
    p = Path(target_dir)
    if not p.is_absolute():
        repo_candidate = PROJECT_ROOT / p
        if repo_candidate.exists():
            return str(repo_candidate)
    return str(target_dir)


def analyze_directory(target_dir: Union[str, Path]) -> List[Dict[str, Any]]:
    results = []
    target_str = str(target_dir)
    for root, _, files in os.walk(target_str):
        if any(ignored in root for ignored in [".git", "__pycache__", "node_modules", ".venv", "snapshots"]):
            continue
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                results.append(analyze_python_file(full_path))
    return results


def run_entropy_summary(target_dir: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Computes an aggregate entropy summary for a target directory."""
    path = _resolve_target_dir(target_dir)
    results = analyze_directory(path)
    total_files = len(results)
    if total_files == 0:
        return {"total_files": 0, "avg_entropy": 0, "bare_excepts_total": 0, "status": "PASS"}

    total_entropy = sum(r.get("entropy_score", 0) for r in results if "entropy_score" in r)
    bare_excepts = sum(len(r.get("bare_excepts", [])) for r in results if "bare_excepts" in r)
    errors = sum(1 for r in results if r.get("status") == "ERROR")
    avg_entropy = round(total_entropy / total_files, 2)

    status = "FAIL" if errors > 0 or bare_excepts > 0 else "PASS" if avg_entropy < 30 else "WARN"

    return {
        "total_files": total_files,
        "avg_entropy": avg_entropy,
        "bare_excepts_total": bare_excepts,
        "syntax_errors": errors,
        "status": status,
    }


def get_top_entropy_files(target_dir: Optional[Union[str, Path]] = None, top_n: int = 5) -> List[Dict[str, Any]]:
    """Retrieves top N files sorted by entropy descending."""
    path = _resolve_target_dir(target_dir)
    results = analyze_directory(path) if os.path.isdir(path) else [analyze_python_file(path)]
    sorted_res = sorted(results, key=lambda x: x.get("entropy_score", 0), reverse=True)
    return sorted_res[:top_n]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Code Entropy & Static Audit Tool")
    parser.add_argument("pos_target", nargs="*", default=None, help="File or directory path(s) to analyze (positional)")
    parser.add_argument("--target", default=None, help="File or directory path to analyze (flag)")
    parser.add_argument("--top", "-n", type=int, default=None, help="Display only top N files sorted by entropy descending")
    parser.add_argument("--summary", action="store_true", help="Display aggregate codebase entropy summary")
    parser.add_argument("--max-entropy", type=float, default=None, help="Fail if average entropy exceeds this threshold")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args(argv)

    targets: List[str] = []
    if args.target:
        targets.append(args.target)
    if args.pos_target:
        if isinstance(args.pos_target, list):
            targets.extend(args.pos_target)
        else:
            targets.append(str(args.pos_target))
    if not targets:
        targets = [str(DEFAULT_SRC if DEFAULT_SRC.exists() else "src")]
    else:
        resolved_targets: List[str] = []
        for tp in targets:
            tp_path = Path(tp)
            if not tp_path.is_absolute() and (PROJECT_ROOT / tp_path).exists():
                resolved_targets.append(str(PROJECT_ROOT / tp_path))
            elif os.path.exists(tp):
                resolved_targets.append(tp)
            else:
                print(f"Error: Target path '{tp}' does not exist.", file=sys.stderr)
                sys.exit(1)
        targets = resolved_targets

    if args.summary:
        all_results = []
        for tp in targets:
            if os.path.isdir(tp):
                all_results.extend(analyze_directory(tp))
            else:
                all_results.append(analyze_python_file(tp))

        total_files = len(all_results)
        if total_files == 0:
            summary = {"total_files": 0, "avg_entropy": 0.0, "bare_excepts_total": 0, "syntax_errors": 0, "status": "PASS"}
        else:
            total_entropy = sum(r.get("entropy_score", 0) for r in all_results if "entropy_score" in r)
            bare_excepts = sum(len(r.get("bare_excepts", [])) for r in all_results if "bare_excepts" in r)
            errors = sum(1 for r in all_results if r.get("status") == "ERROR")
            avg_entropy = round(total_entropy / total_files, 2)
            status = "FAIL" if errors > 0 or bare_excepts > 0 else "PASS" if avg_entropy < 30 else "WARN"
            summary = {
                "total_files": total_files,
                "avg_entropy": avg_entropy,
                "bare_excepts_total": bare_excepts,
                "syntax_errors": errors,
                "status": status,
            }

        if args.max_entropy is not None and summary["avg_entropy"] > args.max_entropy:
            summary["status"] = "FAIL"
            summary["threshold_exceeded"] = True
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("=== Code Entropy Summary ===")
            print(f"Target: {', '.join(targets)}")
            print(f"Status: [{summary['status']}]")
            print(f"Files Audited: {summary['total_files']}")
            print(f"Average Entropy: {summary['avg_entropy']}")
            print(f"Bare Excepts: {summary['bare_excepts_total']}")
            print(f"Syntax Errors: {summary['syntax_errors']}")
            if summary.get("threshold_exceeded"):
                print(f"Threshold Exceeded: Average entropy {summary['avg_entropy']} > {args.max_entropy}")
        sys.exit(0 if summary["status"] != "FAIL" else 1)

    res = []
    for tp in targets:
        if os.path.isfile(tp):
            res.append(analyze_python_file(tp))
        else:
            res.extend(analyze_directory(tp))

    if args.top is not None and args.top > 0:
        res = sorted(res, key=lambda x: x.get("entropy_score", 0), reverse=True)[:args.top]

    if args.max_entropy is not None:
        valid_res = [r for r in res if "entropy_score" in r]
        avg_entropy = round(sum(r.get("entropy_score", 0) for r in valid_res) / len(valid_res), 2) if valid_res else 0.0
        if avg_entropy > args.max_entropy:
            if args.json:
                print(json.dumps({"error": f"Average entropy {avg_entropy} > {args.max_entropy}", "results": res}, indent=2))
            else:
                print(f"Threshold Exceeded: Average entropy {avg_entropy} > {args.max_entropy}", file=sys.stderr)
            sys.exit(1)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print("=== Code Entropy & Static Audit Report ===")
        for item in res:
            if "error" in item:
                print(f"[{item['status']}] {item['file']}: Error - {item['error']}")
            else:
                print(f"[{item['status']}] {item['file']}")
                print(f"  - LOC: {item['loc']} (Code: {item['code_lines']}, Comments: {item['comment_lines']})")
                print(f"  - Complexity: {item['cyclomatic_complexity']} | Functions: {item['functions']} | Classes: {item['classes']}")
                print(f"  - Entropy Score: {item['entropy_score']}")
                if item["bare_excepts"]:
                    print(f"  - Bare excepts on lines: {item['bare_excepts']}")
                if item["large_functions"]:
                    print(f"  - Large functions (>50 lines): {[f['name'] for f in item['large_functions']]}")
            print("-" * 50)


if __name__ == "__main__":
    main()
