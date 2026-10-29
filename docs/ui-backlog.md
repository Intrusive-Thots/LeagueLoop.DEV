# LeagueLoop UI backlog

Prioritized UX/UI work for the CustomTkinter sidebar. Work on the `ui-polish`
branch; keep the test suite green; render with Xvfb before/after each item.
Direction: Operate mode — show only what matters mid-session, real
champion/item/rune art over text, honest offline/empty states, gold as the
single accent.

Render harness used so far: a small script that builds `SidebarWidget` in a
bare `ctk.CTk()` root with a stub config and a real `AssetManager`, run under
`xvfb-run` at 300×1000, then `switch_tab(<tab>)` and capture.

## Done
1. **Honest offline Play tab** (session 1) — header no longer claims
   "● Connected / Queue: Idle" before any client exists (now "Client not
   running / ○ Offline", muted); Friend List shows "No client connected"
   or "Loading friends…" instead of a blank box; Invite All / Export are
   disabled when there's nothing to act on.
2. **Quick icon bar + toggle legibility** (session 1) — all 7 quick automation
   icons fit in one row at sidebar width (was 6 + 1 orphan); OFF toggles now
   draw a visible track and dimmed knob instead of a lone floating dot.

3. **Tab bar** (pass 1) — full labels Play/Loot/Accounts/Auto/Settings with drawn
   icons, gold underline + bright label for the active tab; active tab now shown at startup.
4. **Header glyphs** (pass 1) — drawn lock/unlock, minimize, close icons (`ui/components/glyphs.py`);
   undocked state is neutral grey, not red.
5. **Launch Client primary when offline** (pass 1) — gold Launch above a disabled Find Match.
6. **Automations** (pass 1) — "All automations" switch row with "N of 7 on" summary;
   rows grouped into QUEUE / CHAMP SELECT / POST-GAME cards; gear sits by the toggle.
7. **Footer status** (pass 1) — footer reads "No recent actions" instead of repeating connection state.
8. **Friend rows** (pass 1) — names/status ellipsized with full-name tooltip; green/amber/grey
   presence dots (offline no longer red); gold auto-join glyph.
9. **Champ select grid** (pass 1) — portraits 40→48px; per-row count derives from `CELL_PITCH`.
10. **Loot** (pass 1) — honest "No client connected" state, actions disabled offline, emoji removed,
    single gold progress, "—" placeholders. (Item art grid needs a live client — see #20.)
11. **Accounts** (pass 1) — glyph empty state + gold "Add account"; "Loading accounts…" placeholder
    instead of a blank tab. Rank emblems: N/A, the tool has no rank data.
12. **Settings** (pass 1) — PERFORMANCE / DIAGNOSTICS sections, inline hotkey rows, secondary buttons.
13. **Contrast** (pass 2) — `colors.text.muted` #6C757D → #8A93A0 (≈5.3:1 on #0F1923), placeholder
    fallback too; League Client button now dark-on-gold (was white-on-gold ≈2.2:1).
14. **Focus rings** (pass 2) — `components/focus_ring.py`: CTk buttons/switches/checkboxes made
    Tab-focusable (Space/Return activate); 2px gold ring on keyboard focus only (focus-visible),
    incl. LolToggle and RiotButton. Verified with real xdotool Tab events.
15. **Session header states** (pass 2) — one `HEADER_STATES` table: offline / queue idle / match
    found / champ select / in game / post-game / reconnect; champ select gold (was purple).
16. **Accounts header** (pass 2) — drawn plus / launch / play glyphs replace "+", 🚀, ⚔.
17. **Loot "," artefact** (pass 2) — idle progress nub hidden (progress colour = track).
18. **Power button** (pass 2) — "▶ Active" → bolt glyph + "Auto on" / "Auto paused".
19. **Tooltip overflow** (pass 2) — wraplength 240 and clamped inside the window/screen.
20. **Loot grid (mocked)** (pass 2) — rows: chest glyph badge, neutral border, gold only when
    openable, "Ready"/"Needs key"/"Blocked" without emoji, Open button no longer squeezed out
    by long names (13-char ellipsis + tooltip). Champ select verified as header state (mocked).
21. **Kill Processes** (pass 2) — RiotButton `style="danger"` red outline.
22. **Iconography sweep** (pass 2) — Find Match/Play Again, Invite All, toggle gear, "👥 Team"
    now drawn glyphs or plain text.

24. **Disabled contrast** (pass 3) — disabled token #3A4654 → #6B7584 (≈3.8:1); RiotButton recolours
    its glyph to the disabled colour and restores it on enable; sidebar lock fallback muted.
25. **Match Found toast** (pass 3) — drawn swords glyph (emoji→glyph map for all toasts), themed tint.
26. **Motion audit** (pass 3) — toast slide-in is the one entrance; confetti off; tooltip and
    priority-grid tip slides removed; toggle ambient pulse opt-in (steady gold by default).
27. **Section chevrons** (pass 3) — `set_chevron()` drawn chevrons in all collapsible headers.
28. **Spacing rhythm** (pass 3) — 39 padx/pady literals snapped to 4/8/12.
29. **Error states** (pass 3) — Loot "Couldn't read your loot" + Retry; Accounts amber
    "Account check failed" row + Retry (mocked render; real detection failure needs live client).
30. **Account row buttons** (pass 3) — Switch dark-on-gold + play glyph, Sign in amber outline,
    Sign out red outline (no ⏻), ▲▼✎✕ → drawn chev/pencil/close glyphs; empty-state widow fixed.
31. **Remaining text glyphs** (pass 4) — friend-list menu Enable/Disable Auto-Join with drawn
    check/close image; priority grid Apply (check, dark-on-green), Delete Selected (close),
    Clear All (new trash glyph); draft "Saved" check; sidebar fix-ping/kill-proc statuses use
    drawn refresh/check/close via `SettingsRow.set_status(icon=)`; swords glyph redrawn.
32. **Toast capture** (pass 4) — toast is an in-window placed frame (not a Toplevel); harness
    `LL_TOAST="msg|icon|theme"` shows one before capture. Fixed 5px root strip above the first
    toast, lift on show, 8px stacking gap, error tint #FF7A70, wraplength 200 for the 300px window.
33. **Type scale** (pass 4) — `TYPE_SCALE` in factory.py (micro 9 / small 10 / caption 11 /
    body 12 / header 14 / title 15); 9 off-scale literals (7, 8, 13) snapped.
34. **Pressed states** (pass 4) — `pressed_state.py`: every CTkButton gets a 110ms pressed fill
    (light fills darken 18%, dark fills tint toward gold) via a first "LLPressed" bindtag; 4 tests.
35. **IconButton** (pass 4) — NOT dead: `ui.components.buttons.IconButton` exists and is used by
    collapsible Cards (loot, arena, friend list, sidebar). Kept. (Pass-3 note was wrong.)
36. **Loot empty-state clipping** (pass 4) — caption wraplength 220 overflowed the ~195px box
    (".oot shows up…"); now 160 with a non-breaking last space (no widow).

## Done (pass 5 — final)
37. Last text ✕/✓/⚡ → drawn glyphs: ban/ARAM/editor/arena close buttons, accounts Cancel/Save/
    Update, password eye (gold when shown), hotkey success check, arena labels de-emojied.
38. Harness `LL_MENU` captures the friend-list context menu; menu restyled (distinct bg, solid
    1px border, pixel font). Popup windows (ban, ARAM, editor, mini player, About) captured.
- Sweep: undo/eye/save glyphs added; priority-grid "+ Add" → plus glyph, dark-on-gold text,
  gold hover, disabled "Added" check; ✨/⇧ removed; mini-player ×/[ ] → glyphs; hand cursors
  on clickable labels; ~32 spacing values snapped to 4/8/12; editor subtitle wraps; About
  footer no longer collides with Close; fixed `lambda e=e` closure bug in app_sidebar.
- Kept deliberately: ●/○ status dots and ★ rank text (data, not chrome); About title 16
  (display); loot category emoji (live data only); friend-list/toast paddings that drive layout.

## Pass 7 audit (2026-10-29, offline fixtures, Xvfb renders of every tab/popup/toast/menu)
Priority order. #23 stays parked.

- [x] 39. **P1 Popups open off-screen** — `about_page.py`, `automation_editor.py` centred on the
  300px sidebar with no clamp (About/editor opened at negative x, title bar unreachable);
  `ban_list_window.py` / `aram_list_window.py` only clamped x/y<0 to 100 and ignored
  right/bottom edges. New `ui/components/window_place.py` (`clamp_rect`, `work_area_for` —
  Win32 monitor rcWork, so left-hand monitors with negative coords stay valid —
  `place_on_screen`, `centre_on`) used by all four; 5 tests in `tests/test_window_place.py`.
- [x] 40. **P1 Settings ghost buttons** — `app_sidebar.py` "Open Screenshots Folder" and About
  "Info & Legal" were transparent fixed-width buttons, bold text floating indented off the
  label column with no affordance. Now `SettingsActionRow`s ("Screenshots folder · Captured in
  debug mode · Open", "League Loop · Version … · Info & Legal") matching Fix Ping/Download.
- [x] 41. **P2 Settings row typography** — `SettingsActionRow` titles now regular body like
  the toggle/hotkey rows. `SettingsToggleRow` measures its label on `<Configure>` and sets a
  balanced, left-justified wraplength (`balanced_wrap`) instead of the hard-coded 170 →
  "Auto-save replays / after each match", no centred orphan.
- [x] 42. **P2 Replay-folder copy** — default + empty-path text is "Replay folder shows when
  League is open." (one line); label `height=0` so it doesn't float in CTk's 28px box.
- [x] 43. **P3 Empty-state scrollbars** — new `ui/components/scroll_autohide.py`
  (`autohide_scrollbar`) shows a CTkScrollableFrame's bar only on overflow; wired into friend
  list, accounts, loot vault, arena, AutomationEditor, priority grid, activity log and
  Settings/Automations. Pins canvas height before hiding (no flip loop) + flap guard; tests in
  `tests/test_scroll_autohide.py`.
- [x] 44. **P3 Minor** — Loot Refresh/Claim now sit in a uniform 2-column grid (pack
  `expand` only split spare space, so "Refresh" was wider). AutomationEditor puts the
  type-specific fields in a card matching the "Show Icon on Main Page" card, captions wrap at
  `FORM_WRAP` (300) with `_balance_captions` evening two-line captions (no "pop." / "on main
  page" orphans); `tests/test_editor_caption_wrap.py`.

## Blocked (needs a live League client)
23. Real LCU phase transitions + status pill; champ-select pick/ban panel and ARAM bench
    live highlight; loot opening/crafting results, item art, loot category icons; real
    account-detection failures; friend list with real friends + invite flow; arena synergy
    pairs in a live draft.

### #23 live-client pass (pass 6, 2026-10-22, real LCU on James's PC, read-only GETs)
- **Live-verified:** LCU connect via lockfile; phase `None` → status pill "Queue idle"; real friend list (70 friends) renders with avatars; signed-in-but-not-stored account detection message; Loot tab with real counts (0 openable, 6 keys) and "Nothing to open" empty state.
- **Fixed from live data:** friends on mobile / in Riot Client / playing other Riot games were counted "online" and would have been mass-invited → new `services/friend_presence.py` (kinds, colours, status text, `is_invitable`); badge + Invite All now count invitable friends only. Friend status line was clipped to nothing (two 28px labels in a 40px row) → fixed. Season-pass claim reported phantom "Claimed N rewards" every run → skip claim POST when `rewardsCount <= 0`.
- **Fixtures:** `tests/fixtures/lcu/{friends,loot,summoner,phase}.json` (anonymised live payloads), `tests/test_live_lcu_payloads.py`.
- **Still blocked (James not in phase / forbidden):** champ-select pick/ban panel, ARAM bench highlighting, arena synergy, phase transitions, loot opening art + category icons (nothing openable), real invite flow. No champ-select/lobby payloads could be captured (404 outside those phases). TFT pass claim still counts any 2xx.
- **Incident:** during live verification the app's loot automation claimed rewards on the real account (11 rewards at 23:23:04 UTC-4 incl. 2×750 BE, 25 OE, event pass rewards; an Open All that opened 0). Nothing disenchanted, crafted, queued or invited. Future live runs must use a sandbox config with all loot automation off and no GUI clicks.
