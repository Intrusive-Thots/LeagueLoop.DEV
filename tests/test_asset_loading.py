"""
Champion data loading.

`champ_data` staying empty is what left Priority, ARAM, Bans and Champ Select
with no champions at all, and every champion rendering as a bare numeric id.
Three things made that failure permanent and invisible:

* the download was `session.get(url).json()` with no status check, so a 404
  page could be written to the cache as though it were champion data;
* one failed attempt at startup meant no champions for the whole session;
* the failure was logged and nowhere else, so the UI could not explain it or
  offer a retry.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

import services.asset_manager as am


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


CHAMPIONS = {"data": {"Ahri": {"key": "103", "name": "Ahri", "tags": ["Mage"]}}}


class ChampionDataTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.object(am, "CACHE_DIR", self._tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.manager = am.AssetManager()
        self.addCleanup(self.manager.shutdown)
        self.manager.ddragon_ver = "99.9.9"

    def _serve(self, *responses):
        self.manager.session = mock.Mock()
        self.manager.session.get = mock.Mock(side_effect=list(responses))
        return self.manager.session.get

    def _cache_path(self):
        return os.path.join(self._tmp.name, "champion.json")

    # --------------------------------------------------------------- happy
    def test_a_good_response_is_cached_and_parsed(self):
        self._serve(FakeResponse(CHAMPIONS))
        self.assertTrue(self.manager._load_champion_data())
        self.assertIn("Ahri", self.manager.champ_data)
        self.assertEqual(self.manager.id_to_key[103], "Ahri")
        self.assertEqual(self.manager.champion_data_error, "")
        self.assertTrue(os.path.exists(self._cache_path()))

    def test_the_cache_is_used_on_the_next_load(self):
        get = self._serve(FakeResponse(CHAMPIONS))
        self.manager._load_champion_data()
        self.manager._load_champion_data()
        self.assertEqual(get.call_count, 1)

    # ------------------------------------------------------------ failures
    def test_an_http_error_is_never_written_to_the_cache(self):
        """A 404 body used to be cached as though it were champion data."""
        self._serve(FakeResponse({"nope": True}, status_code=404))
        self.assertFalse(self.manager._load_champion_data())
        self.assertFalse(os.path.exists(self._cache_path()))
        self.assertIn("404", self.manager.champion_data_error)

    def test_an_empty_payload_is_rejected(self):
        self._serve(FakeResponse({"data": {}}))
        self.assertFalse(self.manager._load_champion_data())
        self.assertFalse(os.path.exists(self._cache_path()))
        self.assertIn("no champion data", self.manager.champion_data_error)

    def test_a_non_json_body_is_rejected(self):
        self._serve(FakeResponse(None))
        self.assertFalse(self.manager._load_champion_data())
        self.assertFalse(os.path.exists(self._cache_path()))

    def test_the_failure_reason_is_readable_by_the_ui(self):
        self._serve(FakeResponse({"nope": True}, status_code=503))
        self.manager._load_champion_data()
        self.assertTrue(self.manager.champion_data_error)

    # --------------------------------------------------------------- retry
    def test_a_transient_failure_is_retried_and_succeeds(self):
        self.manager.CHAMPION_RETRY_BACKOFF_S = 0.01
        self._serve(
            FakeResponse({}, status_code=500),
            FakeResponse(CHAMPIONS),
        )
        self.assertTrue(self.manager._load_champion_data_with_retry())
        self.assertIn("Ahri", self.manager.champ_data)

    def test_it_gives_up_after_the_configured_attempts(self):
        self.manager.CHAMPION_RETRY_BACKOFF_S = 0.01
        self.manager.CHAMPION_LOAD_ATTEMPTS = 2
        get = self._serve(*[FakeResponse({}, status_code=500)] * 5)
        self.assertFalse(self.manager._load_champion_data_with_retry())
        self.assertEqual(get.call_count, 2)

    def test_shutdown_interrupts_a_retry_wait(self):
        self.manager.CHAMPION_RETRY_BACKOFF_S = 30.0
        self._serve(*[FakeResponse({}, status_code=500)] * 5)
        self.manager._shutdown_event.set()
        self.assertFalse(self.manager._load_champion_data_with_retry())

    def test_retry_is_callable_from_the_ui(self):
        self._serve(FakeResponse({}, status_code=500), FakeResponse(CHAMPIONS))
        with mock.patch.object(self.manager, "_fetch_latest_version"):
            self.assertFalse(self.manager.retry_champion_data())
            self.assertTrue(self.manager.retry_champion_data())


class ShutdownTests(unittest.TestCase):
    def test_workers_stop_and_the_session_closes(self):
        import threading

        before = threading.active_count()
        manager = am.AssetManager()
        self.assertGreater(threading.active_count(), before)

        manager.shutdown()
        for _ in range(50):
            if threading.active_count() <= before:
                break
            import time
            time.sleep(0.02)
        self.assertLessEqual(threading.active_count(), before)


if __name__ == "__main__":
    unittest.main()

