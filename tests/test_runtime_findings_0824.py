"""
The four defects the 2026-08-24 run actually produced.

Every test here corresponds to a line in `crash.log` or `error.log` from
version 2-08-129-0921 running against the real client, not to a guess about
what might go wrong.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class AssetCacheWriteTests(unittest.TestCase):
    """`[Errno 13] Permission denied: champion_X.png.tmp` and
    `[WinError 32] ... used by another process`."""

    def test_the_temp_name_is_unique_per_process_and_attempt(self):
        """A fixed `.tmp` name means two writers collide. `_pending_downloads`
        de-duplicates within one process and cannot see a second instance —
        and four were started within five minutes."""
        import re
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent
                  / "src" / "services" / "asset_manager.py").read_text(encoding="utf-8")
        self.assertNotIn('tmp_path = f"{path}.tmp"', source)
        self.assertTrue(
            re.search(r'tmp_path = ".*"\.format\(\s*path, os\.getpid\(\)', source),
            "the temp file name is not unique to this process",
        )

    def test_a_locked_destination_is_retried_then_warned_not_errored(self):
        import time as time_module

        from services.asset_manager import AssetManager

        attempts = {"n": 0}

        class Fake:
            _REPLACE_ATTEMPTS = AssetManager._REPLACE_ATTEMPTS
            _REPLACE_BACKOFF_S = 0.0
            _replace_with_retry = AssetManager._replace_with_retry

        def failing_replace(_src, _dst):
            attempts["n"] += 1
            raise OSError(32, "used by another process")

        original_replace, original_sleep = os.replace, time_module.sleep
        os.replace = failing_replace
        time_module.sleep = lambda _s: None
        try:
            Fake()._replace_with_retry("a.tmp", "a.png")
        finally:
            os.replace, time_module.sleep = original_replace, original_sleep

        self.assertEqual(attempts["n"], AssetManager._REPLACE_ATTEMPTS)

    def test_a_successful_replace_does_not_retry(self):
        from services.asset_manager import AssetManager

        calls = {"n": 0}

        class Fake:
            _REPLACE_ATTEMPTS = AssetManager._REPLACE_ATTEMPTS
            _REPLACE_BACKOFF_S = 0.0
            _replace_with_retry = AssetManager._replace_with_retry

        def ok(_src, _dst):
            calls["n"] += 1

        original = os.replace
        os.replace = ok
        try:
            Fake()._replace_with_retry("a.tmp", "a.png")
        finally:
            os.replace = original
        self.assertEqual(calls["n"], 1)


class WebSocketStalenessTests(unittest.TestCase):
    """Hundreds of `Stale WebSocket connection ping timeout (45.0s >= 45.0s)`
    — one every 46 seconds, for hours, against a perfectly healthy client."""

    class _Ws:
        def __init__(self, answers=True, raises=False):
            self.answers, self.raises = answers, raises
            self.pings = 0

        def ping(self):
            self.pings += 1
            if self.raises:
                raise OSError("socket closed")
            answers = self.answers

            class Waiter:
                def wait(self, _timeout):
                    return answers

            return Waiter()

    def _handler(self):
        from services.api_handler import LCUClient

        return LCUClient.__new__(LCUClient)

    def test_a_quiet_but_answering_socket_is_kept(self):
        """Silence is not death: an idle lobby sends nothing for minutes."""
        ws = self._Ws(answers=True)
        self.assertTrue(self._handler()._ws_ping_succeeded(ws))
        self.assertEqual(ws.pings, 1)

    def test_an_unanswered_ping_means_reconnect(self):
        self.assertFalse(self._handler()._ws_ping_succeeded(self._Ws(answers=False)))

    def test_a_ping_that_cannot_be_sent_means_reconnect(self):
        self.assertFalse(self._handler()._ws_ping_succeeded(self._Ws(raises=True)))

    def test_a_build_without_a_pong_waiter_is_treated_as_alive(self):
        """Better evidence than silence, which is what it replaces."""

        class NoWaiter:
            def ping(self):
                return object()

        self.assertTrue(self._handler()._ws_ping_succeeded(NoWaiter()))

    def test_silence_alone_no_longer_records_a_connection_drop(self):
        """The drop count feeds the diagnostics screen, which was reporting a
        healthy link as failing."""
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent
                  / "src" / "services" / "api_handler.py").read_text(encoding="utf-8")
        self.assertNotIn("Stale WS ping timeout", source)
        self.assertIn("WS ping unanswered", source)


if __name__ == "__main__":
    unittest.main()


class WalletEndpointTests(unittest.TestCase):
    """`HTTP 400 Error on GET /lol-inventory/v1/wallet` on every poll."""

    def test_the_wallet_request_names_the_currencies(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent
                  / "src" / "services" / "account_manager.py").read_text(encoding="utf-8")
        self.assertIn("currencyTypes=", source)
        self.assertIn("lol_blue_essence", source)
