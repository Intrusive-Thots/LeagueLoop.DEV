# LeagueLoop — Register of Unfinished Work

Version at time of writing: **2-08-131-2240**
Audited: 21 August 2026. Every entry below was read in the source, not inferred.

---

## How to read this

Each entry is `file:line — what is wrong — what finishing it requires`.

Entries are grouped by **failure class**, not by screen, because the same
mistake was made repeatedly in different places and fixing the class is
cheaper than fixing the instances one at a time. The four classes that
account for most of this document are:

1. **A control writes a config key nothing reads** (or reads one nothing
   writes). Found 11 times so far.
2. **A producer that only reports changes, wired to a consumer that arrived
   late.** First paint is empty or stale forever.
3. **`except Exception: pass` around the one call that does the work.** The
   button appears to work, nothing happens, nothing is reported.
4. **Two implementations of the same screen that drifted.** The user gets a
   different editor depending on which route they took to it.

### What this audit did NOT cover

**Nothing in this repository has ever been run against a real League Client.**
The development environment is Linux; League does not run on Linux. Every test
in `tests/` (385 of them) runs against fakes written in this same repository,
so they prove the code is internally consistent — not that the LCU accepts any
of it. Section 8 lists the specific things that will break first when it is
finally run for real, in the order I expect them to break.

---

## 0. Fixed in this pass — do not redo

| Fix | Files |
|---|---|
| Champion favourites had no way to set one: the tile's context-menu signal was connected to nothing, `_toggle_favorite` mutated an in-memory set, and no config key existed | `champion_grid.py`, `config_keys.py`, `tests/test_favorites.py` |
| Right-clicking a champion opened the context menu **twice** (introduced by the favourites fix — connected at both the grid and the tile) | `champion_grid.py:160` |
| Role filter chips (Top/Jungle/Mid/Bot/Support) matched every champion: `assets.get_champ_roles` did not exist, and `if roles and …` treated "unknown" as "matches" | `asset_manager.py`, `champion_grid.py` |
| The automation hotkey and the tray menu's automation toggle both raised `AttributeError` (`ctrl.is_master_enabled`; the method is `master_enabled()`) inside callbacks that swallow exceptions | `main_window.py`, `system_tray.py` |
| Custom status was sent to the LCU **twice**; the second call passed a `json=` keyword `ApiHandler.request` does not accept, so every save reported a failure for a status that had been set | `settings_tab.py`, `main_window.py` |
| "Respect teammate hovers" was discarded on Done — it only persisted if the user also happened to edit the ban list in the same session | `ban_list_dialog.py` |
| The ban list rendered champion **ids** as names (`#3  266`) because `get_champ_name` falls back to `str(id)` and the guard was only `if name:` | `ban_list_dialog.py` |
| ARAM priorities were annotated and sorted with **Summoner's Rift** win rates — `set_mode` switched the config key but never the scraper | `champion_list_tab.py` |
| The Priority screen opened with **neither** mode button selected | `champion_list_tab.py` |
| Auto-requeue-after-dodge could never fire: `self.last_phase = phase` ran *before* the handler whose only guard compares against `last_phase` | `automation.py` |
| Auto Requeue is a switch on two screens that the engine did not read at all | `automation.py` |
| A "paused" engine still accepted ready checks, honored, skipped stats and joined friend lobbies — pause was checked inside one handler only | `automation.py` |
| Emergency stop during the accept delay still accepted the match: the `threading.Timer` was never cancelled and re-checked nothing when it fired | `automation.py` |
| Starting the app mid-draft left `current_queue_id` unset (the lobby endpoint 404s during champ select), so neither the Arena path nor the draft assistant ran | `automation.py` |

### Logging pass (second sweep)

| Fix | Files |
|---|---|
| Log lines had **no date** (`datefmt='%H:%M:%S'`) and **no level name**, so a file covering two days was unreadable and an ERROR looked like a DEBUG | `utils/logger.py` |
| No traceback was ever recorded — `Logger.error` took a string and nothing else | `utils/logger.py` |
| Nothing marked where one run ended and the next began; no record of version, platform, Python, Qt, or the config the run used | `utils/session_log.py` |
| An unhandled exception on a **worker thread** — where most of this app's work happens — went to a stderr nobody sees. So did Qt's own warnings, and a native crash left nothing at all | `utils/session_log.py` |
| Startup failures (container, client state, automation config, first refresh) printed to `sys.stderr`, invisible when launched from a shortcut or a `.bat` that closes | `ui/qt/app/application.py` |
| **106 `except Exception: pass`** handlers across the codebase discarded the error silently | 28 files, via `tools/log_silent_excepts.py` |
| Every draft PATCH, ready-check accept, reroll and bench swap discarded its result and logged success either way | `services/automation.py` (`_act`) |
| No record of LCU connect/disconnect or gameflow phase transitions; repeated poll failures logged at DEBUG forever | `services/client_state_service.py` |
| The account switch — the flow that has never been observed against a real client — left no trail of which phase it reached | `services/accounts/switcher.py` |
| Loot crafting, the one irreversible operation, recorded nothing about what it opened | `services/loot_service.py` |
| Hotkey binding failures were swallowed, so an app with **no working hotkeys** looked identical to one where the user pressed the wrong keys | `ui/qt/main_window.py` |
| "Find Match" swallowed every failure (§1.5) — now checks the status and reports it | `ui/qt/widgets/play_tab.py` |
| "Prune image cache" discarded its result dict and every failure (§1.6) | `ui/qt/widgets/diagnostics_tab.py` |
| A page's own `toast_requested` was a signal into the void | `ui/qt/main_window.py` |

**What a run now leaves behind**, in `%LOCALAPPDATA%\LeagueLoop\logs`:

