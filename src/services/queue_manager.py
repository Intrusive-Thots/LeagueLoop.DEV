"""
Queue Manager Service
─────────────────────
Dynamically discovers, categorizes, and maps available League of Legends lobby types
and queue IDs via LCU API (with static offline fallback).
"""

import threading
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import Logger

# Default baseline fallback mapping (Queue ID -> Display Name)
BASELINE_QUEUE_MAP: Dict[int, str] = {
    400: "Draft Pick",
    420: "Ranked Solo/Duo",
    440: "Ranked Flex",
    450: "ARAM",
    480: "Swiftplay",
    490: "Quickplay",
    900: "URF",
    1010: "ARURF",
    1020: "One For All",
    1090: "TFT Normal",
    1100: "TFT Ranked",
    1160: "TFT Double Up",
    1300: "Nexus Blitz",
    1400: "Ultimate Spellbook",
    1700: "Arena",
    1710: "Arena 3v6",
    1750: "Arena 3x6",
    2300: "Brawl",
    2400: "ARAM Mayhem",
}

# Reverse default mapping (Display Name -> Queue ID)
BASELINE_NAME_TO_ID: Dict[str, int] = {v: k for k, v in BASELINE_QUEUE_MAP.items()}
# Add extra alias mappings for convenience
BASELINE_NAME_TO_ID.update({
    "ARAM Mayhem": 2400,
    "Ranked Solo": 420,
    "Ranked Flex": 440,
    "Arena": 1700,
})

# Default baseline grouped categories for UI dropdowns
BASELINE_GROUPS: List[Tuple[str, List[str]]] = [
    ("Ranked", ["Ranked Solo/Duo", "Ranked Flex"]),
    ("Casual", ["Quickplay", "Draft Pick", "Swiftplay"]),
    ("ARAM", ["ARAM", "ARAM Mayhem"]),
    ("Arena", ["Arena", "Arena 3v6"]),
    ("Rotating", ["Brawl", "URF", "ARURF", "Nexus Blitz", "One For All", "Ultimate Spellbook"]),
    ("TFT", ["TFT Normal", "TFT Ranked"]),
]


