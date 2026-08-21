"""
Importing a champion list from the clipboard.

People keep these lists in Discord, spreadsheets and tier-list pages.
Retyping sixty champions one click at a time is why such a list goes stale,
so the paste has to be forgiving about format — and strict about identity,
because a list that silently lost four entries is worse than one that says so.
"""
import unittest

from services.champion_list_import import (
    ImportResult,
    build_lookup,
    parse_champion_list,
    split_names,
)

LOOKUP = {
    "sion": 14, "jinx": 222, "fizz": 105, "amumu": 32, "karthus": 30,
    "aurelionsol": 136, "shaco": 35, "twistedfate": 4, "leesin": 64,
    "chogath": 31, "masteryi": 11, "tahmkench": 223, "monkeyking": 62,
    "wukong": 62, "velkoz": 161,
}

# Exactly what was pasted in the request, opening brace and all.
REAL_PASTE = (
    "{Sion, Jinx, Fizz, Amumu, Karthus, AurelionSol, Shaco, TwistedFate"
)


class SplittingTests(unittest.TestCase):
    def test_the_real_paste(self):
        self.assertEqual(
            split_names(REAL_PASTE),
            ["Sion", "Jinx", "Fizz", "Amumu", "Karthus", "AurelionSol",
             "Shaco", "TwistedFate"],
        )

    def test_wrapping_braces_are_stripped(self):
        self.assertEqual(split_names("{Jinx, Sion}"), ["Jinx", "Sion"])

    def test_newlines_and_semicolons_work(self):
        self.assertEqual(split_names("Jinx\nSion;Fizz"), ["Jinx", "Sion", "Fizz"])

    def test_numbered_lists_lose_their_numbering(self):
        self.assertEqual(
            split_names("1. Jinx\n2) Sion\n- Fizz\n#4 Amumu"),
            ["Jinx", "Sion", "Fizz", "Amumu"],
        )

    def test_trailing_annotations_are_dropped(self):
        self.assertEqual(
            split_names("Jinx (52.1%), Sion [S tier]"), ["Jinx", "Sion"]
        )

    def test_spaces_are_not_separators(self):
        """"Lee Sin" and "Master Yi" contain spaces; guessing there loses more
        than it gains."""
        self.assertEqual(split_names("Lee Sin, Master Yi"), ["Lee Sin", "Master Yi"])

    def test_empty(self):
        self.assertEqual(split_names(""), [])
        self.assertEqual(split_names("   "), [])


class ParsingTests(unittest.TestCase):
    def _parse(self, text, existing=None):
        return parse_champion_list(text, lookup=LOOKUP, existing=existing)

    def test_order_is_preserved(self):
        result = self._parse("Jinx, Sion, Fizz")
        self.assertEqual(result.champion_ids, [222, 14, 105])

    def test_punctuation_and_case_are_ignored(self):
        result = self._parse("cho'gath, LEE SIN, Tahm Kench")
        self.assertEqual(result.champion_ids, [31, 64, 223])

    def test_both_the_ddragon_key_and_the_display_name_resolve(self):
        self.assertEqual(self._parse("MonkeyKing").champion_ids, [62])
        self.assertEqual(self._parse("Wukong").champion_ids, [62])

    def test_unknown_names_are_reported_not_dropped(self):
        result = self._parse("Jinx, Notachampion, Sion")
        self.assertEqual(result.champion_ids, [222, 14])
        self.assertEqual(result.unknown, ["Notachampion"])
        self.assertIn("not recognised", result.summary)

    def test_duplicates_are_removed_and_counted(self):
        result = self._parse("Jinx, Sion, Jinx")
        self.assertEqual(result.champion_ids, [222, 14])
        self.assertEqual(result.duplicates, ["Jinx"])
        self.assertIn("duplicate", result.summary)

    def test_existing_ids_count_as_duplicates(self):
        result = self._parse("Jinx, Sion", existing=[222])
        self.assertEqual(result.champion_ids, [14])

    def test_an_empty_paste_says_so(self):
        result = self._parse("")
        self.assertFalse(result.ok)
        self.assertIn("Nothing to import", result.summary)

    def test_a_paste_of_only_junk_is_not_ok(self):
        result = self._parse("asdf, qwer")
        self.assertFalse(result.ok)
        self.assertEqual(len(result.unknown), 2)

    def test_the_summary_truncates_a_long_unknown_list(self):
        result = self._parse("a, b, c, d, e")
        self.assertIn("and 2 more", result.summary)


