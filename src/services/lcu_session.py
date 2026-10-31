"""
What counts as "a new League session" for account-scoped UI.

A bare connected/disconnected flag misses the case that matters after an
account switch: League restarts between two polls, the flag reads True both
times, and friends, header and loot keep the previous account's data. The
LCU connection generation moves on every new connection, so the pair
(connected, generation) changes whenever the session does.
"""
from typing import Any, Optional, Tuple


def lcu_session_key(connected: bool, generation: Any) -> Tuple[bool, Optional[int]]:
    """Hashable key that changes on connect, disconnect and reconnect."""
    if not connected:
        return (False, None)
    return (True, generation if isinstance(generation, int) else None)
