---
name: Spectate Live Game
description: Get live game data for any player using the Riot Games spectator-v4 API — champions, runes, spells, bans, and teams
---

# Spectate Live Game

## Overview
The spectator-v4 API provides real-time data about an ongoing League of Legends match. Use it to show what champions, runes, and summoner spells each player is running — useful for scouting enemies during loading screen or displaying friend game status.

## Prerequisites
- A valid Riot API key in `config.json`
- The player's **encrypted summonerId** (get via summoner-v4 from PUUID)
- The `RiotAPIClient` from the `riot_web_api` skill

## Endpoints

### Active Game by Summoner
```
GET https://{platform}.api.riotgames.com/lol/spectator/v4/active-games/by-summoner/{encryptedSummonerId}
```
Returns **404 Not Found** if the player is NOT in-game. This is expected behavior.

### Featured Games
```
GET https://{platform}.api.riotgames.com/lol/spectator/v4/featured-games
```
Returns a list of highlighted live games. Includes `clientRefreshInterval` (usually 300s) — respect this rate.

## Response Structure (CurrentGameInfoDTO)
```json
{
  "gameId": 123456789,
  "gameMode": "ARAM",
  "gameQueueConfigId": 450,
  "gameType": "MATCHED_GAME",
  "gameLength": 168,
  "mapId": 11,
  "platformId": "EUW1",
  "bannedChampions": [
    { "pickTurn": 1, "championId": 266, "teamId": 100 }
  ],
  "participants": [
    {
      "bot": false,
      "championId": 45,
      "profileIconId": 29,
      "spell1Id": 4,
      "spell2Id": 32,
      "summonerName": "PlayerName",
      "summonerId": "encrypted...",
      "teamId": 100,
      "perks": {
        "perkIds": [8128, 8143, 8138, 8106, 8014, 9111, 5008, 5008, 5002],
        "perkStyle": 8100,
        "perkSubStyle": 8000
      }
    }
  ],
  "observers": {
    "encryptionKey": "abc123..."
  }
}
```

## What's Available vs NOT Available

| ✅ Available | ❌ NOT Available |
|-------------|-----------------|
| Champion ID per player | CS / Gold |
| Runes (all 9 perk IDs) | KDA |
| Summoner spells (spell1Id, spell2Id) | Items |
| Team assignment (100/200) | Current HP/Mana |
| Bans | Ability order |
| Game duration (since start) | Damage stats |
| Game mode / queue ID | — |

## Implementation Example

```python
def get_live_game(self, summoner_id: str) -> dict | None:
    """Get live game data for a summoner. Returns None if not in-game."""
    if not self.riot_api:
        return None

    resp = self.riot_api.platform_request(
        f"/lol/spectator/v4/active-games/by-summoner/{summoner_id}",
        silent=True
    )
    if not resp or resp.status_code == 404:
        return None  # Not in game
    if resp.status_code != 200:
        return None

    return resp.json()


def format_live_game(self, game_data: dict) -> list[dict]:
    """Parse live game into a list of player info dicts."""
    players = []
    for p in game_data.get("participants", []):
        champ_name = self.assets.get_champ_name(p.get("championId", 0))
        team = "Blue" if p.get("teamId") == 100 else "Red"
        players.append({
            "name": p.get("summonerName", "Unknown"),
            "champion": champ_name,
            "team": team,
            "spell1": p.get("spell1Id"),
            "spell2": p.get("spell2Id"),
            "runes": p.get("perks", {}).get("perkIds", []),
        })
    return players
```

## Queue Config IDs (gameQueueConfigId)
```python
QUEUE_MAP = {
    400: "Draft Pick",
    420: "Ranked Solo/Duo",
    440: "Ranked Flex",
    450: "ARAM",
    490: "Quickplay",
    900: "URF",
    1010: "ARURF",
    1020: "One For All",
    1090: "TFT Normal",
    1100: "TFT Ranked",
    1300: "Nexus Blitz",
    1400: "Ultimate Spellbook",
    1700: "Arena",
    2300: "Brawl",
    2400: "ARAM Mayhem",
}
```

## Summoner Spell IDs (Common)
```python
SPELL_MAP = {
    1: "Cleanse", 3: "Exhaust", 4: "Flash", 6: "Ghost",
    7: "Heal", 11: "Smite", 12: "Teleport", 13: "Clarity",
    14: "Ignite", 21: "Barrier", 30: "To the King!",
    31: "Poro Toss", 32: "Mark (ARAM)", 39: "Mark (URF)",
    54: "Placeholder", 55: "TFT Placeholder"
}
```
Full list: `https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/summoner.json`

## Notes
- `gameLength` is in seconds since game start (not total match duration).
- `observers.encryptionKey` can be used to spectate the game via the LoL client.
- Team IDs: `100` = Blue side, `200` = Red side.
- The spectator API is eventually consistent — it may take ~30s after game start for data to appear.
- Perk IDs map to rune trees: `8000` = Precision, `8100` = Domination, `8200` = Sorcery, `8300` = Inspiration, `8400` = Resolve.
