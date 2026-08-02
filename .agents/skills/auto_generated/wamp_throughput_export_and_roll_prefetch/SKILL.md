---
name: wamp_throughput_export_and_roll_prefetch
description: WAMP event throughput rate metrics export and Champ Select roll phase asset pre-fetching pipeline optimization.
---

# WAMP Throughput Export & Champ Select Roll Prefetch Skill

## Overview
Provides real-time event throughput tracking (events per second) for LCU WebSocket connections and optimizes asset pre-downloading during Champ Select roll phases.

## Implementation Standard
1. **Event Throughput Calculation**:
   - Maintain rolling 10-second timestamp list (`_ws_event_timestamps`) in `LCUClient`.
   - Compute `throughput_eps = recent_count / 10.0` and `overall_throughput_eps = total_events / total_elapsed_seconds`.
   - Export via `get_ws_telemetry()`.
2. **Champ Select Asset Prefetching**:
   - Extract team picks, pick intents, and bench champion IDs during Champ Select roll phases in `AutomationEngine._handle_champ_select()`.
   - Resolve champion keys and check `self.icons` memory cache in `AssetManager.preload_champion_icons()`.
   - Asynchronously enqueue missing icons into worker thread queue to eliminate rendering delay in compact Orb mode and main UI.