class LookupTests(unittest.TestCase):
    def test_built_from_asset_manager(self):
        class Assets:
            champ_data = {
                "MonkeyKing": {"key": "62", "name": "Wukong"},
                "LeeSin": {"key": "64", "name": "Lee Sin"},
            }

        lookup = build_lookup(Assets())
        self.assertEqual(lookup["monkeyking"], 62)
        self.assertEqual(lookup["wukong"], 62)
        self.assertEqual(lookup["leesin"], 64)

    def test_a_bad_key_is_skipped_not_fatal(self):
        class Assets:
            champ_data = {"Broken": {"key": "not-a-number", "name": "Broken"}}

        self.assertEqual(build_lookup(Assets()), {})

    def test_no_assets_is_empty_not_a_crash(self):
        self.assertEqual(build_lookup(None), {})


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from ui.qt.widgets.champion_list_tab import QtPriorityTab

        class Assets:
            champ_data = {
                "Jinx": {"key": "222", "name": "Jinx"},
                "Sion": {"key": "14", "name": "Sion"},
                "Fizz": {"key": "105", "name": "Fizz"},
            }
            name_to_id = {}

            def get_champ_name(self, cid):
                return {222: "Jinx", 14: "Sion", 105: "Fizz"}.get(int(cid), "")

        class Config:
            def __init__(self): self.d = {}
            def get(self, k, default=None): return self.d.get(k, default)
            def set(self, k, v): self.d[k] = v

        class Container:
            def __init__(self):
                self.assets = Assets()
                self.config = Config()
                self.scraper = None

        return QtPriorityTab(container=Container())

    def _accept_next_modal(self):
        import ui.qt.widgets.champion_list_tab as mod
        original = mod.LLConfirmModal

        class Auto(original):
            def exec(self_inner):
                return original.Accepted

        mod.LLConfirmModal = Auto
        self.addCleanup(setattr, mod, "LLConfirmModal", original)

    def test_pasting_replaces_the_list(self):
        from PySide6.QtWidgets import QApplication

        tab = self._tab()
        QApplication.clipboard().setText("{Jinx, Sion, Fizz")
        self._accept_next_modal()
        tab.btn_paste.click()

        self.assertEqual(tab.current_ids(), [222, 14, 105])
        self.assertEqual(tab.config.get("priority_list"), [222, 14, 105])

    def test_an_empty_clipboard_says_so_and_changes_nothing(self):
        from PySide6.QtWidgets import QApplication

        tab = self._tab()
        QApplication.clipboard().setText("   ")
        tab.btn_paste.click()

        self.assertEqual(tab.current_ids(), [])
        self.assertIn("Clipboard is empty", tab.hint.text())

    def test_declining_the_confirmation_changes_nothing(self):
        import ui.qt.widgets.champion_list_tab as mod
        from PySide6.QtWidgets import QApplication

        tab = self._tab()
        QApplication.clipboard().setText("Jinx, Sion")

        original = mod.LLConfirmModal

        class Auto(original):
            def exec(self_inner):
                return original.Rejected

        mod.LLConfirmModal = Auto
        self.addCleanup(setattr, mod, "LLConfirmModal", original)

        tab.btn_paste.click()
        self.assertEqual(tab.current_ids(), [])

    def test_unrecognised_names_reach_the_user(self):
        from PySide6.QtWidgets import QApplication

        tab = self._tab()
        QApplication.clipboard().setText("Jinx, Notachampion")
        self._accept_next_modal()
        tab.btn_paste.click()

        self.assertEqual(tab.current_ids(), [222])
        self.assertIn("not recognised", tab.hint.text())


if __name__ == "__main__":
    unittest.main()


class AramModeTests(unittest.TestCase):
    """
    Pasting into the ARAM list was broken.

    `QtAramTab` was a second, near-identical implementation whose method was
    `_current_ids`; the shared paste handler called `current_ids()`. Clicking
    Paste raised AttributeError inside a Qt slot, which prints to stderr and
    otherwise looks like the button doing nothing at all.
    """

    @classmethod
    def setUpClass(cls):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from ui.qt.widgets.champion_list_tab import QtPriorityTab

        class Assets:
            champ_data = {
                "Jinx": {"key": "222", "name": "Jinx"},
                "Sion": {"key": "14", "name": "Sion"},
            }
            name_to_id = {}
            id_to_key = {222: "Jinx", 14: "Sion"}

            def get_champ_name(self, cid):
                return {222: "Jinx", 14: "Sion"}.get(int(cid), "")

        class Config:
            def __init__(self): self.d = {}
            def get(self, k, default=None): return self.d.get(k, default)
            def set(self, k, v): self.d[k] = v

        class Container:
            def __init__(self):
                self.assets = Assets()
                self.config = Config()
                self.scraper = None

        return QtPriorityTab(container=Container())

    def _accept(self):
        import ui.qt.widgets.champion_list_tab as mod
        original = mod.LLConfirmModal

        class Auto(original):
            def exec(self_inner):
                return original.Accepted

        mod.LLConfirmModal = Auto
        self.addCleanup(setattr, mod, "LLConfirmModal", original)

    def test_pasting_into_aram_mode_writes_the_aram_key(self):
        from core.config_keys import ARAM_PRIORITY_LIST, PRIORITY_LIST
        from PySide6.QtWidgets import QApplication

        tab = self._tab()
        tab.set_mode(ARAM_PRIORITY_LIST)

        QApplication.clipboard().setText("{Jinx, Sion")
        self._accept()
        tab.btn_paste.click()

        self.assertEqual(tab.config.get(ARAM_PRIORITY_LIST), [222, 14])
        self.assertIsNone(tab.config.get(PRIORITY_LIST))

    def test_switching_mode_reloads_the_other_list(self):
        from core.config_keys import ARAM_PRIORITY_LIST, PRIORITY_LIST

        tab = self._tab()
        tab.config.set(PRIORITY_LIST, [222])
        tab.config.set(ARAM_PRIORITY_LIST, [14])

        tab.set_mode(ARAM_PRIORITY_LIST)
        self.assertEqual(tab.current_ids(), [14])
        tab.set_mode(PRIORITY_LIST)
        self.assertEqual(tab.current_ids(), [222])

    def test_rows_carry_a_portrait_and_a_rank(self):
        """A ranked list of bare names is the hardest way to recognise 60 champions."""
        from PySide6.QtWidgets import QLabel

        tab = self._tab()
        tab.config.set("priority_list", [222, 14])
        tab._load_list()

        widget = tab.list_widget.itemWidget(tab.list_widget.item(0))
        self.assertIsNotNone(widget, "the list is still plain text items")
        self.assertTrue(hasattr(widget, "rank_label"))
        self.assertEqual(widget.rank_label.text(), "1")
        labels = [l for l in widget.findChildren(QLabel)]
        self.assertGreaterEqual(len(labels), 3)  # rank, portrait, name
