---
name: Resolve Riot ID
description: Convert between Riot ID (Name#Tag), PUUID, and summonerId using account-v1 and summoner-v4 endpoints
---

# Resolve Riot ID

## Overview
Riot uses multiple identifier systems. This skill covers the full resolution chain for converting between player identifiers — essential for any feature that needs to look up player data from a name, PUUID, or summonerId.

## ID Types Quick Reference

| ID | Example | Scope | Mutable? |
|----|---------|-------|----------|
| **Riot ID** | `PlayerName#NA1` | Global display name | Yes (changeable) |
| **PUUID** | `a1b2c3d4-...` (78 chars) | Global, cross-game | No (permanent) |
| **summonerId** | `encrypted string` | Per-region, per-API-key | Changes on transfer |
| **accountId** | `encrypted string` | Per-region | **Obsolete** — don't use |

## Resolution Chains

### Riot ID → PUUID (Regional routing, account-v1)
```
GET https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
```
```json
{
  "puuid": "a1b2c3d4-...",
  "gameName": "PlayerName",
  "tagLine": "NA1"
}
```

### PUUID → Riot ID (Regional routing, account-v1)
```
GET https://{region}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}
```
Same response as above.

### PUUID → summonerId (Platform routing, summoner-v4)
```
GET https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}
```
```json
{
  "id": "encrypted_summoner_id",
  "accountId": "encrypted_account_id",
  "puuid": "a1b2c3d4-...",
  "profileIconId": 4834,
  "revisionDate": 1672531200000,
  "summonerLevel": 350
}
```

## Full Chain: Name → Rank
```python
def get_rank_by_name(self, game_name: str, tag_line: str) -> dict:
    """Resolve Riot ID to ranked data through the full ID chain."""
    if not self.riot_api:
        return {}

    # Step 1: Riot ID → PUUID (regional)
    resp = self.riot_api.regional_request(
        f"/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    )
    if not resp or resp.status_code != 200:
        return {}
    puuid = resp.json().get("puuid")

    # Step 2: PUUID → summonerId (platform)
    resp = self.riot_api.platform_request(
        f"/lol/summoner/v4/summoners/by-puuid/{puuid}"
    )
    if not resp or resp.status_code != 200:
        return {}
    summoner_id = resp.json().get("id")

    # Step 3: summonerId → rank (platform)
    resp = self.riot_api.platform_request(
        f"/lol/league/v4/entries/by-summoner/{summoner_id}"
    )
    if not resp or resp.status_code != 200:
        return {}

    return resp.json()
```

## LCU Shortcuts (No API Key Needed)
When the League Client is connected, you can skip the Riot Web API entirely:

```python
# Get current summoner's PUUID
me = self.lcu.request("GET", "/lol-summoner/v1/current-summoner")
puuid = me.json().get("puuid")

# Get any summoner by summonerId (LCU uses its own encryption)
summoner = self.lcu.request("GET", f"/lol-summoner/v1/summoners/{summoner_id}")

# Get ranked stats by PUUID
ranked = self.lcu.request("GET", f"/lol-ranked/v1/ranked-stats/{puuid}")

# Resolve display name from PUUID
name = self.lcu.request("GET", f"/lol-summoner/v2/summoners/puuid/{puuid}")
```

## Important Caveats

### Encryption is Per-API-Key
A summonerId encrypted with API key A **will not work** with API key B. The encryption changes when you regenerate your key. However, PUUID is consistent across all keys.

### Regional vs Platform
- **account-v1** and **match-v5** use **regional** routing (`americas`, `europe`, `asia`, `sea`)
- **summoner-v4**, **league-v4**, **spectator-v4** use **platform** routing (`na1`, `euw1`, `kr`)
- Getting this wrong returns 404

### Name Changes
Riot IDs (gameName#tagLine) can change. Always store PUUID as the persistent identifier and resolve the display name on-demand.

## Notes
- PUUID works across games — a player's LoL and Valorant PUUIDs are identical (same Riot account).
- The `tagLine` is case-insensitive but the `gameName` portion preserves casing in responses.
- Some old endpoints still accept `accountId` but Riot is deprecating it. Use PUUID.
