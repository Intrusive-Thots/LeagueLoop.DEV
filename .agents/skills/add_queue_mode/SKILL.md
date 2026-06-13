---
name: Add Queue Mode
description: Integrate a new League of Legends game queue mode (Queue ID) to LeagueLoop backend, local API, stats scraper, and UI components.
---

# Add Queue Mode Skill

Use this skill when you need to introduce support for a new League of Legends game mode queue (e.g., URF, Arena, Custom, etc.) into the LeagueLoop ecosystem.

## Steps

### 1. Define the Constant
Add the new queue ID constant to [constants.py](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/core/constants.py):
```python
QUEUE_ARENA_3V6 = 1710
```

### 2. Register in Stats Scraper
In [stats_scraper.py](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/stats_scraper.py):
- Map the queue ID in `_QUEUE_DATASET_MAP` to the correct baseline dataset (e.g., `BASELINE_ARENA_WINRATES`).
- Register the mode name in `_QUEUE_MODE_NAMES` (e.g., `{1710: "Arena 3v6"}`).

### 3. Update Automation Engine Logic
In [automation.py](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/automation.py):
- Include the new queue ID constant in the relevant type checks (e.g. `is_arena = self.current_queue_id in {QUEUE_ARENA, QUEUE_ARENA_3V6}`).

### 4. Update Local API
In [local_api.py](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/local_api.py):
- Add the display name and ID mapping inside the `/queue-modes` endpoint handler.

### 5. Update UI selectors
- In [app_sidebar.py](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/app_sidebar.py):
  - Add the mode name string to the game modes list.
  - Map the mode name string to the queue ID in `_get_queue_id_for_mode`.
- In [session_header.py](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/session_header.py):
  - Include the mode in the sidebar/session header selector dropdown.

### 6. Verify and Add Tests
Create/update tests to ensure coverage. Test mapping and flow.
Example: [test_arena_3v6.py](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/tests/test_arena_3v6.py)
