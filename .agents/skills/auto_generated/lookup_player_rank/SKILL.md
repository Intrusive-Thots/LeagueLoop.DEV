---
name: Look Up Player Rank
description: Fetch and display a summoner's ranked tier, division, LP, and win rate using the Riot Games league-v4 API
---

# Look Up Player Rank

## Overview
Retrieve ranked information for any player using their encrypted summonerId via the `league-v4` endpoint. This is useful for displaying teammate ranks during champ select or showing lobby rank breakdowns.

## Prerequisites
- A valid Riot API key stored in `config.json` as `"riot_api_key"`
- The `RiotAPIClient` from the `riot_web_api` skill must be wired up
- You need the player's **encrypted summonerId** (not PUUID) — get it via summoner-v4

## ID Resolution Chain
```
Riot ID (Name#Tag) → account-v1 → PUUID → summoner-v4 → summonerId → league-v4 → Rank
```
Or from LCU (no API key needed):
```
LCU /lol-summoner/v1/summoners/{summonerId} → summonerId (already encrypted for LCU)
```

## Endpoint
```
GET https://{platform}.api.riotgames.com/lol/league/v4/entries/by-summoner/{encryptedSummonerId}
```

## Response
Array of `LeagueEntryDTO[]` — one per ranked queue. Empty `[]` = unranked.
```json
[
  {
    "leagueId": "cb92okpj-feiwo3-442",
    "queueType": "RANKED_SOLO_5x5",
    "tier": "GOLD",
    "rank": "II",
    "summonerId": "encrypted...",
    "leaguePoints": 75,
    "wins": 120,
    "losses": 100,
    "veteran": false,
    "inactive": false,
    "freshBlood": false,
    "hotStreak": true,
    "miniSeries": null
  },
  {
    "queueType": "RANKED_FLEX_SR",
    "tier": "SILVER",
    "rank": "I",
    "leaguePoints": 100,
    "wins": 30,
    "losses": 25,
    "miniSeries": {
      "target": 3,
      "wins": 2,
      "losses": 1,
      "progress": "WLWN"
    }
  }
]
```

## Queue Types
| queueType | Mode |
|-----------|------|
| `RANKED_SOLO_5x5` | Solo/Duo |
| `RANKED_FLEX_SR` | Flex 5v5 |
| `RANKED_TFT` | TFT |
| `RANKED_TFT_DOUBLE_UP` | TFT Double Up |

## Implementation Example

```python
def get_player_rank(self, summoner_id: str) -> dict:
    """Fetch ranked data for a summoner. Returns dict with solo/flex entries."""
    if not self.riot_api:
        return {}

    resp = self.riot_api.platform_request(
        f"/lol/league/v4/entries/by-summoner/{summoner_id}"
    )
    if not resp or resp.status_code != 200:
        return {}

    entries = resp.json()
    result = {}
    for entry in entries:
        queue = entry.get("queueType", "")
        tier = entry.get("tier", "UNRANKED")
        rank = entry.get("rank", "")
        lp = entry.get("leaguePoints", 0)
        wins = entry.get("wins", 0)
        losses = entry.get("losses", 0)
        total = wins + losses
        wr = round(wins / total * 100, 1) if total > 0 else 0.0

        result[queue] = {
            "tier": tier,
            "rank": rank,
            "lp": lp,
            "wins": wins,
            "losses": losses,
            "winrate": wr,
            "hot_streak": entry.get("hotStreak", False),
            "display": f"{tier.capitalize()} {rank} ({lp} LP) — {wr}% WR"
        }
    return result
```

## Display Format
```python
def format_rank(rank_data: dict) -> str:
    solo = rank_data.get("RANKED_SOLO_5x5")
    if solo:
        return solo["display"]  # "Gold II (75 LP) — 54.5% WR"
    return "Unranked"
```

## Tier Order (for sorting)
```python
TIER_ORDER = {
    "IRON": 0, "BRONZE": 1, "SILVER": 2, "GOLD": 3,
    "PLATINUM": 4, "EMERALD": 5, "DIAMOND": 6,
    "MASTER": 7, "GRANDMASTER": 8, "CHALLENGER": 9
}
RANK_ORDER = {"IV": 0, "III": 1, "II": 2, "I": 3}
```

## Notes
- Riot API summonerId ≠ LCU summonerId. They use different encryption contexts.
- For LCU-only rank lookups (no API key), you can use:
  ```
  GET /lol-ranked/v1/ranked-stats/{puuid}
  ```
  This LCU endpoint works without a Riot API key but only when the client is connected.
- Historical rank data is NOT available — you must track LP before/after games yourself.
- After a rank reset (new season), entries may return empty until placement games are finished.
