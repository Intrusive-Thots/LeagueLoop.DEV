"""
`get_winrate()` returns None when nothing was measured.

It used to return a fabricated 50.0 for every champion. Removing that was
right, but the CustomTkinter shell still compared the result to a number —
and both sites sit inside Tk callbacks, where the TypeError goes to a
traceback nobody reads. A real session produced 233 of them: 155 from the
priority-grid tooltip on every hover, 78 from the lobby stats panel, which
silently rendered nothing every time.

These pin the contract at both ends: the scraper may answer None, and no
caller may compare it without checking.
"""
import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


class ContractTests(unittest.TestCase):
    def test_an_unmeasured_winrate_is_none(self):
        from services.stats_scraper import StatsScraper

        self.assertIsNone(
            StatsScraper(mode="ARAM", fetch_live=False).get_winrate("Ahri")
        )


class CallerTests(unittest.TestCase):
    """Every caller must handle None before comparing or formatting."""

    def _callers(self):
        found = []
        for path in SRC.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "get_winrate":
                    found.append((path, node.lineno))
        return found

    def test_there_are_callers_to_check(self):
        self.assertTrue(self._callers(), "no get_winrate callers found at all")

    def test_no_caller_compares_the_result_without_a_none_check(self):
        offenders = []
        for path, lineno in self._callers():
            body = path.read_text(encoding="utf-8-sig")
            lines = body.splitlines()
            # The assignment target, then the next few lines that use it.
            window = "\n".join(lines[lineno - 1:lineno + 12])
            target = None
            try:
                stmt = ast.parse(lines[lineno - 1].strip()).body[0]
                if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name):
                    target = stmt.targets[0].id
            except (SyntaxError, IndexError):
                pass
            if target is None:
                continue
            compares = any(
                op in window for op in (
                    f"{target} >", f"{target} <", f"{target} >=", f"{target} <=",
                )
            )
            guarded = (
                f"{target} is None" in window
                or f"{target} is not None" in window
                or f"{target} or " in window
            )
            if compares and not guarded:
                offenders.append(f"{path.relative_to(SRC.parent)}:{lineno} ({target})")
        self.assertEqual(
            offenders, [],
            "These compare a winrate that may be None:\n" + "\n".join(offenders),
        )


class RenderTests(unittest.TestCase):
    """The tooltip must say something honest rather than formatting None."""

    def test_the_tooltip_has_a_not_measured_branch(self):
        body = (SRC / "ui" / "components" / "priority_grid.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("winrate is None", body)
        self.assertIn("not measured", body)
        # The label must render the pre-computed text, not format the raw
        # value at the call site where None would blow up.
        self.assertIn("text=wr_text", body)


if __name__ == "__main__":
    unittest.main()
