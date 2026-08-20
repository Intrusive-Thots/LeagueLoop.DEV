"""
Loot open engine (LCU).

Opens chests / capsules / orbs / mystery containers via:
  GET  /lol-loot/v1/player-loot
  GET  /lol-loot/v1/recipes/initial-item/{lootId}
  POST /lol-loot/v1/recipes/{recipeName}/craft[?repeat=N]

Only OPEN recipes are used — never disenchant, reroll, or event-shop forge.
Originally developed as standalone LootOpener; integrated for LeagueLoop.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from utils.logger import Logger

LogFn = Callable[[str], None]

_OPENABLE_ID_HINTS = re.compile(
    r"(CHEST_|CAPSULE|ORB|EGG|LOOT_MATERIAL_KEY|"
    r"MYSTERY|MATERIAL_key|MATERIAL_key_fragment|"
    r"HEXTECH|MASTERWORK|GLORIOUS|HONOR|EVENT)",
    re.IGNORECASE,
)

_SKIP_TYPES = {
    "CHAMPION",
    "CHAMPION_RENTAL",
    "SKIN",
    "SKIN_RENTAL",
    "WARDSKIN",
    "WARDSKIN_RENTAL",
    "SUMMONERICON",
    "EMOTE",
    "STATSTONE",
    "STATSTONE_SHARD",
    "COMPANION",
    "TFT_COMPANION",
    "CURRENCY",
}

_KEY_FRAGMENT_IDS = re.compile(r"key[_]?fragment", re.IGNORECASE)
_KEY_IDS = re.compile(r"(^|_)key($|_|s$)", re.IGNORECASE)


@dataclass
class LootItem:
    loot_id: str
    name: str
    count: int
    type: str
    display_categories: str
    localized_description: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, d: Dict[str, Any]) -> "LootItem":
        return cls(
            loot_id=str(d.get("lootId") or d.get("lootName") or ""),
            name=str(
                d.get("localizedName")
                or d.get("itemDesc")
                or d.get("lootName")
                or d.get("lootId")
                or "?"
            ),
            count=int(d.get("count") or 0),
            type=str(d.get("type") or ""),
            display_categories=str(d.get("displayCategories") or ""),
            localized_description=str(d.get("localizedDescription") or ""),
            raw=d,
        )


@dataclass
class OpenPlan:
    loot_id: str
    item_name: str
    recipe_name: str
    slots_payload: List[str]
    times: int
    needs_key: bool = False
    recipe_description: str = ""


@dataclass
class ClaimResult:
    claimed: int = 0
    sources: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class OpenResult:
    opened: int = 0
    failed: int = 0
    skipped: int = 0
    keys_crafted: int = 0
    rewards_claimed: int = 0
    details: List[str] = field(default_factory=list)


def _by_id(items: List[LootItem]) -> Dict[str, LootItem]:
    return {i.loot_id: i for i in items if i.loot_id}


def is_likely_openable(item: LootItem) -> bool:
    """Heuristic filter before hitting the recipes endpoint."""
    if item.count <= 0 or not item.loot_id:
        return False
    if item.type.upper() in _SKIP_TYPES:
        return False
    if _KEY_IDS.search(item.loot_id) and not _KEY_FRAGMENT_IDS.search(item.loot_id):
        if "fragment" not in item.loot_id.lower():
            if "chest" not in item.loot_id.lower() or item.loot_id.lower().endswith("_key"):
                if re.search(r"(^|_)(key|keys)$", item.loot_id, re.I) or re.search(
                    r"MATERIAL_key$", item.loot_id, re.I
                ):
                    return False

    cats = item.display_categories.upper()
    if "CHEST" in cats:
        return True
    if item.type.upper() == "CHEST":
        return True
    if _OPENABLE_ID_HINTS.search(item.loot_id):
        if _KEY_FRAGMENT_IDS.search(item.loot_id):
            return False
        if re.search(r"(MATERIAL_key|CHEST_key)$", item.loot_id, re.I):
            return False
        return True
    return False


class LootService:
    """
    Bulk-open LCU loot using the existing LCUClient.

    Expects `lcu` to expose:
      - is_connected: bool
      - request(method, endpoint, data=None, silent=False) -> Response | None
    """

    def __init__(self, lcu: Any, log: Optional[LogFn] = None) -> None:
        self.lcu = lcu
        self._log = log or (lambda m: Logger.info("Loot", m))
        self._recipe_cache: Dict[str, List[Dict[str, Any]]] = {}

    def log(self, msg: str) -> None:
        self._log(msg)

    # ── LCU helpers ────────────────────────────────────────────

    def _get_json(self, endpoint: str) -> Any:
        if not getattr(self.lcu, "is_connected", False):
            if hasattr(self.lcu, "connect"):
                self.lcu.connect(silent=True)
        r = self.lcu.request("GET", endpoint, silent=True)
        if r is None or r.status_code != 200:
            return None
        try:
            return r.json()
        except ValueError:
            return None

    def _post(
        self, endpoint: str, body: Any = None
    ) -> Tuple[bool, Any, str]:
        if not getattr(self.lcu, "is_connected", False):
            if hasattr(self.lcu, "connect"):
                self.lcu.connect(silent=True)
        r = self.lcu.request("POST", endpoint, data=body, silent=True)
        if r is None:
            return False, None, "no response / not connected"
        try:
            payload = r.json() if r.content else None
        except ValueError:
            payload = r.text
        if 200 <= r.status_code < 300:
            return True, payload, ""
        msg = ""
        if isinstance(payload, dict):
            msg = str(
                payload.get("message")
                or payload.get("errorCode")
                or payload
            )
        else:
            msg = str(payload) if payload else (r.reason or "error")
        return False, payload, f"HTTP {r.status_code}: {msg}"

    # ── inventory ──────────────────────────────────────────────

    def fetch_loot(self) -> List[LootItem]:
        data = self._get_json("/lol-loot/v1/player-loot")
        if not isinstance(data, list):
            self.log("Failed to fetch player loot.")
            return []
        items = [LootItem.from_api(x) for x in data if isinstance(x, dict)]
        items = [i for i in items if i.count > 0]
        items.sort(key=lambda i: (i.display_categories, i.name.lower()))
        return items

    def fetch_recipes(self, loot_id: str) -> List[Dict[str, Any]]:
        if loot_id in self._recipe_cache:
            return self._recipe_cache[loot_id]
        data = self._get_json(f"/lol-loot/v1/recipes/initial-item/{loot_id}")
        recipes = data if isinstance(data, list) else []
        self._recipe_cache[loot_id] = recipes
        return recipes

    def invalidate_recipe_cache(self) -> None:
        self._recipe_cache.clear()

    # ── planning ───────────────────────────────────────────────

    def _open_recipes_for(self, loot_id: str) -> List[Dict[str, Any]]:
        out = []
        for r in self.fetch_recipes(loot_id):
            name = str(r.get("recipeName") or "")
            rtype = str(r.get("type") or "").upper()
            if rtype == "OPEN" or name.upper().endswith("_OPEN"):
                out.append(r)
        return out

    def _slot_loot_ids(self, recipe: Dict[str, Any], primary_id: str) -> List[str]:
        payload: List[str] = []
        slots = recipe.get("slots") or []
        if not slots:
            return [primary_id]
        for slot in sorted(slots, key=lambda s: int(s.get("slotNumber") or 0)):
            ids = slot.get("lootIds") or []
            qty = int(slot.get("quantity") or 1)
            if not ids:
                continue
            chosen = primary_id if primary_id in ids else ids[0]
            for _ in range(max(1, qty)):
                payload.append(chosen)
        return payload or [primary_id]

    def _recipe_needs_key(self, recipe: Dict[str, Any], primary_id: str) -> bool:
        for slot in recipe.get("slots") or []:
            ids = [str(x) for x in (slot.get("lootIds") or [])]
            if any(
                _KEY_IDS.search(i) and not _KEY_FRAGMENT_IDS.search(i) for i in ids
            ):
                if primary_id not in ids:
                    return True
        return False

    def _max_craftable(
        self,
        recipe: Dict[str, Any],
        inventory: Dict[str, LootItem],
        primary_id: str,
        requested: int,
    ) -> int:
        slots = recipe.get("slots") or []
        if not slots:
            inv = inventory.get(primary_id)
            return min(requested, inv.count if inv else 0)

        limits: List[int] = []
        for slot in slots:
            ids = [str(x) for x in (slot.get("lootIds") or [])]
            qty = max(1, int(slot.get("quantity") or 1))
            if not ids:
                continue
            available = sum(
                inventory[lid].count for lid in ids if lid in inventory
            )
            limits.append(available // qty)
        if not limits:
            return 0
        return min(requested, min(limits))

    def plan_opens(
        self,
        items: Optional[List[LootItem]] = None,
        only_ids: Optional[Set[str]] = None,
    ) -> List[OpenPlan]:
        items = items if items is not None else self.fetch_loot()
        inventory = _by_id(items)
        plans: List[OpenPlan] = []

        candidates = [i for i in items if is_likely_openable(i)]
        if only_ids is not None:
            candidates = [i for i in candidates if i.loot_id in only_ids]

        for item in candidates:
            recipes = self._open_recipes_for(item.loot_id)
            if not recipes:
                continue
            recipes = sorted(recipes, key=lambda r: len(r.get("slots") or []))
            recipe = recipes[0]
            payload = self._slot_loot_ids(recipe, item.loot_id)
            times = self._max_craftable(recipe, inventory, item.loot_id, item.count)
            plans.append(
                OpenPlan(
                    loot_id=item.loot_id,
                    item_name=item.name,
                    recipe_name=str(recipe.get("recipeName") or ""),
                    slots_payload=payload,
                    times=times,
                    needs_key=self._recipe_needs_key(recipe, item.loot_id),
                    recipe_description=str(
                        recipe.get("description")
                        or recipe.get("contextMenuText")
                        or ""
                    ),
                )
            )
        return plans

    # ── key fragments ──────────────────────────────────────────

    def craft_keys_from_fragments(self) -> int:
        items = self.fetch_loot()
        crafted_total = 0
        for item in items:
            if not _KEY_FRAGMENT_IDS.search(item.loot_id):
                continue
            recipes = self.fetch_recipes(item.loot_id)
            forge = None
            for r in recipes:
                name = str(r.get("recipeName") or "").upper()
                rtype = str(r.get("type") or "").upper()
                if rtype in ("FORGE", "CRAFT") or "FORGE" in name or name.endswith("_KEY"):
                    outs = r.get("outputs") or []
                    out_names = " ".join(str(o.get("lootName") or "") for o in outs)
                    if _KEY_IDS.search(out_names) or "KEY" in name:
                        forge = r
                        break
                    if forge is None:
                        forge = r
            if not forge:
                for r in recipes:
                    if str(r.get("type") or "").upper() not in ("DISENCHANT",):
                        forge = r
                        break
            if not forge:
                self.log(f"No forge recipe for {item.name} ({item.loot_id})")
                continue

            inv = _by_id(self.fetch_loot())
            times = self._max_craftable(forge, inv, item.loot_id, item.count)
            if times <= 0:
                continue
            recipe_name = str(forge.get("recipeName") or "")
            payload = self._slot_loot_ids(forge, item.loot_id)
            ok, n = self._craft(recipe_name, payload, times)
            if ok:
                crafted_total += n
                self.log(f"Crafted {n} key(s) from {item.name}")
            else:
                self.log(f"Failed crafting keys from {item.name}")
        return crafted_total

    # ── reward claiming (passes, missions, milestones) ─────────

    def claim_battle_pass_rewards(self) -> ClaimResult:
        """Claim pending event pass, battle pass, and TFT pass milestone rewards."""
        res = ClaimResult()
        pass_endpoints = [
            "/lol-battle-pass/v1/rewards/claim",
            "/lol-battle-pass/v1/claim-all",
            "/lol-event-shop/v1/rewards/claim",
            "/lol-event-shop/v1/claim-all",
            "/lol-tft/v1/battlepass/claim",
            "/lol-tft-pass/v1/claim-all",
        ]
        for ep in pass_endpoints:
            ok, payload, err = self._post(ep, body={})
            if ok:
                cnt = 1
                if isinstance(payload, dict):
                    cnt = len(payload.get("rewards") or payload.get("claimedRewards") or [1])
                elif isinstance(payload, list):
                    cnt = max(1, len(payload))
                res.claimed += cnt
                res.sources.append(f"Pass ({ep})")
                res.details.append(f"Claimed pass rewards via {ep}")
                self.log(f"Successfully claimed {cnt} event/battle pass reward(s)")
            elif "not found" not in err.lower() and "404" not in err:
                res.errors.append(f"{ep}: {err}")

        return res

    def claim_mission_rewards(self) -> ClaimResult:
        """Claim all completed but unclaimed missions and quests."""
        res = ClaimResult()
        missions = self._get_json("/lol-missions/v1/missions")
        if isinstance(missions, list):
            for m in missions:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id") or m.get("missionId")
                status = str(m.get("status") or "").upper()
                reward_status = str(m.get("rewardStatus") or "").upper()
                is_claimable = bool(
                    m.get("isClaimable")
                    or reward_status in ("UNCLAIMED", "AVAILABLE")
                    or status in ("COMPLETED_UNCLAIMED", "COMPLETED")
                )
                if mid and is_claimable:
                    title = m.get("title") or m.get("name") or str(mid)
                    ok, _payload, _err = self._post(f"/lol-missions/v1/missions/{mid}/claim", body={})
                    if ok:
                        res.claimed += 1
                        res.sources.append(f"Mission: {title}")
                        res.details.append(f"Claimed mission '{title}'")
                        self.log(f"Claimed mission: {title}")

        # Batch fallback
        ok, _payload, _ = self._post("/lol-missions/v1/player/claim", body={})
        if ok and not res.claimed:
            res.claimed += 1
            res.sources.append("Missions Player Claim")
            res.details.append("Claimed pending player missions")

        return res

    def claim_loot_milestones(self) -> ClaimResult:
        """Claim open milestone track rewards (e.g. Masterwork chests, Showcase capsules)."""
        res = ClaimResult()
        milestone_data = self._get_json("/lol-loot/v1/milestones")
        if isinstance(milestone_data, list):
            for track in milestone_data:
                if not isinstance(track, dict):
                    continue
                milestones = track.get("milestones") or []
                for ms in milestones:
                    if not isinstance(ms, dict):
                        continue
                    ms_id = ms.get("id") or ms.get("milestoneId")
                    status = str(ms.get("status") or "").upper()
                    if ms_id and status in ("COMPLETED", "UNCLAIMED", "READY"):
                        ok, _, _ = self._post(f"/lol-loot/v1/milestones/{ms_id}/claim", body={})
                        if ok:
                            res.claimed += 1
                            res.sources.append(f"Milestone {ms_id}")
                            res.details.append(f"Claimed loot milestone #{ms_id}")
                            self.log(f"Claimed loot milestone: {ms_id}")

        # Batch fallback
        ok, _, _ = self._post("/lol-loot/v1/milestones/claim-all", body={})
        if ok:
            res.sources.append("Loot Milestones Claim-All")

        return res

    def claim_mastery_and_grants(self) -> ClaimResult:
        """Claim champion mastery milestone and reward grant notifications."""
        res = ClaimResult()
        ok, _, _ = self._post("/lol-champion-mastery/v1/milestones/claim", body={})
        if ok:
            res.claimed += 1
            res.sources.append("Champion Mastery Milestones")
            res.details.append("Claimed champion mastery milestones")
            self.log("Claimed champion mastery milestones")

        ok, _, _ = self._post("/lol-rewards/v1/grants/claim", body={})
        if ok:
            res.claimed += 1
            res.sources.append("Reward Grants")
            res.details.append("Claimed reward grants")

        return res

    def claim_all_rewards(self) -> ClaimResult:
        """
        Execute full claim pipeline across:
        1. Battle Pass & Event Pass milestone tracks (e.g. Pass level rewards)
        2. Completed Missions & Quests
        3. Loot Milestones (Masterwork / Showcase tracks)
        4. Champion Mastery Milestones & Reward Grants
        """
        self.log("Claiming all unclaimed event pass, mission, and milestone rewards…")
        total = ClaimResult()

        for step_fn in (
            self.claim_battle_pass_rewards,
            self.claim_mission_rewards,
            self.claim_loot_milestones,
            self.claim_mastery_and_grants,
        ):
            try:
                step_res = step_fn()
                total.claimed += step_res.claimed
                total.sources.extend(step_res.sources)
                total.details.extend(step_res.details)
                total.errors.extend(step_res.errors)
            except Exception as exc:
                self.log(f"Claim step error: {exc}")
                total.errors.append(str(exc))

        if total.claimed > 0:
            self.log(f"Claim step completed: {total.claimed} reward(s) claimed into inventory.")
        else:
            self.log("Claim step completed: No pending unclaimed rewards found.")

        return total

    # ── craft execution ────────────────────────────────────────

    def _craft(
        self,
        recipe_name: str,
        loot_ids: List[str],
        times: int,
        pause_s: float = 0.12,
    ) -> Tuple[bool, int]:
        if times <= 0 or not recipe_name:
            return False, 0

        base = f"/lol-loot/v1/recipes/{recipe_name}/craft"
        succeeded = 0

        if times > 1:
            ok, _payload, err = self._post(f"{base}?repeat={times}", body=loot_ids)
            if ok:
                return True, times
            self.log(f"Bulk craft failed ({err}); falling back to singles…")

        for i in range(times):
            ok, _payload, err = self._post(base, body=loot_ids)
            if ok:
                succeeded += 1
            else:
                self.log(f"Craft failed for {recipe_name} ({i + 1}/{times}): {err}")
                if "not enough" in err.lower() or "insufficient" in err.lower():
                    break
            if pause_s:
                time.sleep(pause_s)

        return succeeded > 0, succeeded

    def open_all(
        self,
        craft_keys_first: bool = True,
        claim_rewards_first: bool = True,
        max_passes: int = 4,
        only_ids: Optional[Set[str]] = None,
        stop_flag: Optional[Callable[[], bool]] = None,
    ) -> OpenResult:
        result = OpenResult()
        stop = stop_flag or (lambda: False)

        if claim_rewards_first:
            self.log("Claiming pending pass and mission rewards first…")
            claim_res = self.claim_all_rewards()
            result.rewards_claimed = claim_res.claimed
            if claim_res.claimed > 0:
                result.details.append(f"Rewards claimed: {claim_res.claimed}")
                time.sleep(0.3)  # Brief delay to allow inventory to sync

        if craft_keys_first:
            self.log("Forging key fragments → keys…")
            result.keys_crafted = self.craft_keys_from_fragments()
            if result.keys_crafted:
                result.details.append(f"Keys crafted: {result.keys_crafted}")

        for pass_no in range(1, max_passes + 1):
            if stop():
                self.log("Stopped by user.")
                break
            self.invalidate_recipe_cache()
            plans = self.plan_opens(only_ids=only_ids)
            actionable = [p for p in plans if p.times > 0]
            blocked = [p for p in plans if p.times == 0]

            for p in blocked:
                if p.needs_key:
                    msg = f"Skip {p.item_name}: needs a key (none available)."
                else:
                    msg = f"Skip {p.item_name}: missing ingredients."
                self.log(msg)
                result.skipped += 1
                result.details.append(msg)

            if not actionable:
                if pass_no == 1:
                    self.log("Nothing openable right now.")
                else:
                    self.log(f"Pass {pass_no}: no more openable loot.")
                break

            self.log(f"Pass {pass_no}: opening {len(actionable)} stack(s)…")
            opened_this_pass = 0
            for plan in actionable:
                if stop():
                    break
                self.log(
                    f"  Opening {plan.times}× {plan.item_name} [{plan.recipe_name}]"
                )
                _ok, n = self._craft(plan.recipe_name, plan.slots_payload, plan.times)
                if n:
                    result.opened += n
                    opened_this_pass += n
                    result.details.append(f"Opened {n}× {plan.item_name}")
                else:
                    result.failed += 1
                    result.details.append(f"Failed {plan.item_name}")
                time.sleep(0.15)

            if opened_this_pass == 0:
                break
            time.sleep(0.4)

        self.log(
            f"Done. Opened={result.opened} Failed={result.failed} "
            f"Skipped={result.skipped} Keys={result.keys_crafted}"
        )
        return result

    def summarize_openable(self) -> List[Dict[str, Any]]:
        items = self.fetch_loot()
        plans = {p.loot_id: p for p in self.plan_opens(items)}
        rows: List[Dict[str, Any]] = []
        for item in items:
            if not is_likely_openable(item) and item.loot_id not in plans:
                continue
            plan = plans.get(item.loot_id)
            rows.append(
                {
                    "loot_id": item.loot_id,
                    "name": item.name,
                    "count": item.count,
                    "type": item.type,
                    "category": item.display_categories,
                    "can_open": bool(plan and plan.times > 0),
                    "will_open": plan.times if plan else 0,
                    "needs_key": bool(plan.needs_key) if plan else False,
                    "recipe": plan.recipe_name if plan else "",
                    "recipe_desc": plan.recipe_description if plan else "",
                }
            )
        return rows