* `debug.log` — everything, `2026-08-21 19:47:03.418 +0000  ACTION   AutoLoop  [Automation] Draft: locked in Ahri  (champion_id=103)`
* `error.log` — WARNING and above with full tracebacks
* `session.jsonl` — one JSON object per record, for tooling
* `crash.log` — native tracebacks from `faulthandler`

`ACTION` is a level of its own: anything that changed the user's account or
their data — a pick, a ban, an accept, a loot craft, an account switch. When
the question is "what did it actually do", that is the only level you need.

The Diagnostics screen now has a **Logs** card showing the session id, the
folder, and this run's warning/error tally, with buttons to open the folder
and to save a redacted support bundle (a zip of the logs plus a manifest;
`accounts.json` and `config.json` are deliberately excluded, and credential
shaped keys are replaced with `<redacted>` at write time).

A test (`tests/test_logging.py::SilentHandlerTests`) fails the build if a new
`except Exception: pass` is added anywhere in `src/`.

---

33 regression tests were added across `tests/test_dead_controls.py`,
`tests/test_logging.py` and `test_winrate_honesty.py`. Suite: **410 passing.**

### Completion pass — §10 worked through in order

**First — things that acted on the account without being asked (§10.1–5)**

| Fix | Where |
|---|---|
| `dodge_blacklist` force-closed the League Client with **no switch, no try/except and Windows-only flags** that raised into the tick's error killswitch everywhere else. Now behind `dodge_blacklist_enabled`, re-read per draft instead of frozen at startup, refuses to run off Windows, and has an editor (the list was previously unreachable — a stale value kept killing the client with no way to find out why) | `automation.py`, `blacklist_dialog.py` |
| Loot crafts, draft actions, ready-check accepts and honors were **queued while disconnected and replayed on the next connect** — irreversible actions firing minutes later, multiplied, with no UI. `NEVER_QUEUE_PREFIXES` keeps them out of that queue, and `_craft` stops on the first not-connected result instead of looping | `api_handler.py`, `loot_service.py` |
| `priority_picker` shipped **enabled with ten champions nobody chose**, so a fresh install bench-swapped toward a developer's favourites. Now empty and off | `config_manager.py` |
| The chat warden read **every lobby message every tick, gated on nothing**, with no screen admitting it existed. Off by default, with a row that says what it does | `automation.py`, `automation_tab.py` |
| `_encrypt` logged and returned `""` on DPAPI failure, so the account was stored with an empty password and reported as added. Raises `CredentialEncryptionError` now; nothing is stored | `account_manager.py` |
| Engine and UI **disagreed on six defaults** — `auto_join_enabled` read True and rendered False, so invites were auto-accepted while the switch showed off. A test now fails the build if any switch's shipped default differs from what the screen renders | `config_manager.py`, `automation_tab.py` |
| Arena automation was on by default with **no screen anywhere**. Off until there is one | `config_manager.py` |
| `wallet: {"be": 0, "rp": 0}` and `region: "NA1"` were written for every account and read by nothing. Both removed; region is now optional and says it is not used for signing in | `account_manager.py`, `account_editor.py` |

**Second — the draft (§10.6–11)**

| Fix | Where |
|---|---|
| The screen and the engine now describe the same draft: `queue_id` and the bans are carried through state, so `_is_aram()` works and ARAM stops recommending from the Summoner's Rift list | `state.py`, `client_state_service.py`, `champ_select_viewmodel.py` |
| `can_act()` was a **blocking LCU GET on the GUI thread, once a second**, during the phase where latency matters most. Derived from state now | `champ_select_viewmodel.py` |
| The commit button was hardcoded "Lock in" while `lock_in` commits whatever is in progress — on a ban turn it said "Lock in", banned the champion, then reported "Locked in". It reads **Ban** on a ban turn and says so | `champ_select_tab.py` |
| Double-click committed an irreversible draft action with no confirmation. It selects | `champ_select_tab.py` |
| "Pick manually" paused automation and **nothing ever resumed it** — one press killed champ-select automation for the session. The button is now a toggle that says "Resume automation" | `champ_select_tab.py` |
| There was **no "not in a draft" state**: full roster, live buttons, and a timer permanently reading "TIME UP 00:00" | `champ_select_tab.py` |
| Result messages were destroyed within a second by the render loop, so failures read as silent no-ops. They hold for six seconds | `champ_select_tab.py` |
| Confidence came from a **hardcoded rank** (LOW was unreachable), backups came from a different list than the recommendation, and each backup's badge was its index in the filtered row rather than the rank the user configured. All three read real values now | `priority_engine.py`, `champ_select_viewmodel.py` |
| `set_owned` had no caller, so every champion rendered as owned. The pickable set is fetched once per draft and applied | `client_state_service.py`, `champ_select_tab.py` |
| Stale ban markings from the previous draft stayed on the tiles when the validator failed | `champ_select_tab.py` |

**Third — controls that lied (§10.12–16)**

| Fix | Where |
|---|---|
| **Opening the Automation screen wrote config**, persisting every default as though chosen | `automation_tab.py` |
| With the master switch off at startup, every row below stayed enabled and interactive | `automation_tab.py` |
| Turning the master switch **on** wrote config and nothing else — the engine stayed stopped until restart while the row read "on" | `automation_tab.py` |
| The screen never re-read itself, so the hotkey, the tray menu and the HTTP API could leave it showing the opposite of reality | `automation_tab.py` |
| "N priorities configured" counted one list, so role-only users were told they had none and Auto Lock In was greyed out when it would have worked | `automation_tab.py` |
| The emergency stop was constructed **enabled** and only gated in a method that returns early without a view model | `automation_tab.py` |
| "Run in system tray" needed a restart — and with it on but the icon not yet shown, closing the window **exited the app instead of minimising** | `settings_tab.py`, `main_window.py` |
| Rebinding a hotkey did nothing until restart while the label updated immediately, and the old shortcut stayed registered | `settings_tab.py`, `main_window.py` |
| Loot reported "Loot opened" with a success tone when nothing opened and every craft failed. It reports opened / failed / skipped / keys forged | `loot_tab.py` |
| Key forging runs **first** and is irreversible, and fragments were excluded from the preview — the one step never shown was the first one to happen | `loot_service.py`, `loot_tab.py` |
| "Ban list" was connected to two handlers, so it navigated to the Bans tab *and* opened a drifted modal on top of it | `main_window.py` |

