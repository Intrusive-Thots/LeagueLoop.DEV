---
name: connection_drop_and_theme_ram_optimization
description: Reusable pattern for LCUClient connection drop diagnostics, event loop latency telemetry logging, and DesignTokens RAM memory footprint optimization via string interning.
---

# Connection Drop Diagnostics & Theme RAM Footprint Optimization Skill

## Overview
This skill records connection drop reasons/frequency and event loop dispatch latency in `LCUClient`, alongside RAM footprint optimization of UI design token dictionaries using `sys.intern()`.

## Usage Pattern

### 1. Recording Connection Drop Diagnostics
In `LCUClient`:
```python
def _record_connection_drop(self, reason: str):
    with self._ws_telemetry_lock:
        self._connection_drop_count += 1
        self._last_drop_reason = reason
        self._drop_history.append((time.time(), reason))
        if len(self._drop_history) > 20:
            self._drop_history.pop(0)
```

### 2. Event Loop Dispatch Latency Tracking
During WebSocket message processing:
```python
t_loop_start = time.perf_counter()
# ... process ws message ...
loop_dur_ms = (time.perf_counter() - t_loop_start) * 1000.0
with self._ws_telemetry_lock:
    self._event_loop_latency_ms = round(loop_dur_ms, 3)
```

### 3. Theme Memory Optimization & String Interning
In `DesignTokens`:
```python
def _intern_tokens(obj):
    if isinstance(obj, dict):
        return {sys.intern(k) if isinstance(k, str) else k: _intern_tokens(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_intern_tokens(i) for i in obj]
    elif isinstance(obj, str):
        return sys.intern(obj)
    return obj
```
