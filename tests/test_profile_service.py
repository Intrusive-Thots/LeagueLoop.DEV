"""
Profile data.

The profile screen read at most 20 rows from a local SQLite table written by
the automation loop — which was never running in the Qt shell — and presented
that as the user's record. It never asked the client for real match history
and never fetched rank at all.
"""
import unittest

from services.profile_service import (
    Profile,
    ProfileService,
    RankEntry,
    parse_match,
    parse_rank,
)

RANKED_PAYLOAD = {
    "queueMap": {
        "RANKED_SOLO_5x5": {"tier": "EMERALD", "division": "II",
                            "leaguePoints": 47, "wins": 61, "losses": 55},
        "RANKED_FLEX_SR": {"tier": "NONE", "division": "NA",
                           "leaguePoints": 0, "wins": 0, "losses": 0},
    }
}

GAME = {
    "gameId": 123,
    "queueId": 450,
    "gameDuration": 1284,
    "gameCreation": 1700000000000,
    "participants": [{
        "championId": 103,
        "stats": {"win": True, "kills": 9, "deaths": 3, "assists": 14},
        "timeline": {"lane": "MIDDLE", "role": "SOLO"},
    }],
}


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class FakeLcu:
    def __init__(self, summoner=None, ranked=None, history=None, connected=True):
        self.is_connected = connected
        self.summoner = summoner
        self.ranked = ranked
        self.history = history

    def request(self, method, endpoint, silent=False, data=None):
        # Order matters: the match-history path also contains
        # "current-summoner", so it has to be matched first.
        if "match-history" in endpoint:
            return FakeResponse(self.history) if self.history else FakeResponse(None, 404)
        if "ranked" in endpoint:
            return FakeResponse(self.ranked) if self.ranked else FakeResponse(None, 404)
        if "current-summoner" in endpoint:
            return FakeResponse(self.summoner) if self.summoner else FakeResponse(None, 404)
        return FakeResponse(None, 404)


class FakeAssets:
    def get_champ_name(self, champ_id):
        return {103: "Ahri", 86: "Garen"}.get(int(champ_id), "")


class FakeDb:
    def __init__(self, rows=None):
        self.rows = rows or []

    def get_recent_matches(self, limit=20):
        return self.rows[:limit]


class RankTests(unittest.TestCase):
    def test_solo_rank_is_read(self):
        entry = parse_rank(RANKED_PAYLOAD, "RANKED_SOLO_5x5")
        self.assertTrue(entry.ranked)
        self.assertEqual(entry.label, "Emerald II · 47 LP")
        self.assertEqual(entry.record, "61W 55L · 53%")

    def test_unranked_says_unranked(self):
        entry = parse_rank(RANKED_PAYLOAD, "RANKED_FLEX_SR")
        self.assertFalse(entry.ranked)
        self.assertEqual(entry.label, "Unranked")
        self.assertIn("No ranked games", entry.record)

    def test_apex_tiers_have_no_division(self):
        payload = {"queueMap": {"Q": {"tier": "CHALLENGER", "division": "I",
                                      "leaguePoints": 1204}}}
        self.assertEqual(parse_rank(payload, "Q").label, "Challenger 1204 LP")

    def test_missing_queue_is_unranked_not_a_crash(self):
        self.assertFalse(parse_rank({}, "RANKED_SOLO_5x5").ranked)


class MatchTests(unittest.TestCase):
    def test_a_game_is_parsed(self):
        match = parse_match(GAME)
        self.assertEqual(match.game_id, 123)
        self.assertEqual(match.champion_id, 103)
        self.assertTrue(match.win)
        self.assertEqual(match.kda, "9/3/14")
        self.assertEqual(match.role, "MIDDLE")

    def test_a_deathless_game_reports_no_ratio_rather_than_infinity(self):
        game = {"participants": [{"stats": {"kills": 5, "deaths": 0,
                                            "assists": 5}}]}
        self.assertIsNone(parse_match(game).kda_ratio)

    def test_garbage_is_skipped(self):
        self.assertIsNone(parse_match(None))
        self.assertIsNotNone(parse_match({}))


class LoadTests(unittest.TestCase):
    def _service(self, **kw):
        return ProfileService(FakeLcu(**kw), FakeAssets(), FakeDb())

    def test_the_client_is_the_source_of_truth(self):
        service = self._service(
            summoner={"gameName": "DPM", "tagLine": "Null",
                      "summonerLevel": 412, "profileIconId": 5},
            ranked=RANKED_PAYLOAD,
            history={"games": {"games": [GAME]}},
        )
        profile = service.load()
        self.assertEqual(profile.summoner_name, "DPM#Null")
        self.assertEqual(profile.level, 412)
        self.assertEqual(profile.solo.label, "Emerald II · 47 LP")
        self.assertTrue(profile.from_client)
        self.assertEqual(profile.matches[0].champion_name, "Ahri")

    def test_the_sample_is_labelled_not_implied(self):
        service = self._service(
            summoner={"gameName": "A", "tagLine": "B"},
            history={"games": {"games": [GAME, GAME]}},
        )
        profile = service.load()
        self.assertEqual(profile.sample_label, "Last 2 recent games")

    def test_local_rows_are_used_but_marked_as_local(self):
        lcu = FakeLcu(summoner={"gameName": "A", "tagLine": "B"})
        db = FakeDb([{"game_id": 1, "champion_id": 86, "win": False,
                      "kills": 1, "deaths": 7, "assists": 2,
                      "duration_s": 900, "timestamp": 1700000000}])
        profile = ProfileService(lcu, FakeAssets(), db).load()

        self.assertFalse(profile.from_client)
        self.assertIn("recorded locally", profile.sample_label)
        self.assertEqual(profile.matches[0].champion_name, "Garen")

    def test_a_disconnected_client_says_so(self):
        profile = ProfileService(FakeLcu(connected=False), FakeAssets(), FakeDb()).load()
        self.assertEqual(profile.matches, [])
        self.assertIn("Connect the League Client", profile.error)

    def test_no_games_anywhere_is_an_empty_profile_not_an_invention(self):
        profile = self._service(summoner={"gameName": "A", "tagLine": "B"}).load()
        self.assertEqual(profile.matches, [])
        self.assertEqual(profile.sample_label, "No games loaded")

    def test_an_unknown_champion_stays_a_number_rather_than_a_guess(self):
        game = dict(GAME)
        game["participants"] = [{"championId": 9999, "stats": {"win": True}}]
        service = self._service(
            summoner={"gameName": "A", "tagLine": "B"},
            history={"games": {"games": [game]}},
        )
        self.assertEqual(service.load().matches[0].champion_name, "9999")


if __name__ == "__main__":
    unittest.main()