**Fourth — structural (§10.17–21)**

| Fix | Where |
|---|---|
| Drag-reorder **destroyed the row being dragged** — `setItemWidget` does not survive `InternalMove`, so the champion became a permanently blank row and `_renumber_items` skipped it forever. The list rebuilds from the ids | `champion_list_tab.py` |
| The ARAM bench sniper and auto-reroll switches lived only on an unreachable screen, so the engine read two keys nothing could write — and "configure" for both landed on a screen with neither control. Both now live on the Priority screen in ARAM mode | `champion_list_tab.py` |
| `aram_tab.py` is a re-export shim (the bridge cannot delete files; remove it whenever you like) | `aram_tab.py` |
| The Loot open, the loot refresh and the whole Profile load ran **on the GUI thread** — the window was unpaintable throughout, so the "Refreshing…" status never rendered | `background.py`, `loot_tab.py`, `profile_tab.py` |
| `Profile.error` carried two useful sentences and had no reader; "no games" and "the request failed" looked identical | `profile_tab.py` |
| EventBus subscriptions were disposed in `closeEvent`, which a page in a `QStackedWidget` never receives — they outlived the widget for the process lifetime | `accounts_tab.py` |

Suite: **455 passing**, up from 410. All ten screens build real widgets with
no empty-state fallbacks; the only warning in a clean headless run is the
`keyboard` package being absent on Linux.

---

## 1. Controls that are on screen and reach nothing

### 1.1 Champion grid

- `champion_grid.py:441` — the **Owned** quick filter is inert. `_owned`
  defaults to `None` = "assume all owned", every tile is built `owned=True`,
  and `set_owned()` has no caller anywhere. The chip checks and the count does
  not move. → Populate from `GET /lol-champ-select/v1/pickable-champion-ids`
  (already used at `automation.py:935`) on client connect, or remove the chip.
- `champion_grid.py:116` — `favorites_changed` is emitted and connected
  nowhere. Favourites are a filter and nothing else: the draft engine, the
  priority list and the bench sniper all ignore them. → Decide what a
  favourite is *for* (seed a priority list? bias the sniper?) and wire it, or
  say on screen that it only filters.

### 1.2 Automation screen

- `automation_tab.py:180` — on load, `master_toggle.set_checked(False)` matches
  the widget's construction default, so `toggled` never fires and
  `_on_master_toggled` never runs. With the master switch off at startup every
  row below stays enabled and interactive, contradicting the master state.
  → Call the row-enable sync directly from `_load_state()`.
- `automation_tab.py:178` — `row.set_checked(...)` during load re-enters
  `_on_row_toggled` → `config.set(...)`. **Merely opening the screen writes
  config**, persisting defaults as if the user had chosen them. → Block signals
  around the load.
- `automation_tab.py:200` — `_render_state()` updates only the master status
  line. The hotkey, the local HTTP API and `AutomationController.set_master`
  all change automation behind the screen's back, so the switches show the
  opposite of reality. → Re-read config/`AutomationState` in `_render_state`
  with signals blocked.
- `automation_tab.py:208` — turning the master switch **on** writes config and
  nothing else. The engine is only ever started by
  `AutomationController.apply_config()` at launch, so it stays stopped until
  restart while the row reads "on". → Call `controller.set_master(checked)`.
- `automation_tab.py:187` — "N priorities configured" counts the raw
  `"priority_list"` literal only, ignoring the per-role lists the engine
  actually uses and the ARAM list. A user with only role-specific priorities
  sees "0 priorities configured" and Auto Lock In greyed out, when it would
  work. It also bypasses `core.config_keys` — the exact drift that module
  exists to prevent. → Use `PRIORITY_LIST` + `read_champion_ids`, count role
  and ARAM lists too.
- `automation_tab.py:183` — `_refresh_details()` never runs from
  `_render_state`, so after adding priorities the count and the disabled row
  stay stale until restart. → Refresh on tab activation.
- `automation_tab.py:113` — `btn_stop` (the emergency stop) is constructed
  **enabled** and only gated in `_render_state`, which returns early when
  there is no view model. Pressing it then reaches a controller that may not
  exist, with no feedback either way. → Default disabled; report the result.

### 1.3 Settings

- `settings_tab.py:94` — **"Run in system tray"** takes effect only after a
  restart, with no notice. The tray icon is created once at startup, and
  `closeEvent` additionally gates on `self.tray.isVisible()` — so the user
  enables the setting, closes the window, and the app **exits** instead of
  minimising. → Wire the row to `tray.show()`/`tray.hide()` the way
  `always_on_top` is already wired.
- `settings_tab.py:245` — **rebinding a hotkey does nothing until restart**,
  and the UI actively implies otherwise by repainting the key immediately. The
  old shortcut also stays registered. → Add `MainWindow.rebind_hotkeys()`
  (`keyboard.remove_all_hotkeys()` then `_bind_hotkeys()`) and call it.

### 1.4 Champ select

