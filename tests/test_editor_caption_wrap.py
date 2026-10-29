"""Caption balancing helper used by the automation editor (#44)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ui.components.automation_editor import _wrapped_lines  # noqa: E402


def _measure(s):
    return len(s) * 10  # 10px per char, deterministic


def test_fits_on_one_line():
    assert _wrapped_lines("short text", _measure, 200) == 1


def test_greedy_wrap_counts_lines():
    # "aaaa bbbb" = 90px, so at 100px "cccc" spills to line 2
    assert _wrapped_lines("aaaa bbbb cccc", _measure, 100) == 2
    assert _wrapped_lines("aaaa bbbb cccc", _measure, 40) == 3


def test_overlong_word_never_loops():
    assert _wrapped_lines("x" * 50, _measure, 100) == 1
