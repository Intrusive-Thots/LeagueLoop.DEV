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


if __name__ == "__main__":
    unittest.main()

