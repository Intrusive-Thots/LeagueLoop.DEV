# Qt migration status

Phase 2 required three decisions to be documented rather than assumed.

## The orphaned overlay — `src/ui/qt/widgets/transparent_overlay.py`

```
Used:                no
Imported by:         nothing (verified by import graph, not by grep alone)
Signals:             click_through_changed, geometry_committed — both connected nowhere
Win32 functionality: sets WS_EX_TRANSPARENT / WS_EX_LAYERED so clicks pass through
Size:                12 KB
```

**Decision: archive the concept, keep the one useful part, do not delete yet.**

The click-through technique is the only thing in it worth having, and it is
worth having — a companion panel pinned beside the client is a candidate for
click-through when idle. But the file also carries a drag-to-resize handle, a
geometry-commit protocol and a second positioning scheme, none of which
survive contact with `CompanionAnchor`.

It stays until the compact panel exists and we know whether click-through is
wanted. If it is, the ~15 lines of ex-style manipulation move into the Qt
layer as a small helper. If not, the file goes. It is on the register so it
does not quietly become permanent.

It does **not** get maintained in the meantime.

## The compact panel — `orb_widget.py`

```
Current:  280x72, fixed
Contains: a phase label, a recommendation label, a Lock button, a restore button
```

Phases 9–11 describe something quite different: header, current state, primary
action, automation toggles, champion grid, bottom status — roughly 320x600.

**Decision: the orb is the minimised/quick-access representation, not the
compact runtime panel.** They are two different things and the app wants both:

* **Orb** — the "get out of my way" state. Stays as it is.
* **Compact panel** — the runtime companion. To be built in Qt, as its own
  widget, reusing the existing components and tokens.

Both attach through the same `CompanionAnchor`, so the positioning work done
in Phase 2 serves whichever is on screen. Building the compact panel is the
next phase; nothing about it was assumed here.

## The CustomTkinter shell

```
Entry point:  run.py  ->  core/main.py  ->  ui/app_sidebar.py
Status:       legacy, frozen
```

**Decision: `run_qt.py` is the canonical entry point.** The Qt shell is where
all UI work goes.

The legacy shell keeps receiving:

* correctness fixes that stop it crashing or acting on the account without
  being asked (it shares the whole `services/` layer, so a service bug is a
  bug in both);
* whatever is needed to keep it importable.

It does **not** receive layout, styling or UX work. The screen recording that
prompted this phase shows its problems, and re-laying out a shell that is
being deleted would be the most expensive way to fix them.

### What still has to move before it can go

| Feature | Only in the CTk shell |
|---|---|
| `auto_runes_enabled` | the switch exists only in `app_sidebar` |
| `aram_auto_add_played` | same |
| Mobile companion HTTP API | `services/local_api.py` calls `app.after(...)`, which is Tk-only |
| Friend list / mass invite UI | `ui/components/friend_list.py` |
| Arena pairs editor | `ui/components/game_tools/arena_tool.py` |

Until those are ported, `run.py` stays. Both shells write to the same config
and the same `services/` layer, so they cannot silently diverge on behaviour —
only on presentation, which is the point.

## Per-monitor DPI

Qt handles it: `PassThrough` rounding policy plus per-monitor-v2 awareness set
before `QApplication` exists. `run.py` calls `SetProcessDPIAware()` — system
DPI, one factor for all monitors — which is correct for Tk and must **not** be
copied into the Qt path. Doing so would double-scale.

Verified at 100 / 125 / 150 / 175 / 200 % by `tools/check_scaling.py`, which
walks the widget tree and fails if any child escapes its parent.
