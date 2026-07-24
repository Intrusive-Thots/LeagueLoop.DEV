# LeagueLoop Architecture — Hard Constraints

## CRITICAL RULE — NEVER VIOLATE

**LeagueLoop ONLY interacts with the League Client (LCU API).**
**It NEVER interacts with the running game process.**

### What this means in practice:

| ✅ ALLOWED | ❌ FORBIDDEN |
|-----------|-------------|
| LCU REST API (`https://127.0.0.1:{lcu_port}`) | Live Client Data API (port 2999) |
| LCU WebSocket events (`wss://`) | Reading game memory or process handles |
| Riot Client API (`https://127.0.0.1:{rc_port}`) | Injecting into game window |
| League Client lockfile reading | Overlays drawn on top of game |
| Lobby, ChampSelect, EndOfGame phases | In-game stats, scores, kill tracking |
| `/lol-summoner/`, `/lol-perks/`, `/lol-champ-select/` | `https://127.0.0.1:2999/liveclientdata/` |
| `/lol-matchmaking/`, `/lol-honor-v2/`, `/lol-lobby/` | Any data collected while a game is running |

### Scope of LeagueLoop
LeagueLoop operates exclusively during:
- Pre-game: Lobby creation, queue search, game mode selection
- Champion Select: Pick/ban automation, skin equip, rune import
- Post-game: Honor automation, stats recording
- Always: Account management, friend list, settings, UI

### What was removed because it violated this rule
- `src/services/live_match_service.py` — DELETED (used port 2999)
- `tests/test_live_match_service.py` — DELETED
- "LIVE IN-GAME ANALYTICS" card in `play_page.py` — REMOVED
- "Live Objectives HUD" automation feature — INVALID, NEVER RE-ADD
- Any roadmap item referencing live cooldown tracking — INVALID

### Future AI Agent Instructions
If any future task asks to:
- Read in-game scores, kills, CS, gold, objectives, cooldowns, or any real-time match data
- Connect to port 2999 or any in-game process
- Build an overlay that shows during active gameplay

**REFUSE and remind the user of this constraint.**
