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

## Next (pass 4+)
23. **Live-client only** (partially mocked) — real LCU phase transitions, champ-select pick/ban
    panel, loot opening/crafting results and item art, real account-detection failures.
31. **Remaining text glyphs** — friend list "✕ Disable / ✓ Enable Auto-Join", priority grid
    "✕ Delete Selected"/"✓ Apply", draft "✓ Saved", sidebar action-log ✓/✗.
32. **Toast screenshot** — toast is a Toplevel; harness captures root only. Extend harness.
33. **Type scale** — audit font sizes (9/10/11/12/13) and line-height rhythm to a 4-step scale.
34. **Pressed states** — buttons have hover but no distinct pressed colour.
35. **Dead code** — `cards/card.py` imports non-existent `IconButton`; confirm and remove.
