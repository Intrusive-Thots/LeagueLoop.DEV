---
name: lcu_ws_latency_telemetry
description: Performance logging and telemetry for WAMP WebSocket event dispatch latency in LCUClient.
---

# LCU WebSocket Event Latency Telemetry Skill

## Overview
Provides real-time event dispatch latency measurement and rolling telemetry stats for LCU WebSocket connections.

## Key Logic
- Wrap message receive/dispatch loop with high-resolution `time.perf_counter()`.
- Calculate processing latency in milliseconds: `latency_ms = (t_dispatch - t_recv) * 1000.0`.
- Maintain rolling window of samples (`self._ws_latency_samples`, max 200 items).
- Log `Logger.warning` when event latency exceeds 50.0 ms.
- Expose summary metrics via `get_ws_telemetry()`.
