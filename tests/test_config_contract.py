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
