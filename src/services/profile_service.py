"""
Your actual profile, from the League Client.

The profile screen read only the local SQLite `matches` table — rows written
by the automation loop's end-of-game handler, capped at 20, and (because the
engine was never started in the Qt shell) almost always empty. It then
presented that as your record.

The client already knows all of this. `/lol-match-history/...` returns your
real games; `/lol-ranked/v1/current-ranked-stats` returns your real rank.

Everything here is a read. The local database is still useful for games this
app was present for, but it is a supplement, not the source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from utils.logger import Logger

MATCH_HISTORY_ENDPOINT = (
    "/lol-match-history/v1/products/lol/current-summoner/matches"
    "?begIndex={beg}&endIndex={end}"
)
RANKED_ENDPOINT = "/lol-ranked/v1/current-ranked-stats"
SUMMONER_ENDPOINT = "/lol-summoner/v1/current-summoner"

#: Riot's internal queue ids for the ranked ladders.
SOLO_QUEUE = "RANKED_SOLO_5x5"
FLEX_QUEUE = "RANKED_FLEX_SR"

TIER_LABELS = {
    "IRON": "Iron", "BRONZE": "Bronze", "SILVER": "Silver", "GOLD": "Gold",
    "PLATINUM": "Platinum", "EMERALD": "Emerald", "DIAMOND": "Diamond",
    "MASTER": "Master", "GRANDMASTER": "Grandmaster", "CHALLENGER": "Challenger",
}


@dataclass(frozen=True)
class Match:
    """One game, as the client reports it."""

    game_id: int = 0
    champion_id: int = 0
    champion_name: str = ""
    queue_id: int = 0
    win: bool = False
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    duration_s: int = 0
    timestamp_ms: int = 0
    role: str = ""

    @property
    def kda(self) -> str:
        return "{}/{}/{}".format(self.kills, self.deaths, self.assists)

    @property
    def kda_ratio(self) -> Optional[float]:
        """None on a deathless game rather than a fake infinity."""
        if self.deaths == 0:
            return None
        return (self.kills + self.assists) / self.deaths


@dataclass(frozen=True)
class RankEntry:
    queue: str = ""
    tier: str = ""
    division: str = ""
    league_points: int = 0
    wins: int = 0
    losses: int = 0

    @property
    def ranked(self) -> bool:
        return bool(self.tier) and self.tier.upper() != "NONE"

    @property
    def label(self) -> str:
        if not self.ranked:
            return "Unranked"
        tier = TIER_LABELS.get(self.tier.upper(), self.tier.title())
        # Apex tiers have no division worth showing.
        if self.tier.upper() in ("MASTER", "GRANDMASTER", "CHALLENGER"):
            return "{} {} LP".format(tier, self.league_points)
        division = (self.division or "").upper()
        if division in ("NA", ""):
            return "{} {} LP".format(tier, self.league_points)
        return "{} {} · {} LP".format(tier, division, self.league_points)

    @property
    def record(self) -> str:
        total = self.wins + self.losses
        if not total:
            return "No ranked games this split"
        return "{}W {}L · {:.0f}%".format(
            self.wins, self.losses, 100.0 * self.wins / total
        )


@dataclass
class Profile:
    """Everything the profile screen needs, plus how much of it is real."""

    summoner_name: str = ""
    level: int = 0
    profile_icon_id: int = 0
    solo: RankEntry = field(default_factory=RankEntry)
    flex: RankEntry = field(default_factory=RankEntry)
    matches: List[Match] = field(default_factory=list)
    #: True when the match list came from the client rather than a local cache.
    from_client: bool = False
    error: str = ""

    @property
    def sample_label(self) -> str:
        """
        Say what the numbers are computed from.

        The old screen showed champion win rates from at most 20 locally
        recorded games and called it your record.
        """
        if not self.matches:
            return "No games loaded"
        source = "recent games" if self.from_client else "games recorded locally"
        return "Last {} {}".format(len(self.matches), source)


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_match(game: Dict[str, Any]) -> Optional[Match]:
    """
    Parse one entry from the client's match history.

    The player's own row is in `participants[0]` for this endpoint, because
    the client returns match history already scoped to the current summoner.
    """
    if not isinstance(game, dict):
        return None
    participants = game.get("participants") or []
    me = participants[0] if participants else {}
    if not isinstance(me, dict):
        me = {}
    stats = me.get("stats") or {}

    identities = game.get("participantIdentities") or []
    role = str(me.get("timeline", {}).get("role") or "") if isinstance(
        me.get("timeline"), dict
    ) else ""
    lane = str(me.get("timeline", {}).get("lane") or "") if isinstance(
        me.get("timeline"), dict
    ) else ""

    return Match(
        game_id=_int(game.get("gameId")),
        champion_id=_int(me.get("championId")),
        queue_id=_int(game.get("queueId")),
        win=bool(stats.get("win")),
        kills=_int(stats.get("kills")),
        deaths=_int(stats.get("deaths")),
        assists=_int(stats.get("assists")),
        duration_s=_int(game.get("gameDuration")),
        timestamp_ms=_int(game.get("gameCreation")),
        role=lane or role,
    )


def parse_rank(payload: Dict[str, Any], queue: str) -> RankEntry:
    """Pull one ladder out of `/lol-ranked/v1/current-ranked-stats`."""
    queues = (payload or {}).get("queueMap") or {}
    entry = queues.get(queue) or {}
    return RankEntry(
        queue=queue,
        tier=str(entry.get("tier") or ""),
        division=str(entry.get("division") or ""),
        league_points=_int(entry.get("leaguePoints")),
        wins=_int(entry.get("wins")),
        losses=_int(entry.get("losses")),
    )


class ProfileService:
    """Reads the profile from the client, with a local-database fallback."""

    def __init__(self, lcu: Any, assets: Any = None, db: Any = None):
        self._lcu = lcu
        self._assets = assets
        self._db = db

    # ------------------------------------------------------------- plumbing
    def _get(self, endpoint: str):
        if not getattr(self._lcu, "is_connected", False):
            return None
        try:
            res = self._lcu.request("GET", endpoint, silent=True)
        except Exception as exc:
            Logger.debug("Profile", f"{endpoint} raised {exc}")
            return None
        if res is None or getattr(res, "status_code", 0) != 200:
            return None
        try:
            return res.json()
        except Exception:
            return None

    def _champ_name(self, champion_id: int) -> str:
        getter = getattr(self._assets, "get_champ_name", None)
        if callable(getter):
            try:
                name = getter(champion_id)
                if name:
                    return str(name)
            except Exception as exc:
                Logger.debug("ProfileService", "_champ_name suppressed an error", exc=exc)
        # A bare id is honest; inventing a name is not.
        return str(champion_id) if champion_id else ""

    # ---------------------------------------------------------------- reads
    def load(self, limit: int = 20) -> Profile:
        profile = Profile()

        summoner = self._get(SUMMONER_ENDPOINT) or {}
        game_name = str(summoner.get("gameName") or "").strip()
        tag_line = str(summoner.get("tagLine") or "").strip()
        profile.summoner_name = (
            "{}#{}".format(game_name, tag_line) if game_name and tag_line
            else game_name or str(summoner.get("displayName") or "")
        )
        profile.level = _int(summoner.get("summonerLevel"))
        profile.profile_icon_id = _int(summoner.get("profileIconId"))

        ranked = self._get(RANKED_ENDPOINT)
        if ranked:
            profile.solo = parse_rank(ranked, SOLO_QUEUE)
            profile.flex = parse_rank(ranked, FLEX_QUEUE)

        history = self._get(
            MATCH_HISTORY_ENDPOINT.format(beg=0, end=max(1, limit) - 1)
        )
        games = ((history or {}).get("games") or {}).get("games") or []
        matches = []
        for game in games:
            match = parse_match(game)
            if match is None:
                continue
            matches.append(
                Match(**{**match.__dict__,
                         "champion_name": self._champ_name(match.champion_id)})
            )

        if matches:
            profile.matches = matches
            profile.from_client = True
            return profile

        # Fall back to what this app recorded itself, and say so.
        profile.matches = self._from_database(limit)
        profile.from_client = False
        if not profile.matches:
            profile.error = (
                "No match history available. Connect the League Client to load "
                "your recent games."
                if not getattr(self._lcu, "is_connected", False)
                else "The client returned no recent games."
            )
        return profile

    def _from_database(self, limit: int) -> List[Match]:
        if self._db is None:
            return []
        try:
            rows = self._db.get_recent_matches(limit=limit) or []
        except Exception:
            return []

        out = []
        for row in rows:
            out.append(
                Match(
                    game_id=_int(row.get("game_id")),
                    champion_id=_int(row.get("champion_id")),
                    champion_name=str(row.get("champion_name") or "")
                    or self._champ_name(_int(row.get("champion_id"))),
                    queue_id=_int(row.get("queue_id")),
                    win=bool(row.get("win")),
                    kills=_int(row.get("kills")),
                    deaths=_int(row.get("deaths")),
                    assists=_int(row.get("assists")),
                    duration_s=_int(row.get("duration_s")),
                    timestamp_ms=_int(float(row.get("timestamp") or 0) * 1000),
                    role=str(row.get("role") or ""),
                )
            )
        return out
