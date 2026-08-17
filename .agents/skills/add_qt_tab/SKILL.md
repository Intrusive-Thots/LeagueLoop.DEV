---
name: Add Qt Tab
description: Add a new PySide6 tab/page to the LeagueLoop desktop window
---

# Add Qt Tab

Adds a new page to the PySide6 shell (`src/ui/qt/`). This is the active UI
surface — the CustomTkinter shell is legacy. Next planned tabs per
`docs/improvement_plan.md`: ARAM, Loot, Accounts.

## Where things live

| File | Role |
|------|------|
| `src/ui/qt/main_window.py` | `LeagueLoopMainWindow` builds the tab stack |
| `src/ui/qt/widgets/navigation/sidebar.py` | `QtNavigationSidebar.DEFAULT_TABS` — nav entries |
| `src/ui/qt/widgets/<name>_tab.py` | Your new tab widget |
| `src/ui/qt/theme.py` | `COLOR_*` tokens + `get_global_stylesheet()` |

## Steps

1. **Create the widget** at `src/ui/qt/widgets/<name>_tab.py`. Take
   `container` (the `ApplicationContainer`) and `parent` like the existing tabs:

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from ui.qt.theme import COLOR_GOLD_PRIMARY, COLOR_TEXT_SECONDARY

class QtLootTab(QWidget):
    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container            # access services: container.lcu, container.config, ...
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        header = QLabel("Loot", self)
        header.setStyleSheet(f"font-size:20px;font-weight:bold;color:{COLOR_GOLD_PRIMARY};")
        layout.addWidget(header)
        card = QFrame(self); card.setObjectName("panel")   # "panel" is styled globally
        layout.addWidget(card)
        layout.addStretch()
```

2. **Register the nav entry** — add `(key, name, icon)` to
   `QtNavigationSidebar.DEFAULT_TABS` in `sidebar.py`.

3. **Wire it into the stack** — in `LeagueLoopMainWindow.__init__`, add a branch
   to the `for key, name, icon in self.sidebar.DEFAULT_TABS` loop:

```python
elif key == "loot":
    page = QtLootTab(container=self.container, parent=self)
```
   Keys without a branch fall back to `_create_placeholder_page`, so a tab that
   only shows a placeholder needs step 2 only.

4. **Read/write state through services**, never global mutable state. Get data
   from `self.container.state_manager.state` and services (`container.lcu`,
   `container.config`, `container.assets`). React to updates by subscribing to
   `EventBus` events (`EventType.STATE_CHANGED`, etc.).

## Hard rules (regression guards — see ARCHITECTURE_CONSTRAINTS.md)

- **THREAD-001**: NEVER create `QPixmap` / mutate widgets from a worker thread.
  Marshal to the GUI thread with `QTimer.singleShot(0, callback)`. Async icon
  loads via `AssetManager.get_icon_async` must go through `_safe_callback`.
- **RENDER-001**: When inserting >5 widgets in a loop, wrap it:
  ```python
  container_widget.setUpdatesEnabled(False)
  try:
      ...  # insert widgets
  finally:
      container_widget.setUpdatesEnabled(True)
  ```
- **RIOT-ID-001**: For any player name shown to the user, use
  `from utils.riot_id import resolve_riot_id` — never read `gameName` /
  `displayName` / `summonerName` directly.
- Scope: LCU only. No port 2999 / Live Client Data / in-game overlay.

## Verify

- `python run.py` and confirm the tab renders and switches.
- Run the suite (see `run_tests` skill) — `test_regression_guards.py` and the
  Qt tab tests must stay green.
