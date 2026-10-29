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


# --- 2026-10-29 ARAM: Mayhem draft (queue 2400, gameMode KIWI), read-only GETs ---

def test_live_tft_pass_has_nothing_claimable_and_sends_no_put():
    from unittest.mock import MagicMock
    from services.loot_service import LootService
    passes = _load("tft_active_passes.json")
    statuses = {m["status"] for p in passes for m in p["milestones"]}
    assert "REWARDABLE" in statuses  # the premium, locked level-0 reward

    class R:
        status_code = 200
        content = b"[]"
        def json(self):
            return passes
    lcu = MagicMock(is_connected=True)
    lcu.request.side_effect = lambda m, e, **k: R() if m == "GET" else None
    res = LootService(lcu, log=lambda *_: None).claim_tft_pass_rewards()
    assert res.claimed == 0
    assert all(c.args[0] == "GET" for c in lcu.request.call_args_list)


def test_live_champ_select_timer_is_a_stale_snapshot():
    from services.draft.timer import phase_time_left_ms
    a = _load("champ_select_aram_mayhem_stale_a.json")
    b = _load("champ_select_aram_mayhem_stale_b.json")
    # Read 9 s apart, identical timer: the LCU did not refresh it.
    assert a["timer"] == b["timer"]
    t = a["timer"]
    stamp = t["internalNowInEpochMs"]
    assert phase_time_left_ms(t, now_ms=stamp + 2_000) == t["adjustedTimeLeftInPhase"] - 2_000
    assert phase_time_left_ms(t, now_ms=stamp + 11_000) == t["adjustedTimeLeftInPhase"] - 11_000
    assert phase_time_left_ms(t, now_ms=stamp + 60_000) == 0  # 30 s phase, long over


def test_timer_ignores_implausible_skew_and_missing_fields():
    from services.draft.timer import phase_time_left_ms
    t = {"adjustedTimeLeftInPhase": 9000, "internalNowInEpochMs": 10_000, "totalTimeInPhase": 30000}
    assert phase_time_left_ms(t, now_ms=5_000) == 9000        # clock behind the stamp
    assert phase_time_left_ms(t, now_ms=10_000 + 10**7) == 9000  # absurd age
    assert phase_time_left_ms({}, default=15000) == 15000
    assert phase_time_left_ms({"timeLeftInPhase": 4000}) == 4000
    assert phase_time_left_ms({"isInfinite": True, "adjustedTimeLeftInPhase": 5}, default=7) == 7


def test_live_aram_mayhem_draft_shape():
    s = _load("champ_select_aram_mayhem_after_swap.json")
    g = _load("gameflow_session_champ_select.json")
    assert s["queueId"] == 2400 and g["gameData"]["queue"]["gameMode"] == "KIWI"
    assert s["benchEnabled"] and len(s["benchChampions"]) == 8
    # No in-progress pick in Mayhem: every pick action is pre-completed.
    acts = [a for row in s["actions"] for a in row]
    assert acts and all(a["completed"] and not a["isInProgress"] for a in acts)
    me = next(p for p in s["myTeam"] if p["cellId"] == s["localPlayerCellId"])
    # After a bench swap the intent is cleared; championId carries the pick.
    assert me["championId"] and me["championPickIntent"] == 0
    assert all(not p["gameName"] and not p["puuid"] and not p["summonerId"] for p in s["myTeam"])


def test_live_champ_select_publishes_aged_timer_and_my_pick():
    from unittest.mock import MagicMock
    from services.client_state_service import ClientStateService
    s = _load("champ_select_aram_mayhem_after_swap.json")
    svc = ClientStateService.__new__(ClientStateService)
    svc._state = MagicMock()
    svc._pickable_loaded = True
    svc._pickable_ids = ()
    svc._get_json = lambda ep: s
    import services.draft.timer as tm
    real = tm.time.time
    tm.time.time = lambda: (s["timer"]["internalNowInEpochMs"] + 5_000) / 1000.0
    try:
        svc._read_and_publish_champ_select()
    finally:
        tm.time.time = real
    kw = svc._state.update_champ_select.call_args.kwargs
    me = next(p for p in s["myTeam"] if p["cellId"] == s["localPlayerCellId"])
    assert kw["selected_champion_id"] == me["championId"]
    assert kw["queue_id"] == 2400
    assert kw["locked_in"] is True
    assert abs(kw["timer_remaining_s"] - (s["timer"]["adjustedTimeLeftInPhase"] - 5_000) / 1000.0) < 1e-6


def test_live_aram_bench_highlight_state(monkeypatch):
    """The sidebar hands the ARAM list exactly the draft's bench / you / team."""
    from types import SimpleNamespace
    from ui.components.aram_list_window import AramListWindow
    from ui.app_sidebar import SidebarWidget
    s = _load("champ_select_aram_mayhem_after_swap.json")
    me = next(p for p in s["myTeam"] if p["cellId"] == s["localPlayerCellId"])
    got = {}
    monkeypatch.setattr(AramListWindow, "update_champ_select_state",
                        classmethod(lambda cls, b, m, t: got.update(bench=b, me=m, team=t)))
    fake = SimpleNamespace(
        winfo_exists=lambda: True,
        assets=SimpleNamespace(get_champ_name=lambda cid: f"C{cid}"),
        master=None,
    )
    SidebarWidget.update_lobby_stats(fake, s["myTeam"], s["benchChampions"], me, s)
    assert got["me"] == f"C{me['championId']}"
    assert got["bench"] == [f"C{b['championId']}" for b in s["benchChampions"]]
    assert sorted(got["team"]) == sorted(f"C{p['championId']}" for p in s["myTeam"] if p is not me)
