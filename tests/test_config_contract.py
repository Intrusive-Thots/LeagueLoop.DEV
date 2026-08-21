"""
The UI and the engine must agree on config key names.

They did not. The Bans screen wrote `ban_list` while the engine read
`ban_priority`; the ARAM screen wrote `aram_priority_list` while the engine
read `priority_list` and nothing else. Both screens were no-ops — you would
configure a ban list, watch auto-ban ignore it, and blame the automation.

Two string literals in two files cannot be kept in step by discipline, so
these tests assert the contract instead.
"""
import unittest

from core.config_keys import (
    ARAM_PRIORITY_LIST,
    BAN_LIST,
    PRIORITY_LIST,
    read_champion_ids,
    role_ban_key,
    role_priority_key,
)
from services.draft.priority_engine import PriorityEngine


class FakeConfig:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


def engine(**values):
    return PriorityEngine(config_manager=FakeConfig(**values))


class BanContractTests(unittest.TestCase):
    def test_the_engine_reads_the_key_the_bans_screen_writes(self):
        self.assertEqual(
            engine(**{BAN_LIST: [103, 86]})._get_ban_priorities_for_role(""),
            [103, 86],
        )

    def test_the_bans_screen_writes_that_key(self):
        from ui.qt.widgets.champion_list_tab import QtBanListTab
        self.assertEqual(QtBanListTab.CONFIG_KEY, BAN_LIST)

    def test_a_role_specific_ban_list_wins(self):
        e = engine(**{BAN_LIST: [1], role_ban_key("TOP"): [2]})
        self.assertEqual(e._get_ban_priorities_for_role("TOP"), [2])

    def test_an_empty_role_list_falls_back_rather_than_banning_nothing(self):
        e = engine(**{BAN_LIST: [1], role_ban_key("TOP"): []})
        self.assertEqual(e._get_ban_priorities_for_role("TOP"), [1])


class PriorityContractTests(unittest.TestCase):
    def test_the_engine_reads_the_key_the_priority_screen_writes(self):
        from ui.qt.widgets.champion_list_tab import QtPriorityTab
        self.assertEqual(QtPriorityTab.CONFIG_KEY, PRIORITY_LIST)
        self.assertEqual(
            engine(**{PRIORITY_LIST: [7]})._get_pick_priorities_for_role(""), [7]
        )

    def test_a_role_specific_list_wins(self):
        e = engine(**{PRIORITY_LIST: [1], role_priority_key("MIDDLE"): [2]})
        self.assertEqual(e._get_pick_priorities_for_role("MIDDLE"), [2])


class AramContractTests(unittest.TestCase):
    def test_the_engine_reads_the_key_the_aram_screen_writes(self):
        from ui.qt.widgets.champion_list_tab import QtAramTab
        self.assertEqual(QtAramTab.CONFIG_KEY, ARAM_PRIORITY_LIST)
        e = engine(**{ARAM_PRIORITY_LIST: [350], PRIORITY_LIST: [1]})
        self.assertEqual(e._get_pick_priorities_for_role("", aram=True), [350])

    def test_no_aram_list_falls_back_to_the_general_one(self):
        e = engine(**{PRIORITY_LIST: [1, 2]})
        self.assertEqual(e._get_pick_priorities_for_role("", aram=True), [1, 2])

    def test_aram_list_is_ignored_outside_aram(self):
        e = engine(**{ARAM_PRIORITY_LIST: [350], PRIORITY_LIST: [1]})
        self.assertEqual(e._get_pick_priorities_for_role(""), [1])

    def test_aram_is_detected_from_the_session_queue_id(self):
        self.assertTrue(PriorityEngine._is_aram({"queueId": 450}))
        self.assertTrue(PriorityEngine._is_aram({"gameConfig": {"queueId": 450}}))
        self.assertTrue(PriorityEngine._is_aram({"queueId": 720}))

    def test_an_unknown_queue_is_not_treated_as_aram(self):
        self.assertFalse(PriorityEngine._is_aram({"queueId": 420}))
        self.assertFalse(PriorityEngine._is_aram({}))
        self.assertFalse(PriorityEngine._is_aram({"queueId": "nonsense"}))


class ReaderTests(unittest.TestCase):
    def test_string_ids_from_older_configs_are_accepted(self):
        self.assertEqual(
            read_champion_ids(FakeConfig(k=["103", 86]), "k"), [103, 86]
        )

    def test_one_bad_entry_costs_that_entry_not_the_list(self):
        self.assertEqual(
            read_champion_ids(FakeConfig(k=[103, None, "x", 0, 86]), "k"),
            [103, 86],
        )

    def test_missing_key_and_missing_config(self):
        self.assertEqual(read_champion_ids(FakeConfig(), "nope"), [])
        self.assertEqual(read_champion_ids(None, "nope"), [])


