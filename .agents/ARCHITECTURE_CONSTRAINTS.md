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

---

## Regression Prevention Rules (Added 2026-07-26)

These rules address recurring bug classes that have been fixed multiple times.
Violating these rules WILL cause bugs that have already been fixed to recur.

### THREAD-001: Never Touch Qt GUI from Background Threads
- **NEVER** create `QPixmap`, modify `QWidget` properties, or call `set_pixmap()` from a `threading.Thread` worker
- **ALWAYS** use `QTimer.singleShot(0, callback)` to marshal GUI updates to the main thread
- **CHECK**: If `AssetManager.get_icon_async` callback modifies a widget, it MUST go through `_safe_callback` which checks `QThread.currentThread() != app.thread()`
- **Files affected**: `asset_manager.py`, `champions_page.py`, `champion_cell.py`, `friends_page.py`, `friend_row.py`
- **Regression test**: `test_regression_guards.py::TestThreadSafety`

### RIOT-ID-001: Always Use `resolve_riot_id()` for Name Resolution
- **NEVER** access `gameName`, `name`, `displayName`, `summonerName` directly for display purposes
- **ALWAYS** use `from utils.riot_id import resolve_riot_id` then `resolve_riot_id(data)`
- Riot migrated from summoner names to Riot IDs (`gameName#gameTag`). LCU endpoints return different field combinations. The utility handles ALL fallback chains.
- **Files affected**: `friend_service.py`, `friend_row.py`, `friends_page.py`, `play_viewmodel.py`, `header_viewmodel.py`, `dodge_requeue.py`
- **Regression test**: `test_regression_guards.py::TestRiotIdResolution`

### LCU-001: Only Mark League Found When Credentials Are Present
- **NEVER** set `league_found = True` just because `LeagueClient.exe` is in the process list
- **ALWAYS** verify both `--app-port` AND `--remoting-auth-token` are extracted before marking found
- `LeagueClient.exe` is the parent launcher — it does NOT have credentials. `LeagueClientUx.exe` does.
- **Files affected**: `client_detector.py`
- **Regression test**: `test_regression_guards.py::TestLCUProcessScanner`

### RENDER-001: Batch Widget Insertion Must Suppress Layout Updates
- **ALWAYS** wrap loops that insert >5 widgets with:
  ```python
  container.setUpdatesEnabled(False)
  try:
      # insert widgets
  finally:
      container.setUpdatesEnabled(True)
  ```
- Without this, each widget insertion triggers a full layout recalculation, freezing the UI
- **Files affected**: `champions_page.py`, `friends_page.py`
- **Regression test**: `test_regression_guards.py::TestBatchRendering`
