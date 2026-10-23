"""Friend presence, read from the real ``/lol-chat/v1/friends`` payload.

Recorded against a live client (tests/fixtures/lcu/friends.json). What the
payload actually carries, and the old code missed:

* ``availability`` is one of chat / away / dnd / mobile / offline. ``mobile``
  means the Riot Mobile app: online, but cannot join a lobby.
* ``product`` is the Riot game they are in. A friend can be ``dnd`` because
  they are in VALORANT, or ``away`` in the bare Riot Client.
* ``lol.gameStatus`` (outOfGame / inGame / championSelect / inQueue /
  hosting_<QUEUE>) says what they are doing in League.
* There is no ``availabilityMessage`` field; the free text is
  ``statusMessage``.
"""

LEAGUE = "league_of_legends"

COLORS = {
    "chat": "#2ECC71",     # online
    "away": "#E0A43A",     # away
    "ingame": "#4FA3E0",   # in game / champ select / queue (League's blue)
    "other": "#8A93A0",    # another Riot game, or mobile
    "offline": "#5B6573",
}

_GAME_STATUS = {
    "inGame": "In game",
    "championSelect": "In champ select",
    "inQueue": "In queue",
    "spectating": "Spectating",
}


def describe(friend):
    """Return ``(kind, status_text)`` for one friend dict.

    ``kind`` is a key of :data:`COLORS`.
    """
    avail = (friend.get("availability") or "offline").lower()
    if avail == "offline":
        return "offline", "Offline"
    if avail == "mobile":
        return "other", "On mobile"
    product = friend.get("product") or LEAGUE
    if product != LEAGUE:
        name = friend.get("productName") or ""
        if product == "riot_client" or not name:
            return "other", "In Riot Client"
        return "other", f"Playing {name}"
    lol = friend.get("lol") or {}
    status = lol.get("gameStatus") or ""
    if status in _GAME_STATUS:
        return "ingame", _GAME_STATUS[status]
    if status.startswith("hosting_"):
        return ("away" if avail == "away" else "chat"), "In lobby"
    msg = (friend.get("statusMessage") or "").strip()
    if avail == "away":
        return "away", msg or "Away"
    if avail == "dnd":
        return "ingame", msg or "Busy"
    return "chat", msg or "Online"


def is_online(friend):
    """Online on any device (what the friend-count badge used to show)."""
    return (friend.get("availability") or "offline").lower() != "offline"


def is_invitable(friend):
    """Signed in to the League client, so a lobby invite can reach them.

    Mobile users and friends in another Riot game or the bare Riot Client
    cannot accept a League lobby invite, and neither can someone already in a
    game, champ select or queue.
    """
    avail = (friend.get("availability") or "offline").lower()
    if avail in ("offline", "mobile"):
        return False
    if (friend.get("product") or LEAGUE) != LEAGUE:
        return False
    return (friend.get("lol") or {}).get("gameStatus") not in _GAME_STATUS
