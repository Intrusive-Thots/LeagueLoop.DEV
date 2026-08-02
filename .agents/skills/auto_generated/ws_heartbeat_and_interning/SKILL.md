---
name: ws_heartbeat_and_interning
description: Reusable skill for implementing dynamic WebSocket ping timeout reset loops and memory optimization using sys.intern and immutable tuples in Python services.
---

# WS Heartbeat & Memory Interning Skill

## Purpose
When maintaining long-lived WebSocket connections (e.g. LCU WAMP WebSockets) or managing high-volume cached metadata (e.g. DDragon champion tags and Meraki roles), two common issues arise:
1. **Silent Connection Drops**: WebSockets can silently drop without closing TCP sockets, leaving receiving loops blocked indefinitely.
2. **RAM Bloat**: Repeated strings stored across thousands of dictionary entries create excessive memory allocation overhead.

## Pattern 1: Dynamic WebSocket Ping Timeout Reset
Instead of blocking infinitely on `ws.recv()`, pass a timeout parameter and track `last_msg_timestamp`. Reset the connection when staleness exceeds the threshold:

```python
import time
from utils.logger import Logger

while self._ws_should_run:
    try:
        message = ws.recv(timeout=15)
        self._ws_last_msg_timestamp = time.time()
    except TimeoutError:
        stale_age = time.time() - self._ws_last_msg_timestamp
        if stale_age >= self._ws_stale_timeout_s:
            Logger.warning("LCU_WS", f"Stale WS connection ping timeout ({stale_age:.1f}s). Resetting.")
            self._ws_stale_reset_count += 1
            try:
                ws.close()
            except Exception:
                pass
            break
        continue
```

## Pattern 2: Memory String Interning with Immutable Tuples
When parsing JSON structures with repeated string tokens (e.g. `"Fighter"`, `"Tank"`, `"TOP"`, `"SUPPORT"` -> `"UTILITY"`), wrap string items in `sys.intern()` and store as `tuple` rather than `list`:

```python
import sys

# Intern strings & save as immutable tuple
raw_tags = info.get("tags", [])
self.id_to_tags[cid] = tuple(sys.intern(str(t)) for t in raw_tags)

clean_pos = tuple(
    sys.intern("UTILITY" if p == "SUPPORT" else str(p))
    for p in positions
)
self.champ_roles[cid] = clean_pos
```

## Benefits
- Prevents hung/stale socket states while keeping telemetry diagnostic visibility (`last_msg_age_s`, `stale_reset_count`).
- Dramatically cuts Python dictionary object overhead and garbage collection pressure across thousands of champion asset lookups.