- `champ_select_tab.py:246` — the primary button is hardcoded **"Lock in"**,
  and `DraftActions.lock_in` commits *whatever action is in progress,
  including a ban*. On your ban turn the button says "Lock in", bans the
  champion, then reports "Locked in". `DraftActions.pending_type()` exists
  precisely for this and is never called. → Switch label and message on
  `pending_type()`.
- `champ_select_tab.py:213` — double-click (and the grid's "Lock in" context
  item) go straight to `_on_lock_in`: **an irreversible draft action from one
  accidental double-click**, no confirm, no undo. → Confirm, or restrict
  double-click to hover.
- `champ_select_tab.py:331` — "Pick manually" calls `controller.pause(True)`,
  and **nothing in the Qt shell ever resumes**. One press pauses champ-select
  automation permanently. The error killswitch at `automation.py:262` has the
  same problem. → Clear `paused` on champ-select exit and expose a resume
  control.
- `champ_select_tab.py:328` — the same handler reports "Automation is paused"
  **unconditionally**, including when the controller is `None` or the pause
  raised. → Only claim the state when the call succeeded.
- `champ_select_tab.py:383` — there is **no "not in champion select" state**.
  When idle the screen renders the full roster with enabled Pick/Stop buttons,
  "No recommendation" (indistinguishable from a real blocked draft), and a
  timer permanently reading **"TIME UP 00:00"**. → An inactive branch keyed on
  `vm.active`.
- `champ_select_tab.py:443` — every result message is destroyed within one
  tick: `_render()` overwrites `automation_status` on each state push (1 s), so
  "Hovering", "Locked in" and "Could not do that: <reason>" all vanish. Failed
  actions read as silent no-ops. → A transient feedback surface with its own
  lifetime.

### 1.5 Play

- ~~`play_tab.py:236`~~ **FIXED** — **"Find Match"**, the screen's single primary action,
  swallowed every failure (`except Exception: pass`) and non-2xx responses do
  not raise at all — no lobby, queue locked, dodge timer all present as a
  visible no-op. The *hotkey* for the same action has toast feedback; the
  button is strictly worse. → Check `status_code`, emit the existing toast,
  and disable the button when the phase is not Lobby.
- `play_tab.py:189` — the "what automation will do" sentence is built inside a
  per-key `except Exception: continue`, so a config failure silently drops an
  automation from the sentence. It also only recomputes on `state_changed`,
  and the Automation screen writes config without publishing state, so it goes
  stale. → One error path; refresh on tab activation.

### 1.6 Lists and dialogs

- `champion_list_tab.py:145` — **drag-reorder visually destroys the dragged
  row.** Rows are custom widgets installed with `setItemWidget`;
  `QAbstractItemView.InternalMove` re-serialises the item and the index widget
  does not survive. The moved champion becomes a blank row forever (the saved
  order is still correct). Verified against PySide6 6.11.1. → Rebuild the list
  from `current_ids()` inside `_on_rows_moved`, or render rank/portrait/name
  through a `QStyledItemDelegate`, which survives model moves.
- `champion_list_tab.py:475` — **"Clear all" wipes the list with no
  confirmation**, despite being styled DANGER, while the strictly less
  destructive paste-import on the same screen shows a confirm modal. Same at
  `ban_list_dialog.py:256`. → `LLConfirmModal` with the current count.
- `champion_list_tab.py:361` — **"Sort by winrate" never re-enables** once live
  win rates arrive. Enablement is computed at build time and only recomputed
  when the list is mutated; `StatsScraper` fetches on a background thread and
  emits no signal. On the common path the button stays greyed for the session
  even though the data is now there. → Have `StatsScraper` emit "win rates
  updated"; re-run the badge sync and rebuild row labels.
- `champion_list_tab.py:507` / `:530` — `_renumber_items()` is called expecting
  the `(xx.x% WR)` labels to refresh; it only rewrites the rank number. The
  text lives in a `QLabel` built once in `_make_row`. → Add
  `_refresh_row_labels()`.
- `champion_list_tab.py:395` — the hint label is used as a one-way error
  channel and never restored, so "Click a champion to add. Drag to reorder."
  is gone for the rest of the session after one failed paste. It is also the
  same label whose visibility `_sync_grid_badges` toggles — the two uses
  fight. → Give paste feedback its own label.
- `champion_list_tab.py:231` — rows show DDragon **keys**, not names:
  "MonkeyKing", "RenataGlasc", "Nunu" beside grid tiles reading "Wukong",
  "Renata Glasc", "Nunu & Willump". Those keys are then used for the win-rate
  lookup, which is keyed on display names, so those champions show no WR and
  the winrate sort silently sinks them to the bottom of the saved order. →
  Resolve from `assets.champ_data[key]["name"]`.
- ~~`diagnostics_tab.py:374`~~ **FIXED** — "Prune image cache" swallowed every failure and
  discards the `{removed_files, freed_bytes, …}` the service returns. A
  permission error is indistinguishable from a successful no-op. → Show what
  was freed; surface the exception.

### 1.7 Accounts

- `account_editor.py:151` — **Region is a required field that nothing
  consumes.** `switch_to`/`RiotSession.sign_in` never read it; its only uses
  are the list caption and the local HTTP API dump. Users are blocked on a
  value that changes nothing. → Make it display-only, or pass it into sign-in.
- `accounts_tab.py:76` — `switch_requested` is emitted and connected nowhere.
- `accounts_tab.py:827` — `_on_set_default` swallows exceptions and, unlike
  every other mutating handler, has **no `_switching` guard**: the default can
  be repointed mid-switch. → Guard and report.
- `accounts_tab.py:682` — `_on_move` swallows any `move_account` failure and
  refreshes, so a failed reorder is indistinguishable from a successful one.

### 1.8 Loot

