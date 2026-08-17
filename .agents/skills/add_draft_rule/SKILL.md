---
name: Add Draft Rule
description: Add or tune a scoring/availability rule in the champion draft priority engine
---

# Add Draft Rule

The draft decision system is `src/services/draft/` — the core product logic
behind Priority Sniper, Draft Assistant, and the Arena Synergy Picker. It is
**deterministic and unit-tested**; keep it that way.

## Modules

| File | Responsibility |
|------|----------------|
| `role_detector.py` | `RoleDetector.detect_role_from_session(session)` → assigned role |
| `validation.py` | `ActionValidator.is_champion_available(champ_id, session, is_pick=)` |
| `priority_engine.py` | `PriorityEngine.evaluate_pick/evaluate_ban` → `DraftEvaluationResult` |

`DraftEvaluationResult` (frozen dataclass):
`action_type, champion_id, score, role, is_fallback, reason`.

## Where each kind of rule goes

- **Availability rule** (a champ should/shouldn't be pickable/bannable — e.g.
  teammate-respect, already-hovered, global ban): extend
  `ActionValidator.is_champion_available`. Return `False` to exclude.
- **Scoring rule** (change *which* available champ wins): adjust the score
  math in `PriorityEngine.evaluate_pick` / `evaluate_ban`.
- **Role inference**: extend `RoleDetector`.

## Scoring model (keep it deterministic)

Current pick score:

```python
priority_weight = max(100.0 - (rank_idx * 10.0), 10.0)   # earlier in list = higher
role_match_bonus = 20.0 if self._is_champion_valid_for_role(champ_id, role) else 0.0
total_score = priority_weight + role_match_bonus
```

To add a factor (e.g. a synergy bonus), add a named term and fold it in — do
not introduce randomness, wall-clock time, or set iteration order:

```python
synergy_bonus = 15.0 if self._has_synergy(champ_id, session) else 0.0
total_score = priority_weight + role_match_bonus + synergy_bonus
```

Always populate `reason` with a human-readable explanation and set
`is_fallback=(rank_idx > 0)` — the UI and logs surface both.

## Config-driven priorities

Priority/ban lists come from `ConfigManager`, role-keyed with fallback:
`priority_<ROLE>` → `priority_list`; `ban_priority_<ROLE>` → `ban_priority`.
New user-tunable lists follow the same `_get_*_priorities_for_role` pattern and
must coerce entries to `int` defensively.

## Rules

- Pure functions of `(session, config)`. No LCU calls, no I/O, no global state
  inside the engine — the caller in `automation.py` performs the actual LCU
  pick/ban.
- Teammate Respect: never ban/pick over a champion a teammate is hovering —
  enforce in `ActionValidator`, covered by `test_automation.py`.
- Scope: LCU champ-select session data only.

## Verify

- Add/extend cases in `tests/test_draft_engine.py` (and `test_automation.py`
  for engine→LCU wiring). Assert exact `score`/`reason` for representative
  sessions so scoring stays deterministic.
- Run the suite (see `run_tests`); `test_draft_engine.py` must pass.
