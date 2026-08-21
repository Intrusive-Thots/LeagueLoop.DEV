
## Sun Apr 26 21:37:11 UTC 2026 - Test Coverage and Stability
- **What was changed**: Fixed a failing unit test (`test_inprogress_always_minimizes`) in `tests/test_automation.py` by properly mocking `_is_first_tick` and `_is_game_running`.
- **Verification**: Ran the test suite headlessly via xvfb-run. Coverage analysis showed 34% overall coverage.
- **Learning**: Uninitialized state and missing mocks for secondary internal behaviors (like game process checking) can easily cause race conditions or assertion failures in the automation loop tests.
- **Action**: Removed the `.coverage` auto-generated file that was mistakenly staged.