- `loot_tab.py:293` — the `OpenResult` (opened / failed / skipped /
  keys_crafted) is **thrown away**; the screen reports "Loot opened" with a
  SUCCESS tone even when `opened == 0` and every craft returned HTTP 500. The
  only path to a failure message is an exception, and `open_all()` is written
  never to raise. → Render the result; DANGER when `opened == 0 and failed`.
- `loot_tab.py:122` — the button says "Open all", the preview card says "Will
  be opened", and the tooltip says "cannot be undone" — but `open_all()`
  defaults to `craft_keys_first=True` and **forges every key fragment into
  keys first**, and key fragments are excluded from the preview. The one
  irreversible step the user is never shown is the one that runs first. →
  Show forged keys in the preview, or make forging its own confirmed action.
- `loot_tab.py:40` — `open_requested` is emitted and connected nowhere.
- **Disenchant does not exist.** No UI control, no service method;
  `loot_service.py:9` explicitly excludes DISENCHANT recipes. The Loot tab is
  open-only. → Either build it or say so on the screen.

---

## 2. Implemented behaviour with no way to reach it

The engine implements all of these. Nothing in the Qt shell configures any of
them. Several are **on by default**.

| Behaviour | Config key | Default | Status |
|---|---|---|---|
| Arena synergy hover/pick | `arena_synergy_enabled` | **on** | no UI |
| Arena auto-lock | `arena_auto_lock` | on | no UI |
| Arena ban / instant ban | `arena_ban`, `arena_instant_ban` | — | no UI |
| Arena partner pairs table | `arena_pairs` | — | no UI |
| Arena fallback / legacy pick | `arena_fallback_pick`, `auto_pick` | — | no UI |
| Honor target strategy | `honor_strategy` | random | no UI |
| Auto-join friend lobby **list** | `auto_join_list` | — | no UI (the *switch* has one) |
| Blacklist dodge — **taskkills the client** | `dodge_blacklist` | — | no UI |
| Chat warden / toxicity scan | *no key at all* | always on | cannot be switched off |
| Auto-equip runes | `auto_runes_enabled` | — | legacy CTk sidebar only |
| ARAM auto-add played champion | `aram_auto_add_played` | — | legacy CTk sidebar only |
| ARAM auto-sort priority on draft exit | *no key* | always on | mutates the user's list |
| Mass-invite VIP filter | `vip_invite_list` | — | no UI |
| Match + telemetry DB writes | *no key* | always on | no UI |
| ARAM bench sniper | `aram_bench_swap` | — | **UI only existed in the dead `aram_tab.py`** |
| ARAM auto-reroll | `aram_auto_reroll` | — | same |

Two of these need attention before anything else:

- `automation.py:66` — `dodge_blacklist` is parsed once in `__init__`, has no
  UI, and its action is
  `subprocess.run(["taskkill", "/IM", "LeagueClient.exe", "/F"])` with **no
  try/except**. A stale value in `config.json` hard-kills the client mid-draft
  with no way to see or clear the list. On non-Windows it raises into `_tick`
  and feeds the 5-error killswitch.
- `automation.py:798` — `_handle_chat_warden` reads every lobby chat message
  every tick against a hardcoded keyword list, gated on **no config key at
  all**. There is no way to switch it off and no screen acknowledges it exists.

And one that silently overrides the user:

- `automation.py:594` — the bench sniper's effective default. The ARAM screen
  rendered the toggle from `config.get("aram_bench_swap", True)` while the
  engine reads it with default `False`; it is nevertheless effectively **on**
  because the `or priority_picker.enabled` fallback hits
  `DEFAULT_CONFIG["priority_picker"]["enabled"] = True` **with a hardcoded
  10-champion list (Nautilus, Xerath, …) the user never chose** — and
  `_aram_priority_names()` falls back to that same list when
  `aram_priority_list` is empty. Fresh installs bench-swap toward a
  developer's favourites. → One agreed default; delete the seeded list.
- `automation.py:1421` — `auto_join_enabled` defaults **True** in the engine
  and **False** in the UI row, and is absent from `DEFAULT_CONFIG`. On a fresh
  install the screen shows the switch off while lobby invites are being
  auto-accepted. Same shape for `auto_honor_enabled`.

---

## 3. Numbers and labels that are not what they claim

- `champ_select_viewmodel.py:178` — `_session_dict()` omits `queueId` and
  `gameConfig`, so `PriorityEngine._is_aram()` is **always False**. In ARAM the
  screen recommends from the Summoner's Rift list while the engine, reading the
  real session, picks from the ARAM list. **The displayed recommendation
  contradicts what automation will do.** It also omits `bans`. → Carry
  `queue_id` (already on `QueueState`) and the raw `bans` block through.
- `champ_select_viewmodel.py:271` — the confidence badge is derived from a
  **hardcoded rank** (`0 if not result.is_fallback else 1`), so
  `Confidence.LOW` is unreachable and the badge is a two-value fallback flag
  wearing a three-value costume. → Return the real rank from `evaluate_pick`.
- `champ_select_viewmodel.py:324` / `champ_select_tab.py:423` — every backup is
  stamped `Confidence.MEDIUM`, and each backup tile shows a priority badge that
  is **its index in the filtered list**, not the user's configured rank. A
  plausible-looking number that is not the user's data.
- `champ_select_viewmodel.py:290` — backups come from the global
  `"priority_list"` while the recommendation above them comes from the role or
  ARAM list. Whenever a role list is in play the two rows disagree.
- `champ_select_viewmodel.py:260` — reasons render verbatim as
  `Priority rank #1 for role 'MIDDLE'` — raw internal role enum and rank
  syntax on the flagship card. → Format with the `ROLE_LABELS` already present
  in the file.
