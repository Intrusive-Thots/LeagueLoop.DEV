"""
Design token loader.

This was `test_tokens.py` sitting in the repo root, where `pytest.ini`
(`testpaths = tests`) never collected it — and it imported
`src.ui.theme.token_loader`, which cannot resolve under `pythonpath = src`.
A test that is never run and could not pass if it were is worse than no test:
it reads as coverage.
"""
import unittest

import sys

from ui.theme.token_loader import TOKENS, DesignTokens, _intern_tokens


class InternTokensTests(unittest.TestCase):
    def test_intern_dict_string_keys(self):
        input_data = {"key1": "val1", "key2": {"nested_key": "nested_val"}}
        result = _intern_tokens(input_data)

        self.assertEqual(result, input_data)

        # Check interning
        # Since we use literal strings in code, they are often interned.
        # But let's check that the output values are interned strings.
        self.assertTrue(result["key1"] is sys.intern("val1"))
        self.assertTrue(list(result.keys())[0] is sys.intern("key1"))

    def test_intern_dict_non_string_keys(self):
        # We separate tests for 1 and True, because in Python True == 1 and hash(True) == hash(1)
        # thus they overlap if both are used as keys in the same dict
        input_data = {1: "val", None: "none_val", False: "bool_val"}
        result = _intern_tokens(input_data)

        self.assertEqual(result, input_data)
        self.assertTrue(1 in result)
        self.assertTrue(result[1] is sys.intern("val"))

    def test_intern_list(self):
        input_data = ["val1", "val2", {"key": "val3"}]
        result = _intern_tokens(input_data)

        self.assertEqual(result, input_data)
        self.assertTrue(result[0] is sys.intern("val1"))
        self.assertTrue(result[2]["key"] is sys.intern("val3"))

    def test_intern_string(self):
        input_data = "hello world"
        result = _intern_tokens(input_data)
        self.assertTrue(result is sys.intern("hello world"))

    def test_intern_unsupported_types(self):
        for val in [1, 1.5, True, None, object()]:
            self.assertIs(_intern_tokens(val), val)


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


if __name__ == "__main__":
    unittest.main()
