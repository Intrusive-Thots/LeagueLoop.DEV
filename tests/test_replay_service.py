"""
Auto-save replays: opt-in, post-game only, official LCU endpoints.

The download is ``POST /lol-replays/v1/rofls/{gameId}/download`` after
``GET /lol-replays/v1/metadata/{gameId}``. ``checking`` and ``lost`` are
retried a few times. Anything already on disk, or not available, is not
downloaded again. Nothing here runs while a game is in progress.
"""
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.config_keys import AUTO_SAVE_REPLAYS
from services.config_manager import DEFAULT_CONFIG
from services.replay_service import (
    DOWNLOAD_ENDPOINT,
    OUTCOME_ALREADY,
    OUTCOME_FAILED,
    OUTCOME_SAVED,
    OUTCOME_STARTED,
    OUTCOME_STOPPED,
    OUTCOME_UNAVAILABLE,
    ReplaySaver,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class _Config:
    def __init__(self, **values):
        self.values = dict(values)
        self.sets = []

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value, save=True):
        self.values[key] = value
        self.sets.append((key, value))


def _response(code, payload=None):
    response = MagicMock()
    response.status_code = code
    response.json.return_value = payload
    return response


class _Lcu:
    """Scripted LCU. Each metadata read pops the next state."""

    def __init__(self, states=None, eog_ids=None, history=None, post_code=204,
                 configuration=None, rofls_path=None, session_id=None):
        self.states = list(states or [])
        self.eog_ids = list(eog_ids) if eog_ids is not None else [4242]
        self.history = history
        self.post_code = post_code
        self.configuration = configuration
        self.rofls_path = rofls_path
        self.session_id = session_id
        self.posts = []
        self.calls = []

    def request(self, method, endpoint, data=None, silent=False):
        self.calls.append((method, endpoint, data))
        if method == "POST" and endpoint.endswith("/download"):
            self.posts.append((endpoint, data))
            return _response(self.post_code, None)
        if endpoint.startswith("/lol-replays/v1/metadata/"):
            if not self.states:
                return _response(404, None)
            state = self.states.pop(0)
            if state is None:
                return None
            if state == 404:
                return _response(404, None)
            return _response(200, {"state": state, "gameId": 4242})
        if endpoint == "/lol-end-of-game/v1/eog-stats-block":
            if not self.eog_ids:
                return _response(404, None)
            game_id = self.eog_ids.pop(0)
            if game_id is None:
                return _response(404, None)
            return _response(200, {"gameId": game_id})
        if endpoint == "/lol-gameflow/v1/session":
            if not self.session_id:
                return _response(404, None)
            return _response(200, {"gameData": {"gameId": self.session_id}})
        if endpoint.startswith("/lol-match-history/"):
            if self.history is None:
                return None
            return _response(200, self.history)
        if endpoint == "/lol-replays/v1/configuration":
            if self.configuration is None:
                return _response(404, None)
            return _response(200, self.configuration)
        if endpoint == "/lol-replays/v1/rofls/path":
            if self.rofls_path is None:
                return _response(404, None)
            return _response(200, self.rofls_path)
        return _response(404, None)


def _saver(lcu, enabled=True, phase="EndOfGame", **kwargs):
    config = _Config(**{AUTO_SAVE_REPLAYS: enabled})
    phases = {"value": phase}

    def phase_getter():
        return phases["value"]

    saver = ReplaySaver(
        lcu,
        config,
        phase_getter=phase_getter,
        sleep=kwargs.pop("sleep", lambda _s: None),
        spawn=lambda target: target(),
        **kwargs,
    )
    saver._phases = phases
    return saver