- `account_manager.py:301`, `:458` — every account is written with
  `wallet = {"be": 0, "rp": 0}`. `_update_wallet` does fetch the real values,
  but **nothing in the Qt UI reads `wallet` at all**. Persisted zeros for a
  feature that was never surfaced. → Show BE/RP (as "unknown" before the first
  fetch) or delete the field and `_update_wallet`.
- `accounts_tab.py:481` — the unrecognised-account seed hardcodes
  `"region": "NA1"` and then never applies it; the editor's own `"NA1"`
  default is what gets saved. **The stored region is invented for every
  account added this way.** → Read the real shard, or drop the field.
- `profile_service.py:238` — `profile_icon_id` is parsed and never rendered;
  the identity card has no avatar.
- `profile_service.py:266` — `Profile.error` is composed with two genuinely
  useful sentences and **no caller reads it**; the tab shows fixed empty-state
  text instead, so "no games" and "the request failed" look identical.

---

## 4. Failures the user cannot see

Every one of these is a bare `except Exception: pass` (or a discarded return)
around the call that does the work.

- ~~`automation.py:1090, 1099, 1175, 1180`~~ **FIXED** (routed through `_act`,
  which checks the status and records the outcome) — **every draft PATCH discarded its
  result.** `LCUClient.request` returns `None` on failure and never raises, so
  "Draft: Locking Pick X" is logged whether or not the client accepted it, and
  `_last_draft_action_time` advances either way — a rejected lock is never
  retried and no error surfaces. Same at 480 (accept), 502 (requeue), 1260
  (reroll), 1313 (bench swap), 1528/1532 (friend lobby). Only the Arena ban
  lock at 887 checks a status code. → Route through `DraftActions._apply`,
  which already does this correctly.
- `automation.py:1759` — `mass_invite_friends` returns `count` regardless of
  whether the POST succeeded; the caller reports "N invited" either way.
- `accounts_tab.py:225` — `_subscribe_to_switches` returns silently if the
  import fails and wraps each `EventBus.on` in `except: pass`. With no
  subscription the switch still runs but no progress or outcome ever arrives,
  and **the busy lock set when Switch was pressed is never released** — the
  whole account list stays disabled with no message.
- `accounts_tab.py:847` — the same permanent freeze from a second cause:
  `login_account` returns silently when the switcher failed to import at
  construction, and that path emits no finished event.
- `accounts_tab.py:59` — `_DetectTask.run` has a bare `except`. Detection
  failing is indistinguishable from "nobody is signed in".
- `accounts_tab.py:414` — `_credentials_ok` returns **True** whenever
  `has_valid_credentials` raises, so a broken manager silently claims the
  credentials are fine. → Tri-state.
- `account_manager.py:327` — `_encrypt` logs and returns `""` when DPAPI
  fails; `add_account` stores that and returns a valid index. The editor
  reports success, the account is silently unusable, and it surfaces later as
  a "No password" badge with no explanation — under a caption that promises
  "Passwords are encrypted with Windows DPAPI". → Raise.
- `champ_select_tab.py:450` — `_sync_grid_state` returns silently on both
  exception paths, leaving **stale ban markings from the previous draft** on
  the tiles. → Clear before returning.
- `settings_tab.py:236` — the caption promises "Applied immediately when
  connected"; when not connected the method silently does config-only and
  still reports success. *(Partially addressed — the window now distinguishes
  the two cases. The caption should still be reworded.)*

---

## 5. Work done on the GUI thread

The window is frozen and unpaintable for the duration of each of these.

- `loot_tab.py:288` — `_on_open_all` runs the **entire multi-pass loot open**
  on the GUI thread: key forging, up to four passes, one `GET /player-loot`
  plus one recipes GET per stack per pass, N craft POSTs, and `time.sleep`
  between them, plus the rate limiter's own sleeps. The "Refreshing" status
  never even renders. `LootService` already accepts a `log` callback and a
  `stop_flag` that nothing supplies. → `QRunnable` + progress signals.
- `loot_tab.py:194` — `refresh()` is synchronous and is invoked from the
  connection-changed signal, so **simply connecting to League freezes the
  UI**.
- `profile_tab.py:247` — `load()` runs three blocking LCU GETs from
  `__init__`, `showEvent` **and** `connection_changed`.
- `champ_select_tab.py:354` — `_sync_lock_button()` calls
  `DraftActions.can_act()`, a **blocking LCU GET on the GUI thread**, from
  `_render()`, which runs on every state push (1 s). The draft screen issues a
  synchronous network request per second during the one phase that is
  latency-critical. → Derive "is it my turn" from the `actions` already in
  state.
- `draft_actions.py:348` — `can_act()` and `pending_type()` each fetch their
  own session; a refresh that calls both plus a hover costs three fetches
  against the rate limiter. → Accept an already-fetched session.

---

## 6. Two implementations of the same thing

- `ban_list_dialog.py:47` — `QtBanListDialog` is a **second, drifted ban
  editor**, and it is live: `main_window._on_configure_requested` opens it when
  the user arrives from the Automation screen, while the "Bans" nav entry opens
  `QtBanListTab`. The dialog has no Paste list, no rank/portrait rows, no
  import confirmation, and no `champion_activated` connection (double-click
  does nothing there but adds a ban on the tab). This is exactly the divergence
  the Priority/ARAM merge was written to end. → Embed `QtBanListTab` in the
  dialog chrome, keeping only the respect-hovers row.
- `priority_engine.py:88` — `evaluate_ban` is **never called**.
  `automation.py:1062` reaches past it into the private
  `_get_ban_priorities_for_role` and re-implements the availability, banned and
  hover filtering inline. The ARAM pick path is a *third* implementation, in
  champion names, at `automation.py:1183`. Three code paths, one of them
  tested. → Call `evaluate_ban(session)` and `evaluate_pick(session,
  aram=True)`.
