"""A new League session (restart / account switch) must drop the old one's UI state."""
import sys
import threading
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT, _ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.test_ui_components import DummyWidget, mock_ctk, mock_tk, _purge_ui_modules


class SessionKeyTests(unittest.TestCase):
    def test_reconnect_changes_key(self):
        from services.lcu_session import lcu_session_key
        self.assertNotEqual(lcu_session_key(True, 1), lcu_session_key(True, 2))
        self.assertEqual(lcu_session_key(True, 3), lcu_session_key(True, 3))
        self.assertEqual(lcu_session_key(False, 5), lcu_session_key(False, 6))
        self.assertEqual(lcu_session_key(True, MagicMock()), (True, None))


def _lcu(port=1111, token="t-old", pid=10):
    from services.api_handler import LCUClient
    from core.state import ConnectionStateEnum
    c = object.__new__(LCUClient)
    c._lock = threading.RLock()
    c.is_connected = True
    c.port, c.auth_token, c._client_pid = port, token, pid
    c._connection_state = ConnectionStateEnum.CONNECTED
    c._last_scan_time = 99.0
    c._backoff = 8.0
    return c


class CheckClientChangedTests(unittest.TestCase):
    def _run(self, c, league):
        with patch("services.api_handler.scan_clients", return_value={"league": league}), \
                patch("core.events.EventBus.emit") as emit:
            changed = c.check_client_changed()
        return changed, emit

    def test_same_client_keeps_connection(self):
        c = _lcu()
        changed, emit = self._run(c, {"connected": True, "port": 1111, "token": "t-old", "pid": 10})
        self.assertFalse(changed)
        self.assertTrue(c.is_connected)
        emit.assert_not_called()

    def test_restarted_client_drops_connection(self):
        c = _lcu()
        changed, emit = self._run(c, {"connected": True, "port": 2222, "token": "t-new", "pid": 11})
        self.assertTrue(changed)
        self.assertFalse(c.is_connected)
        self.assertEqual(c._last_scan_time, 0.0)
        emit.assert_called_once_with("lcu_connected", False)

    def test_new_pid_alone_counts(self):
        c = _lcu()
        changed, _ = self._run(c, {"connected": True, "port": 1111, "token": "t-old", "pid": 99})
        self.assertTrue(changed)

    def test_not_connected_or_no_client_is_noop(self):
        c = _lcu()
        c.is_connected = False
        self.assertFalse(self._run(c, {"connected": True, "port": 2, "token": "x", "pid": 1})[0])
        c = _lcu()
        self.assertFalse(self._run(c, {"connected": False})[0])
        self.assertTrue(c.is_connected)


class ClientStateGenerationTests(unittest.TestCase):
    def test_new_generation_resyncs_and_clears_summoner(self):
        from services.client_state_service import ClientStateService
        lcu = SimpleNamespace(is_connected=True, connection_generation=1)
        state = MagicMock()
        svc = ClientStateService(lcu, state)
        svc._notice_new_session()
        state.update_client.assert_not_called()
        svc._summoner_loaded = True
        svc._last_phase = "Lobby"
        svc._notice_new_session()  # same generation: nothing
        self.assertTrue(svc._summoner_loaded)
        lcu.connection_generation = 2
        svc._notice_new_session()
        self.assertFalse(svc._summoner_loaded)
        self.assertIsNone(svc._last_phase)
        kwargs = state.update_client.call_args.kwargs
        self.assertIsNone(kwargs["puuid"])
        self.assertIsNone(kwargs["summoner_name"])

    def test_non_int_generation_ignored(self):
        from services.client_state_service import ClientStateService
        svc = ClientStateService(MagicMock(), MagicMock())
        svc._summoner_loaded = True
        svc._notice_new_session()
        svc._notice_new_session()
        self.assertTrue(svc._summoner_loaded)


class AutoLoginGuardTests(unittest.TestCase):
    def _am(self, idx=0, rc=None):
        from services.account_manager import AccountManager
        am = object.__new__(AccountManager)
        am.riot_client = rc
        am.get_default_account_index = lambda: idx
        return am

    def _rc(self, running=True, connects=True, signed=True):
        rc = MagicMock()
        rc.is_riot_client_running.return_value = running
        rc.connect.return_value = connects
        rc.is_signed_in.return_value = signed
        return rc

    def test_no_default(self):
        self.assertEqual(self._am(idx=-1, rc=self._rc()).should_auto_login_default()[0], False)

    def test_signed_in_is_left_alone(self):
        ok, why = self._am(rc=self._rc()).should_auto_login_default()
        self.assertFalse(ok)
        self.assertIn("already signed in", why)

    def test_unreadable_is_left_alone(self):
        rc = self._rc()
        rc.connect.side_effect = RuntimeError("boom")
        self.assertFalse(self._am(rc=rc).should_auto_login_default()[0])

    def test_not_running_or_signed_out_logs_in(self):
        self.assertTrue(self._am(rc=self._rc(running=False)).should_auto_login_default()[0])
        self.assertTrue(self._am(rc=self._rc(signed=False)).should_auto_login_default()[0])


class _Res:
    def __init__(self, code, data=None):
        self.status_code, self._d = code, data

    def json(self):
        return self._d


