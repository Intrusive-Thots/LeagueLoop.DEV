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

## Next (highest impact first)
13. **Contrast pass** — `colors.text.muted` (#6C757D) is ~3.8:1 on cards; lift
    it in `design_tokens.json` and audit all captions.
14. **Focus rings** — keyboard focus visible on CTkButtons/icon buttons, not
    only LolToggle.
15. **Queue states** — matchmaking/ready/champ-select/in-game header states:
    timer tabular figures, progress bar meaning, Requeue/Dodge hierarchy.


## Found in pass 1
16. **Accounts header** — Riot/League Client buttons still use emoji (🚀/⚔) and a bare "+".
17. **Loot VAULT INVENTORY** — summary line shows a stray "," when empty.
18. **"▶ Active" in session header** — automation power state reads like connection state; reword.
19. **Hotkey recorder tooltip** — "Click to record a new hotkey" overflows the 300px window edge.
20. **Loot item grid / Champ select states** — verify with a live client (can't render offline).
21. **Kill Processes** — red text button on dark card; consider danger-outline style.