- `main_window.py:244` — `configure_requested` is connected to **two**
  handlers, so clicking "Ban list" both navigates to the Bans tab *and* opens
  the modal. → Remove one.

---

## 7. Lifecycle, threading and ordering

- `automation.py:599` — the bench sniper and the reroll check run back-to-back
  against the **same session snapshot**, so the reroll reads the pre-swap
  champion and can reroll away the champion the sniper just acquired.
  Compounding: `_last_reroll_time` guards 2.0 s while the champ-select tick is
  also 2.0 s, so the guard does not reliably survive one tick. → Return the new
  id from the sniper; cooldown strictly greater than the tick.
- `automation.py:512` — on leaving champ select with the sniper off, the engine
  **silently rewrites the user's `priority_picker.list`**, promoting whatever
  they played. No key gates it, no UI mentions it.
- `automation.py:1548` — `_honor_handled` is set True whenever auto-honor is
  *off*, and that same flag then gates the skip-stats branch, coupling two
  independent switches.
- `automation.py:636` — `_get_local_player` indexes `p["cellId"]` while every
  other reader uses `.get("cellId")`. A team entry without the key raises into
  `_tick` and counts toward the killswitch.
- `automation.py:335` — `is_first` is computed and never read; `_is_first_tick`
  is written and read nowhere; `best_bench_idx` is assigned and never read;
  `self.stop_func` is stored and never called.
- `accounts_tab.py:508` — `refresh()` re-enables every row button with **no
  `_switching` check** and is wired to detection finishing, so a detection
  landing mid-switch re-enables Switch on every row. A second switch then
  returns `BUSY`, which the user reads as a failure.
- `accounts_tab.py:318` — `closeEvent` is the only place EventBus handles are
  disposed, and **a page inside a `QStackedWidget` never gets one**. The three
  switch subscriptions outlive the widget for the process lifetime;
  `_emit_safely` catching `RuntimeError` is the symptom being papered over.
  `main_window._subscribe_to_global_events()` has the same leak.
- `account_manager.py:420` — `get_active_index` and `get_account_count` read
  `_active_idx`/`_accounts` **without the lock** while the switcher's worker
  thread mutates them. `accounts_tab.refresh()` reads both separately, so a
  delete landing between them renders "Active" on the wrong row.
- `loot_service.py:168` — craft POSTs go through `LCUClient.request`, which on
  a disconnected client **appends the POST to an offline retry queue** and
  returns `None`. `_craft` reads that as "not connected", falls back to N
  individual POSTs which each queue another copy, and the whole queue is
  replayed on the next successful connect. **An irreversible bulk loot open can
  fire minutes later, multiplied, with no UI anywhere.** → Loot crafts must
  bypass the offline queue and abort on the first not-connected result.
- `loot_service.py:370` — on a failed bulk craft, `_craft` falls back to N
  singles without establishing whether the bulk call partially succeeded, while
  the transport is *also* auto-retrying 5xx POSTs. → Re-read `/player-loot`
  and recompute before falling back.

---

## 8. First real run — what it proved

`qt_startup.log` from a live Windows session (6,098 lines) is the first
evidence this repository has ever had. Two things came out of it, both now
fixed:

### 8.1 The sign-out/sign-in failure, diagnosed

    [RiotClientAPI] REQ -> DELETE /rso-auth/v1/session
    [RiotClientAPI] RES <- 204 /rso-auth/v1/session
    [RiotClientAPI] Signed out successfully
    [RiotClientAPI] REQ -> PUT /rso-authenticator/v1/authentication
    [RiotClientAPI] RES <- 201 /rso-authenticator/v1/authentication
    [RiotClientAPI] Sign-in error: invalid_prompt

`PUT /rso-authenticator/v1/authentication` **answers** an authentication
prompt; it does not create one. `sign_in` went straight to the PUT, so the
authenticator had nothing to answer and rejected it with `invalid_prompt` —
after the account had already been signed out. That is the whole reported
bug: the switch signs you out and then cannot sign anyone in.

**Fixed** — `RiotClientAPI._begin_authentication()` now does the
`POST /rso-authenticator/v1/authentication` that opens the RSO session
first, and `sign_in` refuses to send credentials if that step fails, so a
failure no longer costs you the session you were already in.

This was item 2 on the old prediction list. The prediction was right about
the mechanism. It still needs one real run to confirm the fix, and the log
will now say so in one line either way.

### 8.2 The log was 94% noise about a healthy client

    3255 x  HTTP 404 Error on GET /lol-lobby/v2/lobby
    2500 x  HTTP 404 Error on GET /lol-matchmaking/v1/search

`/lol-lobby/v2/lobby` returns 404 when you are not in a lobby, and
`/lol-matchmaking/v1/search` returns 404 when you are not searching. Both are
the client answering correctly. `_record_http_status_code` treated every
`>= 400` as an error, logged each one at WARNING, and fed them into the
sliding-window anomaly detector — which then fired 42 further warnings about
an error rate it had manufactured itself. 5,755 of 6,098 lines.

**Fixed** — `LCUClient.EXPECTED_404_ENDPOINTS` lists the endpoints where 404
means "not right now". They are no longer counted, logged, or fed to the
anomaly detector. Any other 404, and every other status, is unchanged.

### 8.3 Still unproven

Everything else below has still never run against a real client.

### Expected order of failure, unchanged