class NoOrphanKeysTest(unittest.TestCase):
    """Every champion-list key the UI writes must be read by the engine."""

    def test_ui_keys_are_all_consumed(self):
        import inspect
        from services.draft import priority_engine
        from core import config_keys

        source = inspect.getsource(priority_engine)
        for key_name in ("PRIORITY_LIST", "ARAM_PRIORITY_LIST", "BAN_LIST"):
            self.assertIn(
                key_name, source,
                "{} is written by the UI but the engine never reads it"
                .format(getattr(config_keys, key_name)),
            )


if __name__ == "__main__":
    unittest.main()


class OrphanWidgetTests(unittest.TestCase):
    """
    Screens that exist but nothing imports are screens the user never sees.

    `aram_tab.py` (bench sniper, auto-reroll, sort by win rate) and
    `ban_list_dialog.py` (respect-teammate-hovers rule) were both written and
    both orphaned — the generic champion-list tab was standing in for ARAM,
    and the Automation screen's "Ban list" button went nowhere.
    """

    @classmethod
    def setUpClass(cls):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_aram_is_a_mode_on_the_priority_screen_not_a_tab(self):
        """
        Two near-identical screens editing two config keys is how one of them
        ended up with a paste button that called a method the other had under
        a different name. One screen, one implementation, a mode switch.
        """
        from core.config_keys import ARAM_PRIORITY_LIST, PRIORITY_LIST
        from ui.qt.widgets.champion_list_tab import QtPriorityTab
        from ui.qt.widgets.navigation.sidebar import QtNavigationSidebar

        keys = [key for key, _label, _icon in QtNavigationSidebar.DEFAULT_TABS]
        self.assertNotIn("aram", keys)
        self.assertIn("priority", keys)

        modes = dict(QtPriorityTab.MODES)
        self.assertIn(PRIORITY_LIST, modes)
        self.assertIn(ARAM_PRIORITY_LIST, modes)

    def test_the_ban_dialog_is_reachable(self):
        from ui.qt.widgets.ban_list_dialog import QtBanListDialog
        self.assertTrue(callable(QtBanListDialog))

    def test_both_orphans_write_the_shared_keys(self):
        from ui.qt.widgets.aram_tab import QtAramTab as Dedicated
        import inspect
        self.assertIn("ARAM_PRIORITY_LIST", inspect.getsource(Dedicated))

        from ui.qt.widgets import ban_list_dialog
        self.assertIn("BAN_LIST", inspect.getsource(ban_list_dialog))


class ConfigureActionTests(unittest.TestCase):
    """The per-automation "configure" affordances must go somewhere."""

    @classmethod
    def setUpClass(cls):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        import tempfile, os as _os
        from core.container import ApplicationContainer
        from ui.qt.main_window import LeagueLoopMainWindow

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        container = ApplicationContainer(
            db_path=_os.path.join(self._tmp.name, "t.db")
        )
        self.addCleanup(container.shutdown)
        return LeagueLoopMainWindow(container=container)

    def test_priorities_jumps_to_the_priority_screen(self):
        from core.config_keys import AUTO_LOCK_IN
        window = self._window()
        window._on_configure_requested(AUTO_LOCK_IN)
        self.assertIs(
            window.tab_stack.currentWidget(), window.tab_pages["priority"]
        )

    def test_an_unknown_key_does_not_crash(self):
        window = self._window()
        window._on_configure_requested("something_unmapped")
        self.assertIsNotNone(window.tab_stack.currentWidget())