class DefaultOffTests(unittest.TestCase):
    def test_shipped_default_is_off(self):
        self.assertIs(DEFAULT_CONFIG[AUTO_SAVE_REPLAYS], False)

    def test_disabled_does_not_touch_the_client(self):
        lcu = _Lcu(states=["download"])
        saver = _saver(lcu, enabled=False)
        self.assertFalse(saver.on_match_ended())
        self.assertEqual(lcu.calls, [])
        self.assertEqual(lcu.posts, [])

    def test_a_truthy_stand_in_does_not_count_as_on(self):
        """config.get() with no return value is truthy. The feature must not be."""
        lcu = _Lcu(states=["download"])
        saver = ReplaySaver(
            lcu, MagicMock(), sleep=lambda _s: None, spawn=lambda target: target(),
        )
        self.assertFalse(saver.enabled)
        self.assertFalse(saver.on_match_ended())
        self.assertEqual(lcu.posts, [])


class DownloadTests(unittest.TestCase):
    def test_ready_state_posts_the_official_download(self):
        lcu = _Lcu(states=["download", "watch"], eog_ids=[4242])
        saver = _saver(lcu)
        self.assertTrue(saver.on_match_ended())
        self.assertEqual(
            lcu.posts,
            [(
                DOWNLOAD_ENDPOINT.format(game_id=4242),
                {"gameId": 4242, "componentType": "replay-button_match-history"},
            )],
        )
        self.assertEqual(saver.last_message, "Saved replay for game 4242.")
        self.assertFalse(saver.last_error)

    def test_retries_while_checking_or_lost_then_downloads(self):
        lcu = _Lcu(states=["checking", "lost", "download", "watch"])
        saver = _saver(lcu)
        saver.on_match_ended()
        self.assertEqual(len(lcu.posts), 1)
        self.assertEqual(saver.last_message, "Saved replay for game 4242.")

    def test_still_lost_is_skipped_without_a_download(self):
        lcu = _Lcu(states=["lost", "checking", "lost", "lost"])
        messages = []
        saver = _saver(lcu)
        saver.add_listener(lambda message, is_error: messages.append((message, is_error)))
        saver.on_match_ended()
        self.assertEqual(lcu.posts, [])
        self.assertIn("isn't available", saver.last_message)
        self.assertTrue(saver.last_error)
        self.assertTrue(messages[-1][1])

    def test_metadata_404_is_treated_as_unavailable(self):
        lcu = _Lcu(states=[404, 404, 404, 404])
        saver = _saver(lcu)
        saver.on_match_ended()
        self.assertEqual(lcu.posts, [])
        self.assertTrue(saver.last_error)

    def test_already_on_disk_is_not_downloaded_again(self):
        lcu = _Lcu(states=["watch"])
        saver = _saver(lcu)
        self.assertEqual(saver._download_game(4242), OUTCOME_ALREADY)
        self.assertEqual(saver._download_game(4242), OUTCOME_ALREADY)
        self.assertEqual(lcu.posts, [])

    def test_a_second_end_of_game_does_not_post_twice(self):
        lcu = _Lcu(states=["download", "watch"], eog_ids=[4242, 4242])
        saver = _saver(lcu)
        saver.on_match_ended()
        saver.on_match_ended()
        self.assertEqual(len(lcu.posts), 1)

    def test_incompatible_is_skipped(self):
        lcu = _Lcu(states=["incompatible"])
        saver = _saver(lcu)
        self.assertEqual(saver._download_game(7), OUTCOME_UNAVAILABLE)
        self.assertEqual(lcu.posts, [])

    def test_download_in_progress_is_not_posted_again(self):
        lcu = _Lcu(states=["downloading", "downloading", "downloading", "downloading"])
        saver = _saver(lcu)
        self.assertEqual(saver._download_game(7), OUTCOME_STARTED)
        self.assertEqual(lcu.posts, [])
        # Already noted as in flight: a later call does not ask again.
        self.assertEqual(saver._download_game(7), OUTCOME_ALREADY)
        self.assertEqual(lcu.posts, [])

    def test_rejected_download_is_a_quiet_failure(self):
        lcu = _Lcu(states=["download", "download"], post_code=500)
        saver = _saver(lcu)
        self.assertEqual(saver._download_game(7), OUTCOME_FAILED)
        self.assertEqual(len(lcu.posts), 1)

    def test_unread_metadata_does_not_post(self):
        lcu = _Lcu(states=[None, None, None, None])
        saver = _saver(lcu)
        self.assertEqual(saver._download_game(7), OUTCOME_FAILED)
        self.assertEqual(lcu.posts, [])

    def test_stops_when_a_game_starts(self):
        lcu = _Lcu(states=["checking", "download"])

        def sleep(_seconds):
            saver._phases["value"] = "InProgress"

        saver = _saver(lcu, sleep=sleep)
        self.assertEqual(saver._download_game(7), OUTCOME_STOPPED)
        self.assertEqual(lcu.posts, [])

    def test_eog_game_id_is_waited_for(self):
        lcu = _Lcu(states=["download", "watch"], eog_ids=[None, 99], session_id=None)
        saver = _saver(lcu)
        saver.on_match_ended()
        self.assertEqual(lcu.posts[0][0], DOWNLOAD_ENDPOINT.format(game_id=99))

    def test_falls_back_to_the_gameflow_session_id(self):
        lcu = _Lcu(states=["download", "watch"], eog_ids=[], session_id=55)
        saver = _saver(lcu)
        saver.on_match_ended()
        self.assertEqual(lcu.posts[0][0], DOWNLOAD_ENDPOINT.format(game_id=55))


