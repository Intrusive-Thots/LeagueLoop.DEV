---
name: Edit Config
description: Safely modify config.json values with validation
---

# Edit Config

## File Locations
- **Dev config:** `c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\config.json`
- **User config (installed):** `%APPDATA%\LeagueLoop\config.json`
- **Defaults:** `src\services\asset_manager.py` → `DEFAULT_CONFIG` dict

## Steps

1. Read the current config:
```powershell
Get-Content "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\config.json" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

2. To modify a value, edit `config.json` directly using the file edit tools.

3. Validate it parses cleanly:
```powershell
.venv\Scripts\python.exe -c "import json; json.load(open('config.json')); print('Valid JSON')"
```

## Config Schema Reference
| Key | Type | Description |
|-----|------|-------------|
| `auto_accept` | bool | Auto-accept ready check |
| `auto_requeue` | bool | Auto re-queue after game |
| `accept_delay` | float | Seconds to wait before accepting |
| `custom_status` | string | LoL client custom status message |
| `aram_mode` | string | Game mode name (e.g. "ARAM Mayhem") |
| `stealth_mode` | bool | Keep window hidden during games |
| `always_on_top` | bool | Window stays above all others |
| `auto_honor_enabled` | bool | Auto-honor after games |
| `honor_strategy` | string | "random", "friend", or "carry" |
| `auto_join_friend_enabled` | bool | Auto-join friend's lobby |
| `auto_join_friend` | string | Friend name to auto-join |
| `auto_join_list` | array | List of {name, enabled} auto-join targets |
| `priority_picker.enabled` | bool | Enable ARAM priority sniper |
| `priority_picker.list` | string[] | Ordered champion names (DDragon keys) |
| `hotkey_launch_client` | string | Hotkey to launch/restart League Client |
| `hotkey_toggle_automation` | string | Hotkey to toggle automation on/off |
| `hotkey_find_match` | string | Hotkey to start matchmaking |
| `hotkey_compact_mode` | string | Hotkey for compact orb mode |
| `hotkey_omnibar` | string | Hotkey to open command palette |

## Critical Rules
- Champion names in `priority_picker.list` must be **DDragon API keys** (e.g. `"MonkeyKing"` not `"Wukong"`, `"Khazix"` not `"Kha'Zix"`).
- Always validate JSON after editing to prevent runtime crashes.
- When adding a NEW config key, also add it to `DEFAULT_CONFIG` in `asset_manager.py`.
- Back up before making major changes: `Copy-Item config.json config_backup.json`
