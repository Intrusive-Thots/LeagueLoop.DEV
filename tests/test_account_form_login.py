"""
RiotFormFiller against a fake desktop: focus is checked before every key,
typing stops the instant focus leaves the Riot Client, retries return to the
USERNAME box, and the password never reaches a log line.
"""
import unittest
from unittest.mock import patch

from services.accounts.form_login import (
    Desktop, FillStatus, FormFields, RiotFormFiller,
)

PW = "pä$$ wörd!😀"


class FakeDesktop(Desktop):
    def __init__(self, window=7, front=True, steal_after=None, steal_times=1,
                 uia=False):
        self.window = window
        self.front = front
        self.steal_after = steal_after      # steal focus after N chars typed
        self.steal_times = steal_times
        self.uia = uia
        self.log = []                       # ("key", k) / ("char", c) / ("focus", f)
        self.chars = 0
        self.fronted = 0

    def available(self):
        return True

    def find_riot_window(self):
        return self.window

    def bring_to_front(self, hwnd):
        self.fronted += 1
        if self.front:
            self._front = True
        return self.front

    def is_foreground(self, hwnd):
        return getattr(self, "_front", False)

    def press(self, key):
        self.log.append(("key", key))

    def type_char(self, ch):
        self.log.append(("char", ch))
        self.chars += 1
        if self.steal_after is not None and self.steal_times > 0 and self.chars >= self.steal_after:
            self.steal_times -= 1
            self.steal_after = None
            self._front = False             # another window grabs focus

    def find_fields(self, hwnd):
        return FormFields("U", "P") if self.uia else None

    def focus_field(self, field):
        self.log.append(("focus", field))
        return True

    def typed(self):
        return "".join(c for k, c in self.log if k == "char")


def filler(desktop, **kw):
    kw.setdefault("sleep", lambda s: None)
    return RiotFormFiller(desktop, form_settle_s=0, key_interval_s=0, step_pause_s=0, **kw)


class FormFillTests(unittest.TestCase):
    def test_types_username_tab_password_enter(self):
        d = FakeDesktop()
        r = filler(d).fill_and_submit("Smurf_User", PW)
        self.assertTrue(r.ok)
        self.assertEqual(d.typed(), "Smurf_User" + PW)
        keys = [v for k, v in d.log if k == "key"]
        self.assertEqual(keys, ["ctrl+a", "backspace", "tab", "ctrl+a", "backspace", "enter"])
        self.assertFalse(r.targeted)

    def test_with_ui_automation_the_fields_are_focused_by_name(self):
        d = FakeDesktop(uia=True)
        r = filler(d).fill_and_submit("u", "p")
        self.assertTrue(r.ok and r.targeted)
        self.assertEqual([v for k, v in d.log if k == "focus"], ["U", "P"])
        self.assertNotIn(("key", "tab"), d.log)

    def test_no_window(self):
        r = filler(FakeDesktop(window=0), window_timeout_s=0).fill_and_submit("u", "p")
        self.assertIs(r.status, FillStatus.WINDOW_NOT_FOUND)

    def test_cannot_bring_to_front_types_nothing(self):
        d = FakeDesktop(front=False)
        r = filler(d).fill_and_submit("u", PW)
        self.assertIs(r.status, FillStatus.FOCUS_FAILED)
        self.assertEqual(d.log, [])
        self.assertEqual(d.fronted, 3)

    def test_focus_stolen_mid_password_stops_at_once_and_retries_from_username(self):
        d = FakeDesktop(steal_after=len("user") + 3)  # 3 chars into the password
        r = filler(d).fill_and_submit("user", PW)
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)
        first, second = d.typed()[:7], d.typed()[7:]
        self.assertEqual(first, "user" + PW[:3])      # not one key more
        self.assertEqual(second, "user" + PW)
        # Retry walked back from PASSWORD to USERNAME before typing.
        retry_keys = [v for k, v in d.log[d.log.index(("char", PW[2])) + 1:] if k == "key"]
        self.assertEqual(retry_keys[:3], ["shift+tab", "ctrl+a", "backspace"])

    def test_focus_lost_every_time_gives_up(self):
        d = FakeDesktop(steal_after=1, steal_times=99)
        original = d.type_char

        def always_steal(ch):
            original(ch)
            d._front = False
        d.type_char = always_steal
        r = filler(d).fill_and_submit("user", PW)
        self.assertIs(r.status, FillStatus.FOCUS_LOST)
        self.assertNotIn(PW[0], d.typed().replace("u", ""))  # never reached the password

    def test_password_never_logged(self):
        logged = []
        grab = lambda *a, **k: logged.append(repr(a) + repr(k))
        with patch("utils.logger.Logger.info", side_effect=grab), \
             patch("utils.logger.Logger.warning", side_effect=grab), \
             patch("utils.logger.Logger.debug", side_effect=grab):
            filler(FakeDesktop(steal_after=6)).fill_and_submit("user", PW)
        self.assertNotIn(PW, " ".join(logged))
        self.assertNotIn("wörd", " ".join(logged))

    def test_non_windows_is_unavailable(self):
        r = RiotFormFiller(Desktop()).fill_and_submit("u", "p")
        self.assertIs(r.status, FillStatus.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()


class _El:
    def __init__(self, name="", aid=""):
        self.element_info = type("I", (), {"name": name, "automation_id": aid})()


class _Win:
    def __init__(self, edits, all_=None):
        self.edits, self.all = edits, all_ if all_ is not None else edits

    def descendants(self, control_type=None):
        return self.edits if control_type == "Edit" else self.all


def _stub(win):
    from services.accounts.form_login import Win32Desktop
    import types
    return types.SimpleNamespace(_uia_window=lambda h: win, _name=Win32Desktop._name)


class UiaBlindnessTests(unittest.TestCase):
    """The live Riot Client exposes only nine empty panes to UI Automation.
    That must read as "can't tell", never as "form not there" or "no captcha"."""

    def test_no_visible_fields_means_unknown_not_missing(self):
        from services.accounts.form_login import Win32Desktop
        blind = _Win([], [_El(), _El()])
        self.assertIsNone(Win32Desktop.find_fields(_stub(blind), 1))

    def test_form_ready_is_unknown_when_uia_is_blind(self):
        class Blind(FakeDesktop):
            def find_fields(self, hwnd):
                return None
        self.assertIsNone(RiotFormFiller(Blind()).form_ready(1))

    def test_both_named_fields_are_targeted(self):
        from services.accounts.form_login import Win32Desktop
        u, p = _El("USERNAME"), _El("PASSWORD")
        f = Win32Desktop.find_fields(_stub(_Win([u, p])), 1)
        self.assertIs(f.username, u)
        self.assertIs(f.password, p)

    def test_one_field_only_falls_back_to_autofocus(self):
        from services.accounts.form_login import Win32Desktop
        self.assertIsNone(Win32Desktop.find_fields(_stub(_Win([_El("PASSWORD")])), 1))

    def test_captcha_unknown_when_only_empty_panes(self):
        from services.accounts.form_login import Win32Desktop
        self.assertIsNone(Win32Desktop.captcha_visible(_stub(_Win([], [_El()] * 9)), 1))

    def test_captcha_seen_and_ruled_out(self):
        from services.accounts.form_login import Win32Desktop
        self.assertTrue(Win32Desktop.captcha_visible(_stub(_Win([], [_El("hCaptcha challenge")])), 1))
        self.assertFalse(Win32Desktop.captcha_visible(_stub(_Win([], [_El("Sign in")])), 1))
