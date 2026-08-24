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
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

SKIP_FILES = {"logger.py", "session_log.py"}

#: Exception types whose `pass` is a deliberate, meaningful no-op.
BENIGN = {"ImportError", "ModuleNotFoundError", "AttributeError", "KeyError",
          "StopIteration", "IndexError", "FileNotFoundError", "OSError",
          "ValueError", "TypeError", "RuntimeError"}


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("paths", nargs="*", default=["src"])
    args = parser.parse_args()

    total = 0
    for root in args.paths:
        for path in sorted(pathlib.Path(root).rglob("*.py")):
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