1. **Loot, entirely.** The only test that touches it asserts the button starts
   disabled. First to break: `_slot_loot_ids`' `chosen = primary_id if
   primary_id in ids else ids[0]` — for a multi-slot recipe it picks the first
   acceptable ingredient blindly rather than one you own, so the craft 400s and
   the fallback loop retries it N times.
2. **The account switch, end to end.** Tests cover `AccountSwitcher` against a
   fake `RiotSession`; nothing covers `RiotClientAPI`. Sign-in is
   `PUT /rso-authenticator/v1/authentication` while state is read from
   `GET /rso-auth/v1/session`. If the authenticator flow needs a continuation
   call, `wait_until_signed_in` polls a session that never flips and the switch
   reports `TIMED_OUT` after 25 s with the account half-authenticated. **This
   matches the sign-out failure reported and never diagnosed.**
3. **2FA.** `NEEDS_2FA` is produced and given a warning tone, but there is **no
   code path that submits a code** and no re-verification afterwards. The
   switch simply ends and the list keeps showing the old account as Active.
4. **Profile match history.** `parse_match` assumes `participants[0]` is you.
   If the client returns the full 10-participant list for any queue, **every
   match renders another player's KDA and win**, with no way to notice.
5. **Account detection.** `preferred_username` from
   `/riot-client-auth/v1/userinfo` is the only exact-match key. If it is absent
   or shaped differently, every signed-in user falls to a guess and the
   "Signed in as an unsaved account" card appears permanently for accounts that
   are in fact stored.
6. **Every draft PATCH** (see §4) — no result is checked anywhere, so the first
   real rejection will be invisible.

---

## 9. Dead code to delete

- `src/ui/qt/widgets/aram_tab.py` — fully superseded by
  `champion_list_tab.QtAramTab`. No construction site: not in `_build_page`'s
  builders, not in `sidebar.DEFAULT_TABS`; the only non-test importer is
  `tests/test_config_contract.py`, which imports it to assert the merge
  happened. Its own "Paste list" raises `AttributeError` on `self.current_ids`
  (the method here is `_current_ids`) and then on `self.list_widget` (here it
  is `prio_list_widget`) — copy-paste residue.
  **Do not delete it before porting the ARAM Bench Sniper and Auto Reroll rows
  onto the Priority screen** (shown when the mode is ARAM) — it is currently
  the only UI those two keys have ever had. Note also that
  `main_window._on_automation_configure` routes "configure" for both keys to
  the Priority screen, which has no control for either, so the user lands
  somewhere that cannot configure what they clicked.
- `src/ui/qt/widgets/transparent_overlay.py` — orphaned; imported by nothing.
  Its `click_through_changed` and `geometry_committed` signals are connected
  nowhere.
- `src/services/local_api.py` — the mobile-companion HTTP server. Reachable
  only from `core/main.py` (the CustomTkinter shell). It calls `app.after(...)`
  and other Tk-only APIs, so it cannot be pointed at the Qt shell as-is. Two
  `log_message` stubs. → Decide whether the companion feature survives.
- `src/services/queue_manager.py` — only `resolve_queue_id`/`resolve_mode_name`
  are used; `update_available_lobby_types` is reached only from the dead
  sidebar. The Play tab's own comment asks for a `QueueService.start_search()`
  seam that does not exist.
- `src/ui/app_sidebar.py` — the CustomTkinter shell. It is the only UI for
  `auto_runes_enabled` and `aram_auto_add_played` (§2).
- `components/field.py:49` — `text_changed` connected nowhere.
- `orb_widget.py:38` — `lock_in_requested` connected nowhere.
- `champion_list_tab.py:53-60` — `LIST_ICON_SIZE`/`LIST_ROW_HEIGHT` defined
  twice, identically. Merge residue.
- `src/ui/qt/__init__.py` — the only file in the repo with a UTF-8 BOM. It
  breaks any tool that opens sources as plain `utf-8`.
- `champion_grid.py:503` — `_apply_filters` rebuilds and re-sorts the full
  ~170-champion list on **every keystroke**, purely to recover display order,
  and reassigns `_has_champion_data` as a side effect. → Cache the order map in
  `load_champions`.

---

## 10. Suggested order of work

**First — things that act on the user's account without being asked**

1. `dodge_blacklist` taskkill: guard it, expose it, or remove it (§2).
2. Loot crafts bypassing the offline retry queue (§7) — this is the only
   irreversible action in the app that can fire unattended.
3. The seeded `priority_picker.list` and the `aram_bench_swap` /
   `auto_join_enabled` default mismatches (§2).
4. `_encrypt` returning `""` on DPAPI failure (§4).
5. Chat warden with no off switch (§2).

**Second — the draft, because it is the product**

6. Carry `queue_id` and `bans` into `_session_dict` so the screen and the
   engine agree about ARAM (§3).
7. Check the result of every draft PATCH; route them through
   `DraftActions._apply` (§4).
8. Ban vs Lock-in button labelling, and the double-click commit (§1.4).
9. A resume path for `pause()` (§1.4).
10. An idle state for the champ-select screen (§1.4).
11. Move `can_act()` off the GUI thread (§5).

**Third — controls that lie**

12. Tray toggle and hotkey rebinding taking effect without a restart (§1.3).
13. The Automation screen re-syncing from state, and not writing config on
    open (§1.2).
14. Owned filter: back it or remove it (§1.1).
15. Find Match reporting its result (§1.5).
16. Loot reporting its result, and previewing key forging (§1.8).

**Fourth — structural**

17. Port the ARAM rows, then delete `aram_tab.py` (§9).
18. Collapse `QtBanListDialog` onto `QtBanListTab` (§6).
19. Delegate-based list rows so drag-reorder stops destroying the dragged row
    (§1.6).
20. Background the Loot and Profile loads (§5).
21. EventBus handle disposal tied to widget lifetime (§7).

**Finally**

22. Run it on Windows against a real client and work down §8 in order. Until
    that happens, no claim in this repository about the LCU is evidence of
    anything.
