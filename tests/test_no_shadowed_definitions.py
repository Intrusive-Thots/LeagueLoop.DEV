"""A name defined twice in one scope is a bug the interpreter will not report.

`api_handler.LCUClient.get_http_retry_jitter_entropy_telemetry` was defined
twice, 83 lines apart. Python keeps the last definition, so the first was
unreachable — and it happened to contain a `NameError` (`wolfson_vii`,
`foster_wolfson_vii` and `n` were never assigned). That bug sat in the tree
undetected precisely *because* it was shadowed: nothing could call it, so
nothing could fail.

Shadowing hides the two mistakes that matter here. Either the later
definition silently replaced work someone meant to keep, or the earlier one
is dead weight nobody noticed. Both deserve a failing test rather than a
reader who happens to be paying attention.

This checks classes and modules across `src/`. It does not flag
`@property`/`@x.setter` pairs, `@typing.overload`, or definitions guarded by
`if`/`try` — those are all legitimate reasons for one name to appear twice.
"""

import ast
import collections
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _decorator_names(node):
    names = set()
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        name = getattr(target, "attr", None) or getattr(target, "id", None)
        if name:
            names.add(name)
    return names


def _duplicates_in_body(body):
    """Names defined more than once directly in one block.

    Only direct children count. A def inside an `if`, `try` or nested
    function is a deliberate conditional definition, not a shadow.
    """
    seen = collections.defaultdict(list)
    for item in body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        decorators = _decorator_names(item)
        # property setters/getters/deleters legitimately repeat a name, as
        # do typing.overload stubs.
        if decorators & {"setter", "getter", "deleter", "overload"}:
            continue
        seen[item.name].append(item.lineno)
    return {name: lines for name, lines in seen.items() if len(lines) > 1}


class NoShadowedDefinitionsTests(unittest.TestCase):

    def test_no_duplicate_definitions_in_src(self):
        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            except SyntaxError as exc:                # pragma: no cover
                self.fail("%s does not parse: %s" % (path, exc))

            scopes = [("module", tree.body)]
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    scopes.append((node.name, node.body))

            for scope_name, body in scopes:
                for name, lines in _duplicates_in_body(body).items():
                    offenders.append(
                        "%s: %s.%s defined at lines %s — only %d survives"
                        % (
                            path.relative_to(ROOT),
                            scope_name,
                            name,
                            lines,
                            lines[-1],
                        )
                    )

        self.assertEqual(
            offenders, [],
            "a later definition silently replaces an earlier one, so one of "
            "the two is dead and neither is reported: %s" % offenders,
        )


if __name__ == "__main__":
    unittest.main()
