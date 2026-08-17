"""Tests for centralized Riot ID resolution."""
from utils.riot_id import resolve_riot_id, resolve_riot_id_lower


def test_game_name_and_tag():
    assert resolve_riot_id({"gameName": "Foo", "tagLine": "NA1"}) == "Foo#NA1"


def test_game_name_only():
    assert resolve_riot_id({"gameName": "Foo"}) == "Foo"


def test_display_name_fallback():
    assert resolve_riot_id({"displayName": "OldName"}) == "OldName"


def test_summoner_name_fallback():
    assert resolve_riot_id({"summonerName": "Legacy"}) == "Legacy"


def test_name_fallback():
    assert resolve_riot_id({"name": "Plain"}) == "Plain"


def test_preference_order():
    data = {
        "gameName": "A",
        "tagLine": "B",
        "displayName": "D",
        "summonerName": "S",
        "name": "N",
    }
    assert resolve_riot_id(data) == "A#B"


def test_empty_and_none():
    assert resolve_riot_id(None) == ""
    assert resolve_riot_id({}) == ""
    assert resolve_riot_id(None, fallback="x") == "x"


def test_lower():
    assert resolve_riot_id_lower({"gameName": "Foo", "tagLine": "NA1"}) == "foo#na1"