class RecentAndFolderTests(unittest.TestCase):
    def test_recent_games_skip_what_is_missing_and_what_is_saved(self):
        history = {"games": {"games": [
            {"gameId": 1},
            {"gameId": 2},
            {"gameId": 3},
            {"gameId": "nope"},
        ]}}
        # game 1 already on disk, game 2 downloadable, game 3 lost.
        lcu = _Lcu(
            states=["watch", "download", "watch", "lost", "lost", "lost", "lost"],
            history=history,
        )
        saver = _saver(lcu, enabled=False)
        self.assertTrue(saver.download_recent())
        self.assertEqual(
            [endpoint for endpoint, _body in lcu.posts],
            [DOWNLOAD_ENDPOINT.format(game_id=2)],
        )
        self.assertIn("Saved 1 replay", saver.last_message)
        self.assertIn("1 already saved", saver.last_message)
        self.assertIn("1 not available", saver.last_message)

    def test_recent_games_work_with_the_toggle_off(self):
        lcu = _Lcu(states=["download", "watch"], history={"games": {"games": [{"gameId": 8}]}})
        saver = _saver(lcu, enabled=False)
        self.assertTrue(saver.download_recent())
        self.assertEqual(len(lcu.posts), 1)

    def test_no_history_is_reported_quietly(self):
        lcu = _Lcu(history=None)
        saver = _saver(lcu)
        saver.download_recent()
        self.assertIn("Couldn't read recent games", saver.last_message)
        self.assertEqual(lcu.posts, [])

    def test_a_second_batch_does_not_start_while_one_is_running(self):
        lcu = _Lcu(history={"games": {"games": []}})
        saver = _saver(lcu)
        saver._busy = True
        self.assertFalse(saver.download_recent())
        self.assertIn("already running", saver.last_message)

    def test_replay_folder_comes_from_configuration(self):
        lcu = _Lcu(configuration={"replayFolderPath": r"C:\Replays"})
        saver = _saver(lcu)
        self.assertEqual(saver.replay_folder(), r"C:\Replays")

    def test_replay_folder_falls_back_to_the_rofls_path(self):
        lcu = _Lcu(configuration={}, rofls_path=r"D:\League\Replays")
        saver = _saver(lcu)
        self.assertEqual(saver.replay_folder(), r"D:\League\Replays")


