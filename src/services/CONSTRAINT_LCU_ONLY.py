"""
LeagueLoop Architecture Constraint
====================================
This application ONLY interacts with the League Client (LCU API).
It NEVER interacts with the running game process.

Allowed: LCU REST API, LCU WebSocket, Riot Client API, lockfile reading
Forbidden: port 2999 (Live Client Data API), game memory, in-game overlays

If you find yourself connecting to port 2999 or reading game data,
STOP — that is a violation of this constraint.
"""
