"""Scan entire project for syntax errors, import errors, and common issues."""
import os
import py_compile
import ast
import sys
import importlib
import traceback

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_ROOT = os.path.join(os.path.dirname(PROJECT_ROOT), "src")
sys.path.insert(0, SRC_ROOT)

def scan_syntax():
    """Check all .py files for syntax errors."""
    errors = []
    count = 0
    base = os.path.dirname(PROJECT_ROOT)
    for scan_dir in ["src", "tests"]:
        dirpath = os.path.join(base, scan_dir)
        if not os.path.isdir(dirpath):
            continue
        for root, dirs, files in os.walk(dirpath):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    count += 1
                    try:
                        py_compile.compile(path, doraise=True)
                    except py_compile.PyCompileError as e:
                        errors.append((path, str(e)))
    # Also check run.py
    runpy = os.path.join(base, "run.py")
    if os.path.exists(runpy):
        count += 1
        try:
            py_compile.compile(runpy, doraise=True)
        except py_compile.PyCompileError as e:
            errors.append((runpy, str(e)))
    return errors, count

def scan_imports():
    """Parse AST and check for import issues."""
    issues = []
    base = os.path.dirname(PROJECT_ROOT)
    src_dir = os.path.join(base, "src")
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    source = fh.read()
                tree = ast.parse(source, filename=path)
            except SyntaxError:
                continue  # Already caught by syntax scan
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name
                        try:
                            importlib.import_module(mod)
                        except ImportError as e:
                            issues.append((path, node.lineno, f"import {mod}", str(e)))
                        except Exception:
                            pass
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        try:
                            importlib.import_module(node.module)
                        except ImportError as e:
                            issues.append((path, node.lineno, f"from {node.module} import ...", str(e)))
                        except Exception:
                            pass
    return issues

def scan_common_issues():
    """Scan for common code issues."""
    issues = []
    base = os.path.dirname(PROJECT_ROOT)
    src_dir = os.path.join(base, "src")
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
            except Exception:
                continue
            
            for i, line in enumerate(lines, 1):
                stripped = line.rstrip()
                # Check for bare except
                if stripped.strip() == "except:":
                    issues.append((path, i, "bare except clause"))
                # Check for print statements in production code (not test files)
                if "test" not in path.lower() and "scratch" not in path.lower():
                    if stripped.strip().startswith("print(") and "Logger" not in stripped:
                        issues.append((path, i, f"print() instead of Logger: {stripped.strip()[:60]}"))
                # Check for TODO/FIXME/HACK
                for tag in ["TODO", "FIXME", "HACK", "XXX"]:
                    if tag in stripped and not stripped.strip().startswith("#"):
                        pass  # Only in comments
                    if tag in stripped:
                        issues.append((path, i, f"{tag} found: {stripped.strip()[:80]}"))
    return issues

def scan_tests():
    """Try to collect tests to see if there are errors."""
    base = os.path.dirname(PROJECT_ROOT)
    test_dir = os.path.join(base, "tests")
    if not os.path.isdir(test_dir):
        return []
    issues = []
    for root, dirs, files in os.walk(test_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as fh:
                        source = fh.read()
                    ast.parse(source, filename=path)
                except SyntaxError as e:
                    issues.append((path, str(e)))
    return issues

if __name__ == "__main__":
    print("=" * 70)
    print("LEAGUELOOP PROJECT SCAN")
    print("=" * 70)
    
    print("\n[1/3] Scanning for syntax errors...")
    syntax_errors, file_count = scan_syntax()
    if syntax_errors:
        for path, err in syntax_errors:
            print(f"  SYNTAX ERROR: {path}")
            print(f"    {err}")
    else:
        print(f"  OK - No syntax errors in {file_count} files")
    
    print("\n[2/3] Scanning for import issues...")
    import_issues = scan_imports()
    if import_issues:
        for path, line, imp, err in import_issues:
            print(f"  IMPORT ISSUE: {path}:{line}")
            print(f"    {imp}")
            print(f"    {err}")
    else:
        print("  OK - No import issues found")
    
    print("\n[3/3] Scanning for common code issues...")
    common_issues = scan_common_issues()
    if common_issues:
        # Group by type
        by_type = {}
        for path, line, issue in common_issues:
            key = issue.split(":")[0] if ":" in issue else issue
            by_type.setdefault(key, []).append((path, line, issue))
        for key, items in by_type.items():
            print(f"\n  [{key}] ({len(items)} occurrences):")
            for path, line, issue in items[:10]:  # Show max 10
                relpath = os.path.relpath(path, os.path.dirname(PROJECT_ROOT))
                print(f"    {relpath}:{line} - {issue}")
            if len(items) > 10:
                print(f"    ... and {len(items) - 10} more")
    else:
        print("  OK - No common issues found")
    
    print("\n" + "=" * 70)
    total_issues = len(syntax_errors) + len(import_issues)
    print(f"SUMMARY: {total_issues} critical issues, {len(common_issues)} warnings")
    print("=" * 70)