class EngineHookTests(unittest.TestCase):
    def _engine(self, enabled):
        from services.automation import AutomationEngine

        config = MagicMock()
        config.get.side_effect = lambda key, default=None: (
            True if enabled and key == AUTO_SAVE_REPLAYS else default
        )
        engine = AutomationEngine(lcu=MagicMock(), assets=MagicMock(), config=config)
        engine.replay_saver.on_match_ended = MagicMock(return_value=True)
        return engine

    def test_end_of_game_starts_a_download_when_enabled(self):
        engine = self._engine(enabled=True)
        engine._maybe_autosave_replay("EndOfGame", "InProgress")
        engine.replay_saver.on_match_ended.assert_called_once()

    def test_pre_end_of_game_counts(self):
        engine = self._engine(enabled=True)
        engine._maybe_autosave_replay("PreEndOfGame", "WaitingForStats")
        engine.replay_saver.on_match_ended.assert_called_once()

    def test_off_by_default_does_not_start_one(self):
        engine = self._engine(enabled=False)
        engine._maybe_autosave_replay("EndOfGame", "InProgress")
        engine.replay_saver.on_match_ended.assert_not_called()

    def test_in_progress_does_not_start_one(self):
        engine = self._engine(enabled=True)
        engine._maybe_autosave_replay("InProgress", "ChampSelect")
        engine.replay_saver.on_match_ended.assert_not_called()

    def test_staying_on_the_post_game_screen_does_not_ask_again(self):
        engine = self._engine(enabled=True)
        engine._maybe_autosave_replay("EndOfGame", "PreEndOfGame")
        engine.replay_saver.on_match_ended.assert_not_called()

    def test_tick_fires_once_when_the_game_ends_even_if_paused(self):
        """The power switch pauses automation. Replay saving is separate."""
        engine = self._engine(enabled=True)
        engine.paused = True
        engine.last_phase = "InProgress"
        engine._is_first_tick = False
        engine._is_game_running = MagicMock(return_value=False)
        engine.executor = MagicMock()
        engine.window_func = MagicMock()
        engine._stop_event = MagicMock()
        engine._game_pid = None
        phase = MagicMock()
        phase.status_code = 200
        phase.json.return_value = "EndOfGame"
        future = MagicMock()
        future.result.return_value = phase
        engine.executor.submit.return_value = future

        engine._tick()
        engine.replay_saver.on_match_ended.assert_called_once()

        engine.replay_saver.on_match_ended.reset_mock()
        engine._tick()
        engine.replay_saver.on_match_ended.assert_not_called()

    def test_a_real_saver_downloads_through_the_engine_hook(self):
        from services.automation import AutomationEngine

        lcu = _Lcu(states=["checking", "download", "watch"], eog_ids=[4242])
        config = _Config(**{AUTO_SAVE_REPLAYS: True})
        engine = AutomationEngine(lcu=lcu, assets=MagicMock(), config=config)
        engine.replay_saver._spawn = lambda target: target()
        engine.replay_saver._sleep = lambda _s: None
        engine._maybe_autosave_replay("EndOfGame", "InProgress")
        self.assertEqual(len(lcu.posts), 1)
        self.assertEqual(lcu.posts[0][0], DOWNLOAD_ENDPOINT.format(game_id=4242))


