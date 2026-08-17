"""
Centralized Riot ID / summoner name resolution.

Riot migrated from summoner names to Riot IDs (gameName#tagLine).
LCU and other payloads return different combinations of fields.
Always use resolve_riot_id() instead of ad-hoc field access.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional


def resolve_riot_id(data: Optional[Mapping[str, Any]], *, fallback: str = "") -> str:
    """
    Resolve a displayable Riot ID or name from heterogeneous payload shapes.

    Preference order:
      1. gameName#tagLine (when both present)
      2. gameName alone
      3. displayName
      4. summonerName
      5. name
      6. fallback

    Returns stripped string; empty string if nothing found (or fallback).
    """
    if not data:
        return fallback or ""

    game_name = (data.get("gameName") or "").strip()
    tag_line = (data.get("tagLine") or data.get("tagline") or "").strip()
    if game_name and tag_line:
        return f"{game_name}#{tag_line}"
    if game_name:
        return game_name

    for key in ("displayName", "summonerName", "name"):
        val = data.get(key)
        if val and str(val).strip():
            return str(val).strip()

    return fallback or ""


def resolve_riot_id_lower(data: Optional[Mapping[str, Any]], *, fallback: str = "") -> str:
    """Same as resolve_riot_id but lowercased (for comparisons / search)."""
    return resolve_riot_id(data, fallback=fallback).lower()
