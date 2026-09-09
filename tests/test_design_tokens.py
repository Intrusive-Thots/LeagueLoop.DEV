"""
Design token loader.

This was `test_tokens.py` sitting in the repo root, where `pytest.ini`
(`testpaths = tests`) never collected it — and it imported
`src.ui.theme.token_loader`, which cannot resolve under `pythonpath = src`.
A test that is never run and could not pass if it were is worse than no test:
it reads as coverage.
"""
import unittest

from ui.theme.token_loader import TOKENS, DesignTokens, _intern_tokens


class DesignTokenTests(unittest.TestCase):
    def test_spacing_scale_is_loaded(self):
        spacing = TOKENS.get("spacing")
        self.assertIsInstance(spacing, dict)
        for step in ("xs", "sm", "md", "lg", "xl"):
            self.assertIn(step, spacing)

    def test_dotted_lookup(self):
        self.assertEqual(TOKENS.get("spacing.md"), TOKENS.get("spacing")["md"])

    def test_missing_key_returns_the_default(self):
        sentinel = object()
        self.assertIs(TOKENS.get("nope.not.here", default=sentinel), sentinel)

    def test_a_positional_default_is_swallowed_by_a_heuristic(self):
        """
        Documenting a trap rather than asserting it is correct.

        `get(*keys, default=None)` inspects the *last* positional argument and
        promotes it to the default if it looks like one — a colour, "bold",
        "center", or any number. So `get("spacing", "md")` reads a nested key,
        but `get("colors", "bold")` silently becomes a lookup of "colors" with
        "bold" as the fallback. Callers cannot tell which they wrote.
        """
        self.assertEqual(TOKENS.get("nope", "bold"), "bold")

    def test_loader_is_constructible(self):
        self.assertIsInstance(TOKENS, DesignTokens)

    def test_intern_tokens_edge_cases(self):
        # Dict with integer keys and float values
        obj = {1: 1.5, 2: None, "str_key": "str_val"}
        interned = _intern_tokens(obj)
        self.assertEqual(interned[1], 1.5)
        self.assertIsNone(interned[2])
        self.assertEqual(interned["str_key"], "str_val")

        # Lists with mixed types
        lst = [1, "test", None, [2, "nested"]]
        interned_lst = _intern_tokens(lst)
        self.assertEqual(interned_lst[0], 1)
        self.assertEqual(interned_lst[1], "test")
        self.assertIsNone(interned_lst[2])
        self.assertEqual(interned_lst[3][0], 2)
        self.assertEqual(interned_lst[3][1], "nested")

        # Raw types
        self.assertEqual(_intern_tokens(42), 42)
        self.assertEqual(_intern_tokens(42.5), 42.5)
        self.assertIsNone(_intern_tokens(None))

        # Test interning behavior (not easily testable with assertIs since same string literal might be interned automatically,
        # but we can verify it doesn't break strings)
        self.assertEqual(_intern_tokens("a_long_string_that_is_not_interned_yet_12345"), "a_long_string_that_is_not_interned_yet_12345")


if __name__ == "__main__":
    unittest.main()
