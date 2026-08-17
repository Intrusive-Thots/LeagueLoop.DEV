---
name: Add Typed Event or Service
description: Wire a new typed EventBus event, state slice, or DI-registered service into the app spine
---

# Add Typed Event or Service

The architectural spine is three pieces that decouple UI, automation, and LCU:

- **EventBus** (`src/core/events.py`) — process-wide pub/sub singleton.
- **StateManager / ApplicationState** (`src/core/state.py`) — immutable,
  thread-safe state; emits `EventType.STATE_CHANGED` on every mutation.
- **ApplicationContainer** (`src/core/container.py`) — owns the service graph
  (DI). Services are reached as `container.lcu`, `container.config`, etc.

## A. Add a typed event

1. Add a member to `EventType` in `events.py` (the value is the wire string):

```python
class EventType(Enum):
    ...
    LOOT_UPDATED = "loot_updated"
```

2. **Emit** from the producer (a service). Use the singleton — do not
   instantiate a new bus:

```python
from core.events import EventBus, EventType, Event
EventBus.emit(EventType.LOOT_UPDATED.value, {"count": n})
# or structured:
EventBus.emit_typed(Event(type=EventType.LOOT_UPDATED, data={"count": n}))
```

3. **Subscribe** from consumers (UI/other services). `on()` returns a
   `SubscriptionHandle` — dispose it on teardown to avoid leaks:

```python
self._sub = EventBus.on(EventType.LOOT_UPDATED.value, self._on_loot)
# later: self._sub.dispose()
```

- Listener exceptions are isolated (logged, others still run) — but keep
  callbacks fast and non-blocking.
- **THREAD-001**: if a callback updates Qt widgets and may fire off the GUI
  thread, marshal with `QTimer.singleShot(0, ...)` (or `EventBus.invoke_thread_safe`).

## B. Add a state slice / field

`ApplicationState` is composed of frozen dataclasses (`ClientState`,
`QueueState`, `ChampSelectState`, `AutomationState`, `AccountState`, `UIState`).

- New **field** on an existing slice: add it to that frozen dataclass with a
  default, then mutate atomically via the matching `StateManager.update_*`:

```python
sm.update_automation(auto_disenchant=True)   # does dataclasses.replace + notifies
```

- New **slice**: add a `@dataclass(frozen=True)` class, add it as a
  `field(default_factory=...)` on `ApplicationState`, and add an
  `update_<slice>()` method that mirrors the existing ones (replace under
  `self._lock`, then `self._notify_state_change()`).
- Read state via the snapshot property: `container.state_manager.state` — never
  mutate the dataclasses in place.

## C. Register a service in the container

Add construction to `ApplicationContainer.__init__` (import inside the method,
as the file does, to keep import order lazy):

```python
from services.loot_service import LootService
...
self.loot: LootService = LootService(self.lcu, bus=self.bus)
```

- Services that need runtime callbacks use a `create_*` factory method (see
  `create_automation`); simple singletons are constructed inline.
- Add teardown to `shutdown()` if the service holds threads, sockets, or the DB.
- Consumers receive `container` and read `container.loot` — never import a
  service as a global singleton.

## Rules

- One EventBus singleton, one StateManager (owned by the container). Don't
  create parallel instances.
- State is immutable — always go through `update_*`; never assign to a frozen
  field.
- Scope: LCU only.

## Verify

- Unit-test event flow and state transitions like
  `tests/test_core_events_state.py` / `test_state_and_events.py` (subscribe,
  emit/update, assert the callback fired and the snapshot changed).
- Run the full suite (see `run_tests`).
