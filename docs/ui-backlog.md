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

## Next (highest impact first)
3. **Tab bar labels** — "Accts / Auto / Set" abbreviations read as noise;
   replace with icon tabs (with tooltips) or a 4-tab layout that fits full words.
   Add a visible selected-tab indicator (gold underline).
4. **Header controls** — emoji 🔒/🗕 glyphs render inconsistently (minimize is
   missing on Linux render); draw proper icons; align close/minimize/dock.
5. **Launch Client vs Find Match** — when offline, Find Match can't work; make
   Launch Client the primary action and disable/explain Find Match.
6. **Automations tab** — "⚡ ALL ON" master row reads as a heading; make it a
   compact labelled switch; use rune/item art consistently; group by phase
   (Queue / Champ Select / Post-game).
7. **Footer status** — "Waiting for client…" duplicates the header; merge into a
   single status source or use the footer for last-action log only.
8. **Friend rows** — truncate long names with ellipsis; status colour dot
   contrast; VIP / auto-join indicator as icon, not text.
9. **Champ Select surface** — priority grid: champion portraits larger, lock
   state obvious, ban list uses real portraits.
10. **Loot tab** — empty/offline state, item art grid, disenchant totals.
11. **Accounts tab** — empty state, rank emblems, clear active account.
12. **Settings tab** — group into sections, consistent row height, hotkey
    recorder focus states.
13. **Contrast pass** — `colors.text.muted` (#6C757D) is ~3.8:1 on cards; lift
    it in `design_tokens.json` and audit all captions.
14. **Focus rings** — keyboard focus visible on CTkButtons/icon buttons, not
    only LolToggle.
15. **Queue states** — matchmaking/ready/champ-select/in-game header states:
    timer tabular figures, progress bar meaning, Requeue/Dodge hierarchy.
