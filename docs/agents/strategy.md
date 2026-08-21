# LeagueLoop Engineering Strategy

## Dual-Shell Transition & Verification Strategy
- Develop and maintain UI parity across CustomTkinter and PySide6 Qt desktop shells.
- Ensure all GUI components have headless offscreen mock/render tests to maintain fast test execution in CI/CD without X11 or display requirements.
- Use `ApplicationState` and `ShellViewModel` for reactive, decoupled presentation states rather than polling background services from widgets.

## Performance & Resource Strategy
- Utilize $O(1)$ online algorithms (`RunningStats`, `RunningPercentile`) for high-frequency telemetry.
- Pool HTTP connections and maintain shared keep-alive adapters via `http_session_factory.py`.
- Enforce bounded thread pools and interruptible `Event.wait(timeout)` loops to guarantee responsive, instantaneous application shutdowns.
