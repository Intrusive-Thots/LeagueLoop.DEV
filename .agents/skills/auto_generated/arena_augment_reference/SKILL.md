---
name: Arena Augment Reference
description: Look up Arena (Cherry) augment IDs, names, and images for match data parsing and UI display
---

# Arena Augment Reference

## Overview
Arena augment IDs appear in match-v5 data for Arena (Cherry) games. These IDs map to specific augment names and images hosted on CommunityDragon. Use this reference when displaying post-match Arena data or building augment recommendation features.

## Data Source
The canonical augment list is hosted by CommunityDragon:
```
https://raw.communitydragon.org/latest/cdragon/arena/en_us.json
```

## Fetching Augments

```python
import requests
import json
import os

AUGMENT_CACHE = os.path.join(CACHE_DIR, "arena_augments.json")

def fetch_arena_augments() -> dict:
    """Fetch and cache the Arena augment ID → name mapping."""
    if os.path.exists(AUGMENT_CACHE):
        with open(AUGMENT_CACHE, "r") as f:
            return json.load(f)

    url = "https://raw.communitydragon.org/latest/cdragon/arena/en_us.json"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return {}

    data = resp.json()
    augments = {}
    for aug in data.get("augments", []):
        aug_id = aug.get("id", 0)
        name = aug.get("name", "Unknown")
        desc = aug.get("desc", "")
        icon = aug.get("iconSmall", "")
        rarity = aug.get("rarity", 0)  # 0=Silver, 1=Gold, 2=Prismatic
        augments[str(aug_id)] = {
            "name": name,
            "desc": desc,
            "icon": icon,
            "rarity": rarity
        }

    with open(AUGMENT_CACHE, "w") as f:
        json.dump(augments, f)

    return augments
```

## Augment Rarity Tiers
| Rarity | Tier | Color |
|--------|------|-------|
| 0 | Silver | `#C0C0C0` |
| 1 | Gold | `#FFD700` |
| 2 | Prismatic | `#E8D5F5` |

## Augment Image URLs
CommunityDragon hosts augment icons. The `iconSmall` field from the JSON gives a relative path:
```python
def get_augment_icon_url(icon_path: str) -> str:
    """Convert CommunityDragon relative path to full URL."""
    # icon_path looks like: "ASSETS/Maps/Cherry/Augments/Icons/..."
    clean = icon_path.lower().replace("/lol-game-data/assets/", "")
    return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/{clean}"
```

## Notable Augments (Partial List)
| Name | ID | Rarity |
|------|----|--------|
| Warmup Routine | Various | Silver |
| Vanish | Various | Silver |
| Raid Boss | Various | Prismatic |
| Omni Soul | Various | Prismatic |
| Prismatic Egg | Various | Prismatic |
| OK Boomerang | Various | Gold |
| Snowball Fight | Various | Gold |

## Using with Match Data
In match-v5 responses, Arena augments appear per-participant:
```json
{
  "participants": [
    {
      "puuid": "...",
      "playerAugment1": 501,
      "playerAugment2": 302,
      "playerAugment3": 105,
      "playerAugment4": 408,
      "placement": 1,
      "subteamPlacement": 1
    }
  ]
}
```

```python
augments = fetch_arena_augments()
aug_name = augments.get(str(player["playerAugment1"]), {}).get("name", "Unknown")
```

## Integration with LeagueLoop Arena Tool
The Arena tool in `ui/components/game_tools/arena_tool.py` could be enhanced to:
1. Show augment recommendations based on champion synergies
2. Display augment pick history from match-v5 data
3. Track augment win rates across your games

## Notes
- Augment IDs change between patches — always fetch the latest data.
- Cache the augment list locally to avoid repeated downloads.
- The CommunityDragon URL does NOT require an API key.
