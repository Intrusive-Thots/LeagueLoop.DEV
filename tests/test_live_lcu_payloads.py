"""Behaviour against LCU payloads recorded from a live client (anonymised).

Fixtures in tests/fixtures/lcu were captured read-only (GET) from James's
client on 2026-10-22 with names, ids and status text scrubbed.
"""
import json
import os

from services import friend_presence as fp

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "lcu")


def _load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def test_live_friends_have_no_availability_message_field():
    friends = _load("friends.json")
    assert friends and all("availabilityMessage" not in f for f in friends)
    assert any("statusMessage" in f for f in friends)


def test_live_presence_kinds():
    online = [f for f in _load("friends.json") if fp.is_online(f)]
    described = [fp.describe(f) for f in online]
    texts = {t for _, t in described}
    assert "On mobile" in texts
    assert "In game" in texts
    assert "In lobby" in texts
    assert "Playing VALORANT" in texts
    assert "In Riot Client" in texts
    for kind, _ in described:
        assert kind in fp.COLORS


def test_live_invitable_excludes_mobile_other_games_and_in_game():
    friends = _load("friends.json")
    inv = [f for f in friends if fp.is_invitable(f)]
    online = [f for f in friends if fp.is_online(f)]
    assert 0 < len(inv) < len(online)
    for f in inv:
        assert f["availability"] not in ("offline", "mobile")
        assert f["product"] == "league_of_legends"
        assert f["lol"].get("gameStatus") != "inGame"


def test_mass_invite_skips_uninvitable(monkeypatch):
    from unittest.mock import MagicMock
    from services.automation import AutomationEngine
    friends = _load("friends.json")
    # Give every friend a summoner id so only presence decides.
    for i, f in enumerate(friends, 1):
        f["summonerId"] = i
    eng = AutomationEngine.__new__(AutomationEngine)
    eng._log = lambda *a, **k: None
    eng._last_mass_invite = 0
    eng.config = MagicMock()
    eng.config.get.return_value = ""
    get = MagicMock(status_code=200)
    get.json.return_value = friends
    post = MagicMock(status_code=204)
    eng.lcu = MagicMock()
    eng.lcu.request.side_effect = lambda m, *a, **k: get if m == "GET" else post
    count = eng.mass_invite_friends()
    expected = sum(1 for f in friends if fp.is_invitable(f))
    assert count == expected
    posted = eng.lcu.request.call_args_list[-1][0][2]
    assert len(posted) == expected


def test_season_pass_with_nothing_unclaimed_is_not_claimed():
    """Live run logged 'Claimed 1 reward(s)' per event on every click."""
    from unittest.mock import MagicMock
    from services.loot_service import LootService
    calls = []

    class R:
        def __init__(self, code, body):
            self.status_code, self._b = code, body
            self.text = json.dumps(body)

        def json(self):
            return self._b

    def req(method, endpoint, data=None, silent=False):
        calls.append((method, endpoint))
        if endpoint == "/lol-event-hub/v1/events":
            return R(200, [{"id": "ev1", "name": "Pass"}])
        if endpoint.endswith("/unclaimed-rewards"):
            return R(200, {"rewardsCount": 0})
        return R(204, {})

    lcu = MagicMock()
    lcu.request.side_effect = req
    svc = LootService(lcu, log=lambda *a, **k: None)
    res = svc.claim_season_pass_rewards()
    assert res.claimed == 0
    assert not any(m == "POST" for m, _ in calls)