class FriendListResetTests(unittest.TestCase):
    def setUp(self):
        _purge_ui_modules()
        self._p = patch.dict(sys.modules, {"customtkinter": mock_ctk, "tkinter": mock_tk})
        self._p.start()
        self.addCleanup(self._p.stop)
        self.addCleanup(_purge_ui_modules)

    def _fl(self, responses):
        with patch("ui.components.factory.make_card") as mk, \
                patch("ui.components.friend_list.EventBus"):
            card = DummyWidget()
            card._toggle_controller = MagicMock(is_expanded=True)
            card._header = DummyWidget()
            mk.return_value = card
            from ui.components.friend_list import FriendPriorityList
            cfg = MagicMock()
            cfg.get.return_value = []
            lcu = MagicMock()
            lcu.request.side_effect = list(responses)
            fl = FriendPriorityList(DummyWidget(), config=cfg, lcu=lcu)
        fl.winfo_exists = lambda: True
        fl._render_list = MagicMock()
        fl._process_friends = MagicMock()
        fl.after = lambda ms, cb: cb()  # run retries immediately
        return fl, lcu

    def _inline_threads(self):
        class T:
            def __init__(self, target=None, daemon=None, **kw):
                self._t = target

            def start(self):
                self._t()
        return patch("ui.components.friend_list.threading.Thread", T)

    def test_reset_clears_and_refetches_until_loaded(self):
        fl, lcu = self._fl([_Res(404), _Res(503), _Res(200, [{"puuid": "a"}])])
        fl._friends_data = [{"puuid": "old"}]
        fl._last_render_sig = ("x",)
        with self._inline_threads():
            fl.reset_for_new_session(fetch=True, attempts=5, delay_ms=1)
        self.assertEqual(fl._friends_data, [])
        self.assertIsNone(fl._last_render_sig)
        fl._render_list.assert_called()
        self.assertEqual(lcu.request.call_count, 3)
        fl._process_friends.assert_called_once_with([{"puuid": "a"}])

    def test_gives_up_after_attempts(self):
        fl, lcu = self._fl([_Res(404)] * 10)
        with self._inline_threads():
            fl.reset_for_new_session(fetch=True, attempts=3, delay_ms=1)
        self.assertEqual(lcu.request.call_count, 3)
        fl._process_friends.assert_not_called()

    def test_offline_reset_does_not_fetch(self):
        fl, lcu = self._fl([])
        fl.reset_for_new_session(fetch=False)
        lcu.request.assert_not_called()

    def test_stale_epoch_dropped(self):
        fl, lcu = self._fl([_Res(200, [{"puuid": "old"}])])
        fl._session_epoch = 5
        with self._inline_threads():
            fl._fetch_until_loaded(4, 3, 1)
        lcu.request.assert_not_called()


class SidebarResetTests(unittest.TestCase):
    def setUp(self):
        _purge_ui_modules()
        self._p = patch.dict(sys.modules, {"customtkinter": mock_ctk, "tkinter": mock_tk})
        self._p.start()
        self.addCleanup(self._p.stop)
        self.addCleanup(_purge_ui_modules)

    def _fake(self, connected):
        return SimpleNamespace(
            winfo_exists=lambda: True,
            lcu=SimpleNamespace(is_connected=connected),
            master=None,
            _last_ui_phase="None",
            _current_game_phase="Lobby",
            _stop_local_queue_timer=MagicMock(),
            _set_header_state=MagicMock(),
            friend_list=MagicMock(),
            reset_client_scope=MagicMock(),
        )

    def test_reset_connected_sets_idle_and_refetches(self):
        from ui.app_sidebar import SidebarWidget as AppSidebar
        s = self._fake(True)
        AppSidebar.reset_client_scope(s)
        self.assertIsNone(s._last_ui_phase)
        self.assertEqual(s._current_game_phase, "None")
        s._set_header_state.assert_called_once_with("idle")
        s.friend_list.reset_for_new_session.assert_called_once_with(fetch=True)

    def test_reset_offline(self):
        from ui.app_sidebar import SidebarWidget as AppSidebar
        s = self._fake(False)
        AppSidebar.reset_client_scope(s)
        s._set_header_state.assert_called_once_with("offline")
        s.friend_list.reset_for_new_session.assert_called_once_with(fetch=False)

    def test_failed_switch_keeps_view(self):
        from ui.app_sidebar import SidebarWidget as AppSidebar
        s = self._fake(True)
        with patch("ui.app_sidebar.EventBus") as eb:
            AppSidebar._on_account_switch_finished(s, SimpleNamespace(ok=False))
            eb.invoke_thread_safe.assert_not_called()
            AppSidebar._on_account_switch_finished(s, SimpleNamespace(ok=True))
            eb.invoke_thread_safe.assert_called_once()


class ConnectionLoopSourceTests(unittest.TestCase):
    def test_loop_checks_client_and_tracks_generation(self):
        src = (_ROOT / "src" / "core" / "main.py").read_text(encoding="utf-8")
        loop = src[src.index("last_key = None"):]
        loop = loop[: loop.index("time.sleep")]
        self.assertIn("check_client_changed", loop)
        self.assertIn("connection_generation", loop)
        self.assertLess(loop.index("check_client_changed"), loop.index("self.lcu.connect("))


if __name__ == "__main__":
    unittest.main()
