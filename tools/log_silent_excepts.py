"""
Turn `except Exception: pass` into a logged debug record.

A swallowed exception is the single most common reason this app appears to
work while doing nothing. This rewrites the bodies that are exactly `pass`
so the failure at least reaches `debug.log` with a traceback, naming the
function it happened in.

It deliberately does NOT change control flow: the exception is still
swallowed. Turning a swallow into a raise is a judgement call per site; this
just stops them being invisible.

Usage:
    python tools/log_silent_excepts.py            # report only
    python tools/log_silent_excepts.py --write    # rewrite in place
    python tools/log_silent_excepts.py --json     # output JSON audit
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
from typing import Dict, Any, List, Optional, Union

SKIP_FILES = {"logger.py", "session_log.py"}

#: Exception types whose `pass` is a deliberate, meaningful no-op.
BENIGN = {"ImportError", "ModuleNotFoundError", "AttributeError", "KeyError",
          "StopIteration", "IndexError", "FileNotFoundError", "OSError",
          "ValueError", "TypeError", "RuntimeError"}

DEFAULT_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"


def _handler_type_names(handler: ast.ExceptHandler):
    node = handler.type
    if node is None:
        return {"bare"}
    names = []
    if isinstance(node, ast.Tuple):
        parts = node.elts
    else:
        parts = [node]
    for part in parts:
        if isinstance(part, ast.Name):
            names.append(part.id)
        elif isinstance(part, ast.Attribute):
            names.append(part.attr)
    return set(names)


def _enclosing(tree, lineno):
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.lineno <= lineno <= (node.end_lineno or node.lineno):
                if best is None or node.lineno > best.lineno:
                    best = node
    return best.name if best else "<module>"


def sites(path: pathlib.Path):
    src = path.read_text(encoding="utf-8-sig")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src, []
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        body = [
            b for b in node.body
            if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant)
                    and isinstance(b.value.value, str))
        ]
        if len(body) != 1 or not isinstance(body[0], ast.Pass):
            continue
        types = _handler_type_names(node)
        # Only the broad catches. A narrow `except ImportError: pass` around an
        # optional dependency is a real decision, not an oversight.
        if not (types & {"Exception", "BaseException", "bare"}):
            continue
        found.append({
            "line": body[0].lineno,
            "col": body[0].col_offset,
            "func": _enclosing(tree, node.lineno),
            "handler_line": node.lineno,
            "name": node.name,
        })
    return src, found


def rewrite(path: pathlib.Path, tag: str) -> int:
    src, found = sites(path)
    if not found:
        return 0
    lines = src.splitlines(keepends=True)
    for site in sorted(found, key=lambda s: s["line"], reverse=True):
        idx = site["line"] - 1
        line = lines[idx]
        if line.strip() != "pass":
            continue
        indent = " " * site["col"]
        var = site["name"] or "exc"
        # Give the handler a name if it does not have one.
        if not site["name"]:
            h = site["handler_line"] - 1
            header = lines[h]
            new_header = re.sub(
                r"except\s+(Exception|BaseException)\s*:",
                r"except \1 as exc:",
                header,
                count=1,
            )
            if new_header == header and header.strip().startswith("except:"):
                new_header = header.replace("except:", "except Exception as exc:", 1)
            lines[h] = new_header
        func = site["func"]
        lines[idx] = (
            f'{indent}Logger.debug("{tag}", "{func} suppressed an error", exc={var})\n'
        )
    out = "".join(lines)
    if "from utils.logger import Logger" not in out:
        # Insert after the last top-level import.
        tree = ast.parse(out)
        last = 0
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                last = node.end_lineno or node.lineno
        out_lines = out.splitlines(keepends=True)
        out_lines.insert(last, "from utils.logger import Logger\n")
        out = "".join(out_lines)
    path.write_text(out, encoding="utf-8")
    return len(found)


def scan_silent_handlers(
    paths: Optional[List[Union[str, pathlib.Path]]] = None,
    skip_files: Optional[set] = None,
) -> Dict[str, Any]:
    """Scans Python files for swallowed exception handlers (`except Exception: pass` or bare `except: pass`)."""
    if paths is None:
        paths = [DEFAULT_SRC if DEFAULT_SRC.exists() else "src"]
    if skip_files is None:
        skip_files = SKIP_FILES

    offending_files = []
    total_handlers = 0
    total_files_audited = 0

    for root in paths:
        root_path = pathlib.Path(root)
        if not root_path.exists():
            continue
        if root_path.is_file():
            py_files = [root_path] if root_path.suffix == ".py" else []
        else:
            py_files = sorted(root_path.rglob("*.py"))

        for path in py_files:
            if path.name in skip_files:
                continue
            total_files_audited += 1
            src, found = sites(path)
            if found:
                total_handlers += len(found)
                offending_files.append({
                    "file": str(path),
                    "count": len(found),
                    "sites": found,
                })

    status = "PASS" if total_handlers == 0 else "FAIL"
    msg = (
        "Zero silent exception handlers detected"
        if total_handlers == 0
        else f"{total_handlers} silent handler(s) detected across {len(offending_files)} file(s)"
    )

    return {
        "status": status,
        "silent_handlers_count": total_handlers,
        "files_audited": total_files_audited,
        "offending_files": offending_files,
        "message": msg,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit and rewrite silent exception handlers")
    parser.add_argument("--write", action="store_true", help="Rewrite silent pass handlers in-place with Logger.debug")
    parser.add_argument("--json", action="store_true", help="Output audit results in JSON format")
    parser.add_argument("paths", nargs="*", default=None, help="Target files or directories to audit")
    args = parser.parse_args(argv)

    target_paths = args.paths if args.paths else [str(DEFAULT_SRC) if DEFAULT_SRC.exists() else "src"]

    if args.json:
        res = scan_silent_handlers(paths=target_paths)
        print(json.dumps(res, indent=2))
        return 0 if res["status"] == "PASS" else 1

    total = 0
    for root in target_paths:
        root_path = pathlib.Path(root)
        if not root_path.exists():
            continue
        py_files = [root_path] if root_path.is_file() and root_path.suffix == ".py" else sorted(root_path.rglob("*.py"))
        for path in py_files:
            if path.name in SKIP_FILES:
                continue
            src, found = sites(path)
            if not found:
                continue
            total += len(found)
            tag = path.stem.replace("_", " ").title().replace(" ", "")
            if args.write:
                rewrite(path, tag)
                print(f"{len(found):3d}  rewrote {path}")
            else:
                for site in found:
                    print(f"{path}:{site['line']}  {site['func']}")
    print(f"\n{total} silent handler(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