class SettingsToggleTests(unittest.TestCase):
    """The settings row, built for real. Skips where Tk cannot start."""

    def setUp(self):
        try:
            import customtkinter as ctk
            from ui.app_sidebar import SidebarWidget
        except Exception as exc:
            raise unittest.SkipTest(f"sidebar cannot be imported: {exc}")

        try:
            self.app = ctk.CTk()
        except Exception as exc:
            raise unittest.SkipTest(f"no display: {exc}")
        self.app.geometry("300x520")
        for name in (
            "_hotkey_launch_client", "_on_close",
            "on_dock_toggled", "on_settings_saved",
        ):
            setattr(self.app, name, lambda *a, **k: None)
        self.config = _Config()
        try:
            self.sidebar = SidebarWidget(
                self.app, toggle_callback=lambda *a: None, config=self.config,
            )
        except Exception as exc:
            self.app.destroy()
            raise unittest.SkipTest(f"could not build the sidebar: {exc}")

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass

    def _pump(self, passes=15):
        for _ in range(passes):
            self.app.update_idletasks()
            self.app.update()

    def test_toggle_is_off_and_persists(self):
        self.assertFalse(self.sidebar.var_auto_save_replays.get())
        self.assertNotIn(AUTO_SAVE_REPLAYS, self.config.values)

        self.sidebar.row_auto_save_replays.toggle.toggle()
        self._pump()
        self.assertIs(self.config.values[AUTO_SAVE_REPLAYS], True)

        self.sidebar.row_auto_save_replays.toggle.toggle()
        self._pump()
        self.assertIs(self.config.values[AUTO_SAVE_REPLAYS], False)

        self.assertIn(
            "Downloads the replay (.rofl) when a match ends",
            self.sidebar.lbl_replay_help.cget("text"),
        )
        self.assertIn(
            "Download replays for recent games",
            self.sidebar.row_replay_recent.desc_label.cget("text"),
        )

    def test_status_and_folder_follow_the_saver(self):
        class _Saver:
            def __init__(self):
                self.listeners = []
                self.last_message = "Saved replay for game 5."
                self.last_error = False
                self.downloads = 0

            def add_listener(self, listener):
                self.listeners.append(listener)

            def replay_folder(self):
                return r"C:\Replays"

            def download_recent(self):
                self.downloads += 1
                for listener in self.listeners:
                    listener("Saved 1 replay.", False)
                return True

        saver = _Saver()
        self.sidebar.set_replay_saver(saver)
        self._pump()
        self.assertEqual(
            self.sidebar.row_replay_recent.status_label.cget("text"),
            "Saved replay for game 5.",
        )

        self.sidebar.switch_tab("Settings")
        for thread in threading.enumerate():
            if thread.name == "ReplayFolder" and thread is not threading.current_thread():
                thread.join(timeout=2)
        self._pump()
        self.assertIn(r"C:\Replays", self.sidebar.lbl_replay_folder.cget("text"))

        self.sidebar._on_download_recent_replays()
        self._pump()
        self.assertEqual(saver.downloads, 1)
        self.assertEqual(
            self.sidebar.row_replay_recent.status_label.cget("text"),
            "Saved 1 replay.",
        )


class BoundaryTests(unittest.TestCase):
    def test_module_does_not_play_replays_or_touch_the_game(self):
        text = (SRC / "services" / "replay_service.py").read_text(encoding="utf-8")
        self.assertNotIn("/watch", text)
        self.assertNotIn("game.cfg", text)
        self.assertNotIn("2999", text)
        self.assertNotIn("liveclientdata", text)
        self.assertIn("/lol-replays/v1/rofls/", text)
        self.assertIn("/lol-replays/v1/metadata/", text)

    def test_settings_label_and_help_are_present(self):
        text = (SRC / "ui" / "app_sidebar.py").read_text(encoding="utf-8")
        self.assertIn("Auto-save replays after each match", text)
        self.assertIn("Downloads the replay (.rofl) when a match ends", text)
        self.assertIn("Download replays for recent games", text)
        self.assertIn(AUTO_SAVE_REPLAYS, text)

    def test_missing_replay_404_is_not_logged_as_a_client_error(self):
        from services.api_handler import LCUClient

        self.assertTrue(LCUClient._is_expected_absence(
            404, "/lol-replays/v1/metadata/12345"
        ))
        self.assertTrue(LCUClient._is_expected_absence(
            404, "/lol-replays/v1/rofls/12345/download"
        ))
        self.assertFalse(LCUClient._is_expected_absence(
            500, "/lol-replays/v1/metadata/12345"
        ))


if __name__ == "__main__":
    unittest.main()
