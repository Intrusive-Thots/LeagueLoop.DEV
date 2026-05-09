---
name: Add Riot Web API Call
description: Integrate a Riot Games public REST API endpoint into LeagueLoop (spectator, league, match, account — separate from the local LCU API)
---

# Add Riot Web API Call

## Context
LeagueLoop currently talks to the **local LCU API** (localhost via lockfile). The **Riot Web API** is the public REST API at `{platform}.api.riotgames.com` that provides data the LCU doesn't expose: match history, spectator data, ranked info, and cross-region account lookups. These require a **Riot API key**.

> **Key Difference**: LCU = local client data (champ select, lobby). Riot Web API = remote server data (ranks, match history, spectator).

## API Key Requirement
All Riot Web API calls require an API key in the `X-Riot-Token` header:
```
X-Riot-Token: RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```
- **Development keys** expire every 24 hours — fine for testing
- **Production keys** require a Riot-approved application
- Store the key in `config.json` as `"riot_api_key": ""`

## Routing

### Platform Routing (Game-specific endpoints)
Used for: summoner-v4, league-v4, spectator-v4, champion-mastery
```
https://{platform}.api.riotgames.com/lol/...
```
| Platform | Region |
|----------|--------|
| `na1` | North America |
| `euw1` | EU West |
| `eun1` | EU Nordic & East |
| `kr` | Korea |
| `br1` | Brazil |
| `la1` | Latin America North |
| `la2` | Latin America South |
| `oc1` | Oceania |
| `tr1` | Turkey |
| `ru` | Russia |
| `jp1` | Japan |
| `ph2` | Philippines |
| `sg2` | Singapore |
| `th2` | Thailand |
| `tw2` | Taiwan |
| `vn2` | Vietnam |

### Regional Routing (Account & match endpoints)
Used for: account-v1, match-v5
```
https://{region}.api.riotgames.com/...
```
| Region | Covers |
|--------|--------|
| `americas` | NA, BR, LAN, LAS, OCE |
| `europe` | EUW, EUNE, TR, RU |
| `asia` | KR, JP |
| `sea` | PH, SG, TH, TW, VN |

## Player ID Types

| ID | Format | Scope | Used By |
|----|--------|-------|---------|
| **PUUID** | 78-char string | Global, cross-game (LoL + Valorant) | All modern endpoints, LCU |
| **summonerId** | Encrypted string | Per-region, changes on transfer | league-v4, spectator-v4 |
| **accountId** | Encrypted string | Per-region | Obsolete — avoid |

> PUUID is the future. All new endpoints use it exclusively.

## Steps to Integrate

### 1. Add a Riot API client class
Create `services/riot_api.py`:
```python
import requests
from utils.logger import Logger

class RiotAPIClient:
    """Client for the Riot Games public REST API."""

    BASE = "https://{routing}.api.riotgames.com"

    def __init__(self, api_key: str, platform: str = "na1", region: str = "americas"):
        self.api_key = api_key
        self.platform = platform
        self.region = region
        self.session = requests.Session()
        self.session.headers["X-Riot-Token"] = api_key

    def _request(self, routing: str, path: str, silent: bool = False):
        url = f"{self.BASE.format(routing=routing)}{path}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                Logger.warning("RiotAPI", f"Rate limited. Retry after {retry_after}s")
                return None
            if resp.status_code != 200 and not silent:
                Logger.debug("RiotAPI", f"{resp.status_code} {path}")
            return resp
        except Exception as e:
            Logger.error("RiotAPI", f"Request failed: {e}")
            return None

    def platform_request(self, path: str, silent: bool = False):
        return self._request(self.platform, path, silent)

    def regional_request(self, path: str, silent: bool = False):
        return self._request(self.region, path, silent)
```

### 2. Add config key
In `services/asset_manager.py` → `DEFAULT_CONFIG`:
```python
"riot_api_key": "",
"riot_platform": "na1",
"riot_region": "americas",
```

### 3. Wire into AutomationEngine
In `automation.py.__init__`:
```python
api_key = self.config.get("riot_api_key", "")
if api_key:
    from .riot_api import RiotAPIClient
    self.riot_api = RiotAPIClient(
        api_key,
        self.config.get("riot_platform", "na1"),
        self.config.get("riot_region", "americas")
    )
else:
    self.riot_api = None
```

### 4. Use it
```python
if self.riot_api:
    resp = self.riot_api.platform_request(f"/lol/league/v4/entries/by-summoner/{summoner_id}")
    if resp and resp.status_code == 200:
        entries = resp.json()
```

## Key Endpoints

### Account (Regional)
```
GET /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
GET /riot/account/v1/accounts/by-puuid/{puuid}
```

### Summoner (Platform) — Deprecated, use Account
```
GET /lol/summoner/v4/summoners/by-puuid/{puuid}
```
Returns: `{ id, accountId, puuid, profileIconId, revisionDate, summonerLevel }`

### League / Rank (Platform)
```
GET /lol/league/v4/entries/by-summoner/{encryptedSummonerId}
```
Returns array of `LeagueEntryDTO`:
```json
{
  "queueType": "RANKED_SOLO_5x5",
  "tier": "GOLD",
  "rank": "II",
  "leaguePoints": 75,
  "wins": 120,
  "losses": 100
}
```
Empty array = unranked.

### Spectator (Platform)
```
GET /lol/spectator/v4/active-games/by-summoner/{encryptedSummonerId}
```
Returns 404 if not in-game. Response includes:
- `participants[]` — championId, perks, spells, teamId
- `bannedChampions[]` — championId, teamId, pickTurn
- `gameMode`, `gameQueueConfigId`, `gameLength`
- Does **NOT** include CS, KDA, or in-game stats

### Match History (Regional)
```
GET /lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=20
GET /lol/match/v5/matches/{matchId}
```

## Rate Limits
- **Development**: 20 req/s, 100 req/2min
- **Production**: Varies by app approval
- Always check `Retry-After` header on 429 responses
- Cache aggressively — match data never changes

## Notes
- The Riot API key is **separate** from LCU auth (lockfile). They are independent systems.
- Encryption of IDs is per-API-key — summonerId from one key won't work with another.
- PUUID is consistent across keys and regions.
- Data Dragon (DDragon) endpoints do NOT require an API key — LeagueLoop already uses these in `asset_manager.py`.
