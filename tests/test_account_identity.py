"""
Identity parsing and account matching.

These were ~150 lines inlined in `detect_active_account()` with no coverage,
mixing API reads, name matching, list mutation and wallet fetching. Pulling
the decisions out made them testable; these tests pin the ones that decide
*which account you are*.
"""
import unittest

from services.accounts.identity import (
    ClientIdentity,
    MatchKind,
    from_lcu_summoner,
    from_riot_userinfo,
    match_account,
    missing_tagline_update,
)

ACCOUNTS = [
    {"label": "Main", "username": "themalcolm3", "tagline": "DPM#Null"},
    {"label": "Smurf", "username": "dpmnull2", "tagline": ""},
    {"label": "Faker", "username": "euwguy", "tagline": "Malc#EUW"},
]


class ParsingTests(unittest.TestCase):
    def test_riot_userinfo(self):
        identity = from_riot_userinfo({
            "preferred_username": "TheMalcolm3",
            "acct": {"game_name": "DPM", "tag_line": "Null"},
        })
        self.assertEqual(identity.login_name, "themalcolm3")
        self.assertEqual(identity.riot_id, "dpm#null")
        self.assertFalse(identity.is_empty)

    def test_riot_userinfo_without_a_riot_id(self):
        identity = from_riot_userinfo({"preferred_username": "solo"})
        self.assertEqual(identity.riot_id, "")
        self.assertEqual(identity.display_name(), "solo")

    def test_lcu_summoner_never_yields_a_login_name(self):
        """The LCU simply does not know it, so it must not be guessed."""
        identity = from_lcu_summoner({"gameName": "DPM", "tagLine": "Null"})
        self.assertEqual(identity.login_name, "")
        self.assertEqual(identity.riot_id, "dpm#null")

    def test_empty_payloads(self):
        self.assertTrue(from_riot_userinfo(None).is_empty)
        self.assertTrue(from_lcu_summoner({}).is_empty)


class MatchingTests(unittest.TestCase):
    def test_login_username_is_the_strongest_match(self):
        match = match_account(ClientIdentity(login_name="dpmnull2"), ACCOUNTS)
        self.assertEqual(match.index, 1)
        self.assertIs(match.kind, MatchKind.LOGIN_USERNAME)
        self.assertTrue(match.confident)

    def test_riot_id_matches_when_there_is_no_login_name(self):
        match = match_account(
            ClientIdentity(game_name="malc", tag_line="euw"), ACCOUNTS
        )
        self.assertEqual(match.index, 2)
        self.assertIs(match.kind, MatchKind.RIOT_ID)
        self.assertTrue(match.confident)

    def test_a_strong_match_later_in_the_list_beats_a_weak_one_earlier(self):
        """
        The original bug: it evaluated every rule against account 0 before
        looking at account 1 at all, so a label coincidence on the first row
        won over an exact Riot ID on the second.
        """
        accounts = [
            {"label": "malc", "username": "someone-else", "tagline": ""},
            {"label": "Other", "username": "x", "tagline": "malc#euw"},
        ]
        match = match_account(
            ClientIdentity(game_name="malc", tag_line="euw"), accounts
        )
        self.assertEqual(match.index, 1)
        self.assertIs(match.kind, MatchKind.RIOT_ID)

    def test_label_coincidence_is_reported_but_not_confident(self):
        accounts = [{"label": "faker", "username": "nope", "tagline": ""}]
        match = match_account(ClientIdentity(game_name="faker"), accounts)
        self.assertTrue(match.found)
        self.assertFalse(match.confident)
        self.assertIs(match.kind, MatchKind.LABEL_GUESS)

    def test_no_match(self):
        match = match_account(ClientIdentity(login_name="stranger"), ACCOUNTS)
        self.assertFalse(match.found)
        self.assertFalse(match.confident)

    def test_empty_identity_matches_nothing(self):
        self.assertFalse(match_account(ClientIdentity(), ACCOUNTS).found)

    def test_empty_account_fields_do_not_match_an_empty_identity_field(self):
        """A blank stored tagline must not match a blank live Riot ID."""
        accounts = [{"label": "", "username": "", "tagline": ""}]
        self.assertFalse(match_account(ClientIdentity(game_name="x"), accounts).found)

    def test_matching_is_case_insensitive(self):
        match = match_account(ClientIdentity(login_name="THEMALCOLM3"), ACCOUNTS)
        self.assertEqual(match.index, 0)


class TaglineBackfillTests(unittest.TestCase):
    def test_fills_a_blank_tagline(self):
        identity = ClientIdentity(game_name="dpm", tag_line="null")
        self.assertEqual(
            missing_tagline_update(identity, {"tagline": ""}), "dpm#null"
        )

    def test_never_overwrites_an_existing_tagline(self):
        identity = ClientIdentity(game_name="dpm", tag_line="null")
        self.assertEqual(
            missing_tagline_update(identity, {"tagline": "Something#Else"}), ""
        )

    def test_nothing_to_fill_without_a_riot_id(self):
        self.assertEqual(
            missing_tagline_update(ClientIdentity(login_name="a"), {"tagline": ""}), ""
        )

    def test_no_account(self):
        identity = ClientIdentity(game_name="dpm", tag_line="null")
        self.assertEqual(missing_tagline_update(identity, None), "")


if __name__ == "__main__":
    unittest.main()