class BootstrapTests(unittest.TestCase):
    """
    One startup sequence, shared by both shells.

    Four separate bugs this session had the same cause: a service that
    `core/main.py` started imperatively and the Qt shell never did. Adding a
    service to `bootstrap()` now reaches both by construction.
    """

    def _container(self):
        import tempfile, os
        from core.container import ApplicationContainer

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        container = ApplicationContainer(db_path=os.path.join(tmp.name, "t.db"))
        self.addCleanup(container.shutdown)
        return container

    def test_bootstrap_builds_every_lazy_service(self):
        container = self._container().bootstrap(start_assets=False)
        self.assertIsNotNone(container.automation)
        self.assertIsNotNone(container.automation_controller)
        self.assertIsNotNone(container.client_state)

    def test_the_client_state_poller_is_not_started_by_default(self):
        """Starting before the UI subscribes delivers the first values to nobody."""
        container = self._container().bootstrap(start_assets=False)
        self.assertFalse(container.client_state.running)

    def test_one_broken_service_does_not_stop_the_others(self):
        container = self._container()

        class Boom:
            def start_loading(self):
                raise RuntimeError("no network")

        container.assets = Boom()
        container.bootstrap(start_assets=True)

        self.assertTrue(container.bootstrap_errors)
        self.assertIn("assets", [name for name, _ in container.bootstrap_errors])
        self.assertIsNotNone(container.automation_controller)

    def test_both_shells_call_it(self):
        """
        Read as source, not imported: `core.main` pulls in tkinter, which is
        absent on the CI image. The point of the assertion is the call site,
        and the call site is visible in the text.
        """
        import inspect
        import os
        from ui.qt.app import application

        self.assertIn("bootstrap(", inspect.getsource(application))

        legacy_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "core", "main.py",
        )
        with open(legacy_path, encoding="utf-8") as handle:
            self.assertIn("container.bootstrap(", handle.read())


class PlayHandoffTests(unittest.TestCase):
    """Play's automation card links to the screen that owns automation."""

    @classmethod
    def setUpClass(cls):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_the_link_navigates(self):
        import tempfile, os as _os
        from core.container import ApplicationContainer
        from ui.qt.main_window import LeagueLoopMainWindow

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        container = ApplicationContainer(db_path=_os.path.join(tmp.name, "t.db"))
        self.addCleanup(container.shutdown)

        window = LeagueLoopMainWindow(container=container)
        window.sidebar.select_tab("play")
        window.tab_pages["play"].btn_automation.click()
        self.assertIs(
            window.tab_stack.currentWidget(), window.tab_pages["automation"]
        )


class DeadToggleTests(unittest.TestCase):
    """
    Every switch the UI shows must reach something at runtime.

    Seven did not: `always_on_top`, `aram_bench_swap`, `aram_auto_reroll`,
    `auto_set_roles`, `auto_hover`, `developer_mode`, and the ban dialog's
    `auto_ban_respect_teammates` (the engine reads `auto_ban_respect_hovers`).
    A switch for a feature that does not exist is worse than a missing
    feature — it makes the working ones look unreliable too.
    """

    def _engine_source(self):
        import inspect
        from services import automation

        return inspect.getsource(automation)

    def test_the_bench_sniper_switch_is_read(self):
        self.assertIn("aram_bench_swap", self._engine_source())

    def test_the_reroll_switch_is_read(self):
        source = self._engine_source()
        self.assertIn("aram_auto_reroll", source)
        self.assertIn("my-selection/reroll", source)

    def test_auto_hover_gates_hovering(self):
        self.assertIn('self.config.get("auto_hover"', self._engine_source())

    def test_auto_set_roles_is_gone_rather_than_pretending(self):
        import inspect
        from ui.qt.widgets import automation_tab

        source = inspect.getsource(automation_tab)
        self.assertNotIn('("auto_set_roles"', source)

    def test_the_ban_dialog_writes_the_key_the_engine_reads(self):
        import inspect
        from core.config_keys import AUTO_BAN_RESPECT_HOVERS
        from ui.qt.widgets import ban_list_dialog

        source = inspect.getsource(ban_list_dialog)
        self.assertIn("AUTO_BAN_RESPECT_HOVERS", source)
        # The old key may still be named in a comment explaining the fix; what
        # matters is that it is no longer used as a config key.
        self.assertNotIn('config.set("auto_ban_respect_teammates"', source)
        self.assertNotIn('config.get("auto_ban_respect_teammates"', source)
        self.assertIn(AUTO_BAN_RESPECT_HOVERS, self._engine_source())

    def test_developer_mode_reaches_diagnostics(self):
        import inspect
        from ui.qt.widgets import diagnostics_tab

        self.assertIn("developer_mode", inspect.getsource(diagnostics_tab))


class VersionTests(unittest.TestCase):
    def test_the_major_version_is_two(self):
        from core.version import __version__

        self.assertTrue(
            __version__.startswith("2-"),
            "major version should be 2; got {}".format(__version__),
        )

    def test_the_format_holds(self):
        import re
        from core.version import __version__

        self.assertRegex(__version__, r"^\d-\d{2}-\d{1,3}-\d{4}$")

    def test_the_bump_tool_agrees_with_the_file(self):
        import os
        import subprocess
        import sys

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            [sys.executable, os.path.join(root, "tools", "bump_version.py"), "--check"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
