"""
Every configuration key, in one place.

The UI and the automation engine disagreed on key names, silently. The Bans
screen wrote `ban_list`; the engine read `ban_priority`. The ARAM screen wrote
`aram_priority_list`; the engine read `priority_list` and nothing else. Both
screens therefore did nothing at all, with no error and no clue — you would
configure a ban list, watch auto-ban never ban it, and reasonably conclude the
automation was broken rather than the wiring.

Two independent string literals in two files cannot be kept in step by
discipline. Import from here on both sides so a rename is a rename, and add a
test that every key the UI writes is read by something.
"""
from __future__ import annotations

from typing import List

# --- champion lists ------------------------------------------------------
#: Pick priority for Summoner's Rift, most wanted first.
PRIORITY_LIST = "priority_list"
#: Per-role override, e.g. priority_MIDDLE. Falls back to PRIORITY_LIST.
PRIORITY_ROLE_PREFIX = "priority_"
#: Pick priority used in ARAM.
ARAM_PRIORITY_LIST = "aram_priority_list"
#: Champions to ban, most wanted first.
BAN_LIST = "ban_list"
#: Champions marked as favourites. Ids, unordered — a set, not a ranking.
FAVORITE_CHAMPIONS = "favorite_champions"
#: Per-role ban override, e.g. ban_priority_TOP.
BAN_ROLE_PREFIX = "ban_priority_"

# --- automation ----------------------------------------------------------
AUTOMATION_MASTER = "automation_master"
AUTO_ACCEPT = "auto_accept"
AUTO_LOCK_IN = "auto_lock_in"
AUTO_HOVER = "auto_hover"
AUTO_BAN_ENABLED = "auto_ban_enabled"
AUTO_REQUEUE = "auto_requeue"
AUTO_RANDOM_SKIN = "auto_random_skin"
#: Skip banning a champion a teammate is hovering.
AUTO_BAN_RESPECT_HOVERS = "auto_ban_respect_hovers"

#: Auto-join a friend's lobby, and whose lobbies count.
AUTO_JOIN_ENABLED = "auto_join_enabled"
AUTO_JOIN_LIST = "auto_join_list"
#: Honor a teammate after the game, and how the target is chosen.
AUTO_HONOR_ENABLED = "auto_honor_enabled"
HONOR_STRATEGY = "honor_strategy"
#: Click through the post-game screens.
SKIP_STATS_ENABLED = "skip_stats_enabled"
#: ARAM: swap to a higher-priority champion from the bench, and reroll.
ARAM_BENCH_SWAP = "aram_bench_swap"
ARAM_AUTO_REROLL = "aram_auto_reroll"
#: Watch lobby chat for abuse and warn. Off by default: it reads every
#: message in the lobby, which the user should opt into knowingly.
CHAT_WARDEN_ENABLED = "chat_warden_enabled"
#: Leave the draft when a named player is on your team. This force-closes
#: the League Client, so it is gated on its own switch as well as the list.
DODGE_BLACKLIST_ENABLED = "dodge_blacklist_enabled"
DODGE_BLACKLIST = "dodge_blacklist"

# --- shell ---------------------------------------------------------------
QT_LAST_TAB = "qt_last_tab"
RUN_IN_TRAY = "run_in_tray"
#: Keep the window pinned above the League Client, which raises itself when a
#: lobby or a draft starts.
ALWAYS_ON_TOP = "always_on_top"
#: Follow the League Client's window: move with it, hide when it minimises,
#: come back when it restores. Off means the window stays where it was put.
ATTACH_TO_CLIENT = "attach_to_client"
#: Which side of the client the companion prefers to sit on.
COMPANION_SIDE = "companion_side"


def role_priority_key(role: str) -> str:
    """Per-role pick priority key, or the general one when role is unknown."""
    role = (role or "").strip().upper()
    return "{}{}".format(PRIORITY_ROLE_PREFIX, role) if role else PRIORITY_LIST


def role_ban_key(role: str) -> str:
    """Per-role ban key, or the general ban list when role is unknown."""
    role = (role or "").strip().upper()
    return "{}{}".format(BAN_ROLE_PREFIX, role) if role else BAN_LIST


def read_champion_ids(config, key: str) -> List[int]:
    """
    Read a champion-id list, tolerating the string ids older configs stored.

    Returns [] rather than raising: a malformed entry should cost you that
    entry, not the whole list.
    """
    if config is None:
        return []
    try:
        raw = config.get(key, []) or []
    except Exception:
        return []

    out: List[int] = []
    for item in raw:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value > 0:
            out.append(value)
    return out
