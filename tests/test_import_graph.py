"""
Every first-party module named in an `import` has to exist.

`src/services/client_window_tracker.py` was deleted on the belief that only the
removed Qt shell used it. `LeagueLoopApp.docking_loop` imported it too, from
inside the thread body, so the failure was a ModuleNotFoundError on a daemon
thread at startup: no dialog, no crash, nothing in the window except a
companion frozen at its opening size in the corner of the screen. The suite was
green throughout, because no test imports `core.main`.

A deferred import is exactly the kind that no test reaches, which is why this
check reads the source rather than importing it: it walks every `import` and
`from ... import` in `src/`, keeps the ones that name a first-party package,
and asserts the file is on disk.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

#: Top-level packages that live in `src/`. Anything else is third-party or
#: stdlib and is not this test's business.
FIRST_PARTY = {"core", "services", "ui", "utils"}


def _module_exists(dotted: str) -> bool:
    """True when `a.b.c` resolves to src/a/b/c.py or src/a/b/c/__init__.py."""
    base = SRC.joinpath(*dotted.split("."))
    if base.with_suffix(".py").is_file():
        return True
    if (base / "__init__.py").is_file():
        return True
    # A namespace package: a directory with modules but no __init__.py, which
    # `services/api` is.
    return base.is_dir()


def _resolve_relative(path: Path, level: int, module: str | None) -> str | None:
    """Turn `from .api_handler import X` inside src/services/ into services.api_handler."""
    package = path.parent.relative_to(SRC).parts
    if level > 1:
        package = package[: -(level - 1)] if level - 1 <= len(package) else ()
    parts = list(package) + ([module] if module else [])
    return ".".join(parts) if parts else None


class ImportGraphTests(unittest.TestCase):
    def test_every_first_party_import_resolves(self):
        missing = []
        for path in sorted(SRC.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                targets = []
                if isinstance(node, ast.Import):
                    targets = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        resolved = _resolve_relative(path, node.level, node.module)
                        targets = [resolved] if resolved else []
                    elif node.module:
                        targets = [node.module]

                for dotted in targets:
                    if not dotted:
                        continue
                    if dotted.split(".")[0] not in FIRST_PARTY:
                        continue
                    if _module_exists(dotted):
                        continue
                    # `from services.accounts import Vault` names a symbol, not
                    # a module; only complain when the parent is missing too.
                    parent = dotted.rsplit(".", 1)[0]
                    if "." in dotted and _module_exists(parent):
                        continue
                    missing.append(
                        "%s:%d imports '%s'"
                        % (path.relative_to(ROOT), node.lineno, dotted)
                    )

        self.assertEqual(
            sorted(set(missing)),
            [],
            "these name a first-party module that is not on disk, which is a "
            "ModuleNotFoundError the moment the line runs:\n"
            + "\n".join(sorted(set(missing))),
        )

    def test_the_docking_loop_can_reach_its_tracker(self):
        """The specific regression, named, so it cannot come back quietly.

        What is asserted here is the contract, not an outcome: `tick()` answers
        with a ClientWindow instead of raising. Asserting "nothing found" would
        be true on a build machine and false on the developer's, where the
        League Client is usually open -- a test that fails for the person best
        placed to run it is worse than no test.
        """
        from services.client_window_tracker import ClientWindow, ClientWindowTracker

        tracker = ClientWindowTracker()
        window = tracker.tick()
        self.assertIsInstance(window, ClientWindow)
        self.assertEqual(len(window.rect), 4)
        self.assertIsInstance(window.usable, bool)
        if not window.found:
            self.assertEqual(window.rect, (0, 0, 0, 0))
            self.assertFalse(window.usable)
        else:
            # A found window must describe itself consistently.
            self.assertTrue(window.hwnd)
            if window.usable:
                self.assertGreater(window.rect[2], 0)
                self.assertGreater(window.rect[3], 0)

        # Calling it repeatedly must stay stable -- the docking loop does this
        # twenty times a second.
        again = tracker.tick()
        self.assertEqual(again.found, window.found)


if __name__ == "__main__":
    unittest.main()
