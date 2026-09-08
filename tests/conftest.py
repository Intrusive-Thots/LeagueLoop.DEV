"""
Shared test setup — and a guard against the suite hanging.

`pytest` reporting "340 passed" and then never returning to the prompt is the
worst failure a suite can have: there is no failing test to look at, and the
cause is invisible. It happened here because one test constructed the whole
application, which on Windows starts `keyboard`'s listener on a **non-daemon**
thread. Linux failed that silently, so the suite looked fine.

The hook below names any non-daemon thread still running when the session
ends. It cannot stop the hang, but it turns "stuck with no output" into a
line saying exactly what is holding the interpreter open.
"""
import os
import threading

# Every UI test runs headless. Set before Qt/Tk are imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# pystray has no usable backend in CI and raises at import without this.
os.environ.setdefault("PYSTRAY_BACKEND", "dummy")


def pytest_sessionfinish(session, exitstatus):
    """Report threads that will keep the interpreter alive after the run."""
    lingering = [
        thread for thread in threading.enumerate()
        if thread is not threading.current_thread()
        and thread.is_alive()
        and not thread.daemon
    ]
    if not lingering:
        return

    writer = getattr(session.config, "pluginmanager", None)
    report = (
        "\n"
        + "=" * 70 + "\n"
        "WARNING: {} non-daemon thread(s) are still running.\n"
        "pytest has finished, but Python cannot exit until these stop — the\n"
        "terminal will appear to hang. Named here so the cause is visible:\n"
        "\n".format(len(lingering))
        + "".join("  - {}\n".format(t.name) for t in lingering)
        + "\nUsually this means a test built something that starts a listener,\n"
        "a server or a global hook. See SuiteHygieneTests in\n"
        "tests/test_container_contract.py.\n"
        + "=" * 70 + "\n"
    )
    try:
        session.config.get_terminal_writer().write(report)
    except Exception:
        print(report)
