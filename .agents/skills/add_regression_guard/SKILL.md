---
name: Add Regression Guard
description: Record a fixed bug class as a documented rule plus an automated guard test
---

# Add Regression Guard

Use this whenever a bug is fixed that has recurred before, or that a future
change could plausibly reintroduce. A guard is two parts: a **documented rule**
and an **automated test** that fails if the rule is violated.

## The two files

1. **`.agents/ARCHITECTURE_CONSTRAINTS.md`** — add a rule under "Regression
   Prevention Rules". Follow the existing house format (see THREAD-001,
   RIOT-ID-001, LCU-001, RENDER-001):

```markdown
### <TAG>-00N: <One-line imperative>
- **NEVER** <the specific dangerous thing>
- **ALWAYS** <the required correct thing>
- <why it breaks — the root cause, in one or two lines>
- **Files affected**: `file_a.py`, `file_b.py`
- **Regression test**: `test_regression_guards.py::<test_name>`
```
   Pick a stable tag prefix by domain (`THREAD`, `RIOT-ID`, `LCU`, `RENDER`,
   `ASSET`, ...) and the next number in that series.

2. **`tests/test_regression_guards.py`** — add a test that mechanically
   enforces the rule. These are static/heuristic checks over the source tree,
   not runtime tests. Helpers already present: `_python_files()` yields every
   `.py` under `src/`; `REPO_ROOT` / `SRC` are module constants.

## Pattern: forbid a token across the tree

```python
def test_no_blocking_sleep_in_handlers():
    """API-002: never time.sleep() inside a request handler."""
    handler = SRC / "services" / "local_api.py"
    text = handler.read_text(encoding="utf-8")
    assert "time.sleep(" not in text, "local_api handlers must not block"
```

## Pattern: require a safe construct where a dangerous one appears

Mirror `test_no_direct_qt_from_threads_pattern` — only fail when the dangerous
combo is present *without* the required mitigation:

```python
def test_batch_insert_suppresses_updates():
    """RENDER-001 heuristic."""
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "for " in text and ".addWidget(" in text and "setUpdatesEnabled(False)" not in text:
            # tighten this heuristic to the real risky files rather than flagging all
            ...
```

Keep heuristics narrow enough to avoid false positives — scope to specific
files when a tree-wide scan would be too noisy.

## Rules

- Every new rule in the doc **must** name a real `test_regression_guards.py`
  test, and that test must exist and pass.
- Guards should be cheap and deterministic (no LCU, no GUI, no network).
- Don't delete or weaken an existing guard to make a change pass — that defeats
  the purpose. Fix the code instead.

## Verify

- Run `pytest tests/test_regression_guards.py -v` — new test passes.
- Temporarily reintroduce the bug locally and confirm the test **fails**
  (proves the guard actually guards), then revert.
- Run the full suite (see `run_tests`).