class QueueManager:
    """Manages dynamic queue discovery, queue ID mapping, and categorized lobby types."""

    _instance: Optional["QueueManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._queue_id_to_name: Dict[int, str] = dict(BASELINE_QUEUE_MAP)
        self._name_to_queue_id: Dict[str, int] = dict(BASELINE_NAME_TO_ID)
        self._categorized_groups: List[Tuple[str, List[str]]] = list(BASELINE_GROUPS)
        self._last_updated: float = 0.0

    @classmethod
    def get_instance(cls) -> "QueueManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ─────────── Dynamic Update ───────────

    def update_available_lobby_types(self, lcu=None) -> List[Tuple[str, List[str]]]:
        """Dynamically fetch and update current available lobby types from LCU.
        
        Queries /lol-game-queues/v1/queues, filters for available queues,
        updates internal name-ID mappings, and rebuilds UI categories.
        Returns the updated categorized groups tuple list.
        """
        if not lcu or not getattr(lcu, "is_connected", False):
            return self.get_categorized_groups()

        try:
            res = lcu.request("GET", "/lol-game-queues/v1/queues", silent=True)
            if not res or res.status_code != 200:
                return self.get_categorized_groups()

            queues_data = res.json()
            if not isinstance(queues_data, list):
                return self.get_categorized_groups()

            available_queues: List[Dict[str, Any]] = []
            for q in queues_data:
                # Include available queues or non-custom queues
                avail = q.get("queueAvailability")
                if avail == "Available" and not q.get("isCustom", False):
                    available_queues.append(q)

            if not available_queues:
                return self.get_categorized_groups()

            # Temp storage for building new categories
            new_id_map: Dict[int, str] = dict(BASELINE_QUEUE_MAP)
            new_name_map: Dict[str, int] = dict(BASELINE_NAME_TO_ID)

            group_ranked: List[str] = []
            group_casual: List[str] = []
            group_aram: List[str] = []
            group_arena: List[str] = []
            group_rotating: List[str] = []
            group_tft: List[str] = []

            for q in available_queues:
                qid = int(q.get("id", 0))
                q_name = q.get("name") or q.get("description") or f"Queue {qid}"
                category = (q.get("category") or "").lower()
                game_mode = (q.get("gameMode") or "").lower()

                # Clean display name
                display_name = q_name.strip()

                new_id_map[qid] = display_name
                new_name_map[display_name] = qid
                new_name_map[display_name.lower()] = qid

                # Categorize into groups
                if "tft" in game_mode or "tft" in display_name.lower():
                    if display_name not in group_tft:
                        group_tft.append(display_name)
                elif "aram" in game_mode or "aram" in display_name.lower() or "howling" in display_name.lower():
                    if display_name not in group_aram:
                        group_aram.append(display_name)
                elif "cherry" in game_mode or "arena" in display_name.lower():
                    if display_name not in group_arena:
                        group_arena.append(display_name)
                elif q.get("isRanked") or "ranked" in display_name.lower():
                    if display_name not in group_ranked:
                        group_ranked.append(display_name)
                elif category == "pvp" and game_mode == "classic":
                    if display_name not in group_casual:
                        group_casual.append(display_name)
                else:
                    if display_name not in group_rotating and display_name not in group_casual:
                        group_rotating.append(display_name)

            # Reconstruct categorized groups list
            new_groups: List[Tuple[str, List[str]]] = []
            if group_ranked:
                new_groups.append(("Ranked", group_ranked))
            if group_casual:
                new_groups.append(("Casual", group_casual))
            if group_aram:
                new_groups.append(("ARAM", group_aram))
            if group_arena:
                new_groups.append(("Arena", group_arena))
            if group_rotating:
                new_groups.append(("Rotating / Special", group_rotating))
            if group_tft:
                new_groups.append(("TFT", group_tft))

            with self._lock:
                self._queue_id_to_name = new_id_map
                self._name_to_queue_id = new_name_map
                if new_groups:
                    self._categorized_groups = new_groups

            Logger.info("QueueManager", f"Dynamically updated {len(available_queues)} lobby types from LCU.")

        except Exception as e:
            Logger.debug("QueueManager", f"Failed to dynamically update queues: {e}")

        return self.get_categorized_groups()

    # ─────────── Resolvers ───────────

    def get_categorized_groups(self) -> List[Tuple[str, List[str]]]:
        """Return the current categorized groups for UI menus."""
        with self._lock:
            return list(self._categorized_groups)

    def resolve_queue_id(self, mode: str, lcu=None) -> int:
        """Resolve a mode string (e.g. 'ARAM', 'Ranked Solo/Duo') to a numeric Queue ID."""
        if not mode:
            return 450  # Default to ARAM

        with self._lock:
            if mode in self._name_to_queue_id:
                return self._name_to_queue_id[mode]
            mode_lower = mode.lower()
            if mode_lower in self._name_to_queue_id:
                return self._name_to_queue_id[mode_lower]

        # Fuzzy match against dynamic map
        with self._lock:
            for name, qid in self._name_to_queue_id.items():
                if isinstance(name, str) and mode_lower in name.lower():
                    return qid

        # Fallback to static mapping
        return BASELINE_NAME_TO_ID.get(mode, 450)

    def resolve_mode_name(self, queue_id: int, lcu=None) -> str:
        """Resolve a numeric Queue ID (e.g. 450) to a display name string (e.g. 'ARAM')."""
        try:
            qid = int(queue_id)
        except (TypeError, ValueError):
            return "ARAM"

        with self._lock:
            if qid in self._queue_id_to_name:
                return self._queue_id_to_name[qid]

        return BASELINE_QUEUE_MAP.get(qid, f"Queue {qid}")


# Global convenience helper functions
_mgr = QueueManager.get_instance()

def update_available_lobby_types(lcu=None) -> List[Tuple[str, List[str]]]:
    """Dynamically update available lobby types from LCU."""
    return _mgr.update_available_lobby_types(lcu)

def get_categorized_lobby_types() -> List[Tuple[str, List[str]]]:
    """Get current categorized lobby types."""
    return _mgr.get_categorized_groups()

def resolve_queue_id(mode: str, lcu=None) -> int:
    """Resolve mode string to queue ID."""
    return _mgr.resolve_queue_id(mode, lcu)

def resolve_mode_name(queue_id: int, lcu=None) -> str:
    """Resolve queue ID to mode string."""
    return _mgr.resolve_mode_name(queue_id, lcu)
