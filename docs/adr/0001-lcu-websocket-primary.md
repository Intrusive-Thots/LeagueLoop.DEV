# ADR-0001: LCU WebSocket as primary wake path

## Status

Accepted

## Context

The Automation Engine must react quickly to Ready Check, Champ Select, and other Gameflow Phase changes. Pure HTTP polling either misses short-lived prompts or burns CPU/LCU capacity with aggressive intervals—especially harmful while In Progress (CEF client sensitivity).

## Decision

Treat LCU WebSocket subscriptions as the primary wake path for automation. HTTP polls remain as reconciliation and self-heal when the socket is stale or disconnected. While In Progress, suppress most HTTP traffic and only wake on gameflow-phase events (plus sparse process/phase probes).

## Consequences

- Ready Check and Champ Select actions stay low-latency without a tight global poll.
- Implementation must handle reconnect, ghost Champ Select, and process-vs-LCU phase corrections.
- Telemetry around WAMP/WebSocket latency is a first-class ops concern, not optional.
- Callers should not assume every state change was observed via HTTP.

## Alternatives considered

- **HTTP-only polling** — simpler, but either slow to accept matches or heavy on the client.
- **UI automation / pixel macros** — brittle across patches and DPI; rejected for primary flows.
