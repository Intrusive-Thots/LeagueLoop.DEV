"""
One failed service must not stop the old shell from launching.

`ApplicationContainer.bootstrap()` is written to keep going when an optional
service fails — it logs "Service 'accounts' did not start, every feature that
needs it is unavailable for this run" and carries on. The UI did not honour
that: `AccountsTool.__init__` called `account_manager.get_accounts()`
unconditionally, so a `None` manager raised `AttributeError` out of
`setup_ui()` and **the whole application failed to launch**.

Reproduced by running the real shell with the account service unavailable.
On Windows the specific trigger (`win32crypt` missing) does not fire, but the
same path is taken whenever the manager cannot be built — a corrupt
`accounts.json`, a DPAPI failure, a permissions problem.

These tests need Tk, which the CustomTkinter shell is built on. They skip
where it is absent rather than failing, so the suite still runs anywhere.
"""
import os
import unittest

try:
    import tkinter  # noqa: F401
    import customtkinter  # noqa: F401
    HAVE_TK = True
except Exception:                       # pragma: no cover - environment
    HAVE_TK = False

os.environ.setdefault("PYSTRAY_BACKEND", "dummy")


@unittest.skipUnless(HAVE_TK, "CustomTkinter/Tk is not available here")
class AccountsPanelWithoutAService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import customtkinter as ctk

        try:
            cls.root = ctk.CTk()
        except Exception as exc:        # pragma: no cover - no display
            raise unittest.SkipTest("no display available: %s" % exc)
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def _tool(self, manager=None, reason=""):
        from ui.components.game_tools.accounts_tool import AccountsTool

        return AccountsTool(self.root, manager, unavailable_reason=reason)

    def test_the_panel_builds_with_no_account_manager(self):
        """The constructor is what took the app down."""
        tool = self._tool()
        self.assertFalse(tool.available)

    def test_it_says_why_rather_than_looking_empty(self):
        """"No accounts saved yet" invites you to add one, and Add would then
        fail. Unavailable is a different state from empty."""
        tool = self._tool(reason="The account service did not start: boom")
        self.assertIn("boom", tool.unavailable_reason)
        text = self._visible_text(tool)
        self.assertIn("unavailable", text.lower())
        self.assertIn("boom", text)

    def test_add_account_is_refused_instead_of_raising(self):
        tool = self._tool()
        tool._show_add_form()          # must not raise

    def test_expanding_the_section_does_not_start_a_doomed_thread(self):
        """`_toggle_collapse` starts detection on a background thread. With a
        None manager that raised where nobody could see it."""
        tool = self._tool()
        tool._detect_active()
        self.assertFalse(tool._detect_in_progress)

    def test_the_header_count_is_blank_not_broken(self):
        tool = self._tool()
        tool._update_header_count()
        self.assertEqual(tool.lbl_count.cget("text"), "")

    def test_a_working_manager_still_renders_accounts(self):
        """The guard must not change the normal path."""
        class Manager:
            def get_accounts(self):
                return [{"label": "Main", "username": "u", "password_enc": "x"}]

            def get_active_index(self):
                return 0

            def get_account_count(self):
                return 1

            def has_valid_credentials(self, _i):
                return True

            def detect_active_account(self):
                return None

        tool = self._tool(Manager())
        self.assertTrue(tool.available)
        self.assertIn("Main", self._visible_text(tool))

    def _visible_text(self, widget):
        """Every label's text in a widget subtree, joined."""
        found = []
        stack = [widget]
        while stack:
            current = stack.pop()
            try:
                stack.extend(current.winfo_children())
            except Exception:
                continue
            try:
                value = current.cget("text")
            except Exception:
                continue
            if isinstance(value, str) and value:
                found.append(value)
        return "\n".join(found)


class ContainerFailureReasonTests(unittest.TestCase):
    """The reason has to travel with the None, or the UI can only say
    "unavailable" — which tells the user nothing they can act on."""

    def test_a_failed_service_reports_a_usable_reason(self):
        from core.container import ApplicationContainer

        container = ApplicationContainer.__new__(ApplicationContainer)
        container.bootstrap_errors = [
            ("accounts", ModuleNotFoundError("No module named 'win32crypt'"))
        ]
        reason = container.failure_reason("accounts")
        self.assertIn("accounts", reason)
        self.assertIn("win32crypt", reason)

    def test_a_service_that_started_has_no_reason(self):
        from core.container import ApplicationContainer

        container = ApplicationContainer.__new__(ApplicationContainer)
        container.bootstrap_errors = []
        self.assertEqual(container.failure_reason("accounts"), "")

    def test_an_exception_with_no_message_still_names_its_type(self):
        from core.container import ApplicationContainer

        container = ApplicationContainer.__new__(ApplicationContainer)
        container.bootstrap_errors = [("accounts", RuntimeError())]
        self.assertIn("RuntimeError", container.failure_reason("accounts"))


@unittest.skipUnless(HAVE_TK, "core.main imports Tk at module scope")
class AutoLoginTests(unittest.TestCase):
    """`_auto_load_default_account` is scheduled with `after()` at startup, so
    it fires whatever happened during bootstrap."""

    def test_it_is_skipped_when_there_is_no_account_service(self):
        import inspect

        from core.main import LeagueLoopApp

        source = inspect.getsource(LeagueLoopApp._auto_load_default_account)
        self.assertIn("self.account_manager is None", source)
        guard = source.index("self.account_manager is None")
        use = source.index("get_default_account_index")
        self.assertLess(guard, use, "the guard runs after the call it guards")


if __name__ == "__main__":
    unittest.main()
