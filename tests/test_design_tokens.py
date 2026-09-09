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

    def test_intern_tokens(self):
        # String interning
        # Using join prevents compile-time constant folding string interning
        s1 = "".join(["some_random_string_", "constructed"])
        s2 = "some_random_string_constructed"
        self.assertIsNot(s1, s2)

        interned_s1 = _intern_tokens(s1)
        interned_s2 = _intern_tokens(s2)
        self.assertIs(interned_s1, interned_s2)

        # List interning
        lst = [s1, s2, 123]
        interned_lst = _intern_tokens(lst)
        self.assertEqual(interned_lst, [s1, s2, 123])
        self.assertIs(interned_lst[0], interned_lst[1])

        # Dictionary interning
        d = {s1: s2, 1: 2}
        interned_d = _intern_tokens(d)
        self.assertEqual(interned_d, {s1: s2, 1: 2})
        keys = list(interned_d.keys())
        values = list(interned_d.values())

        # In dictionaries order is preserved (for Python 3.7+),
        # so s1 is at index 0, 1 is at index 1.
        self.assertIs(keys[0], values[0])
        self.assertEqual(keys[1], 1)
        self.assertEqual(values[1], 2)

        # Fallback/Error path (unsupported types return unmodified)
        sentinel = object()
        self.assertIs(_intern_tokens(sentinel), sentinel)
        self.assertIs(_intern_tokens(None), None)
        self.assertIs(_intern_tokens(42), 42)


if __name__ == "__main__":
    unittest.main()
