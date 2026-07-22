"""
Draft Assistant Automation Handler for LeagueLoop.

Provides Arena synergy picking, teammate respect draft algorithm, and role enforcement.
"""

import time
import random
from utils.logger import Logger
from core.constants import PRIORITY_SWAP_COOLDOWN
from .champ_select import get_local_player

def perform_arena_synergy(engine, session):
    me = get_local_player(engine, session)
    if not me:
        return

    actions = session.get("actions", [])
    my_action = None
    for row in actions:
        for action in row:
            if action.get("actorCellId") == me.get("cellId") and not action.get("completed"):
                my_action = action
                break
        if my_action:
            break

    if not my_action:
        return

    banned_ids = []
    for b in session.get("bannedChampions", []):
        if isinstance(b, dict):
            banned_ids.append(b.get("championId", 0))
        else:
            banned_ids.append(b)

    action_type = my_action.get("type", "")
    if action_type == "ban":
        handle_arena_ban(engine, session, my_action, banned_ids)
    elif action_type == "pick":
        handle_arena_pick(engine, session, me, my_action, banned_ids)
    else:
        if my_action.get("isAllyAction", True) and not my_action.get("completed"):
            engine._log(f"Arena: Unknown action type '{action_type}'. Assuming pick.")
            handle_arena_pick(engine, session, me, my_action, banned_ids)

def handle_arena_ban(engine, session, action, banned_ids):
    arena_ban = engine.config.get("arena_ban", "")
    if not arena_ban:
        return
        
    ban_id = engine.assets.name_to_id.get(arena_ban.lower(), 0)
    if not ban_id or ban_id in banned_ids:
        return

    now = time.time()
    action_id = action.get("id", 0)
    current_hover = action.get("championId", 0)
    
    timer = session.get("timer", {})
    time_left_ms = timer.get("adjustedTimeLeftInPhase", 15000)
    instant_ban = engine.config.get("arena_instant_ban", False)
    
    if current_hover != ban_id and (now - getattr(engine, "_last_synergy_patch", 0) > 0.5):
        engine._log(f"Arena: Hovering Ban {arena_ban}")
        engine.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": ban_id})
        engine._last_synergy_patch = now
        engine._synergy_patch_time = now
        
    elif current_hover == ban_id:
        time_since_patch = now - getattr(engine, "_synergy_patch_time", 0)
        if time_since_patch > 0.5 and (instant_ban or time_left_ms <= 2000) and (now - getattr(engine, "_last_synergy_patch", 0) > 0.5):
            log_msg = "(Instant)" if instant_ban else "(<2s left)"
            engine._log(f"Arena: Locking Ban {arena_ban} {log_msg}")
            res = engine.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": ban_id, "completed": True})
            if res and res.status_code not in (200, 204):
                Logger.error("Auto", f"Arena ban lock FAILED: {res.status_code} {res.text[:200]}")
            engine._last_synergy_patch = now

def handle_arena_pick(engine, session, me, action, banned_ids):
    action_id = action.get("id", 0)
    current_hover = action.get("championId", 0)
    now = time.time()
    
    my_team = session.get("myTeam", [])
    teammate = next((p for p in my_team if p.get("cellId") != me.get("cellId")), None)
    
    target_id = 0
    if teammate:
        teammate_champ_id = teammate.get("championId", 0)
        teammate_intent = teammate.get("championPickIntent", 0)
        target_id = teammate_champ_id if teammate_champ_id != 0 else teammate_intent
    
    pairs = engine.config.get("arena_pairs", [])
    mapped_me_list = []
    
    if target_id != 0:
        teammate_champ_name = engine.assets.get_champ_name(target_id)
        if teammate_champ_name:
            teammate_name_lower = teammate_champ_name.lower()
            for pair in pairs:
                if pair.get("enabled", True) and pair.get("teammate", "").lower() == teammate_name_lower:
                    val = pair.get("me", [])
                    mapped_me_list = val if isinstance(val, list) else [val]
                    break

    if not mapped_me_list:
        fallback = engine.config.get("arena_fallback_pick", "")
        if not fallback:
            fallback = engine.config.get("auto_pick", "")
            
        if fallback:
            mapped_me_list = [fallback]
            
    mapped_my_id, mapped_me_champ = 0, ""
    
    if mapped_me_list:
        for champ_name in mapped_me_list:
            if champ_name.lower() in ("bravery", "random"):
                if getattr(engine, "_bravery_pick_id", 0) in banned_ids or getattr(engine, "_bravery_pick_id", 0) == target_id:
                    engine._bravery_pick_id = 0
                if not getattr(engine, "_bravery_pick_id", 0):
                    req = engine.lcu.request("GET", "/lol-champ-select/v1/pickable-champion-ids", silent=True)
                    if req and req.status_code == 200:
                        pickable = req.json()
                        valid = [cid for cid in pickable if cid not in banned_ids and cid != target_id]
                        if valid:
                            engine._bravery_pick_id = random.choice(valid)
                if getattr(engine, "_bravery_pick_id", 0):
                    mapped_my_id = engine._bravery_pick_id
                    mapped_me_champ = engine.assets.get_champ_name(mapped_my_id) or "Random"
                    break
            else:
                cid = engine.assets.name_to_id.get(champ_name.lower())
                if cid and cid not in banned_ids and cid != target_id:
                    mapped_my_id = cid
                    mapped_me_champ = champ_name
                    break
                
    if mapped_my_id == 0:
        legacy_fallback = engine.config.get("auto_pick", "")
        if legacy_fallback:
            cid = engine.assets.name_to_id.get(legacy_fallback.lower())
            if cid and cid not in banned_ids and cid != target_id:
                mapped_my_id = cid
                mapped_me_champ = legacy_fallback
            
    timer = session.get("timer", {})
    time_left_ms = timer.get("adjustedTimeLeftInPhase", 15000)
    
    teammate_locked = False
    if teammate:
        actions = session.get("actions", [])
        for row in actions:
            for act in row:
                if act.get("actorCellId") == teammate.get("cellId") and act.get("type") == "pick":
                    if act.get("completed", False):
                        teammate_locked = True
                    break
            if teammate_locked:
                break
                
    if not teammate_locked and target_id != 0 and teammate and teammate.get("championId", 0) != 0:
        teammate_locked = True

    if mapped_my_id != 0 and current_hover != mapped_my_id:
        if now - getattr(engine, "_last_synergy_patch", 0) > 0.5:
            engine._log(f"Arena: Selecting {mapped_me_champ}...")
            engine.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": mapped_my_id})
            engine._last_synergy_patch = now
            engine._synergy_patch_time = now
    else:
        if engine.config.get("arena_auto_lock", False):
            lock_target = mapped_my_id if mapped_my_id != 0 else current_hover
            
            if lock_target != 0 and current_hover == lock_target:
                time_since_patch = now - getattr(engine, "_synergy_patch_time", 0)
                if time_since_patch > 0.5 and (time_left_ms <= 2000 or teammate_locked) and (now - getattr(engine, "_last_synergy_patch", 0) > 0.5):
                    champ_str = mapped_me_champ if mapped_my_id != 0 else engine.assets.get_champ_name(current_hover)
                    log_msg = "(Teammate Locked)" if teammate_locked else "(<2s left)"
                    engine._log(f"Arena: Locking Pick {champ_str} {log_msg}")
                    engine.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": lock_target, "completed": True})
                    engine._last_synergy_patch = now

def perform_draft_assistant(engine, session):
    me = get_local_player(engine, session)
    if not me:
        return

    assigned = me.get("assignedPosition", "")
    if not assigned:
        return
        
    assigned = assigned.upper()
    
    actions = session.get("actions", [])
    my_action = None
    for row in actions:
        for action in row:
            if action.get("actorCellId") == me.get("cellId") and action.get("isInProgress"):
                my_action = action
                break
        if my_action:
            break

    if not my_action:
        return

    action_type = my_action.get("type", "")
    action_id = my_action.get("id", 0)
    
    my_team = session.get("myTeam", [])
    banned_champ_ids = []
    for b in session.get("bannedChampions", []):
        if isinstance(b, dict): banned_champ_ids.append(b.get("championId", 0))
        else: banned_champ_ids.append(b)

    now = time.time()

    if action_type == "ban":
        my_cell_id = me.get("cellId")
        teammate_hovers = {
            champ_id
            for p in my_team
            if p.get("cellId") != my_cell_id
            for champ_id in (p.get("championPickIntent", 0), p.get("championId", 0))
            if champ_id > 0
        }
        
        ban_candidates = []
        for i in range(1, 4):
            ban_str = engine.config.get(f"ban_{assigned}_{i}", "")
            if ban_str:
                ban_candidates.append(ban_str)
        
        if not ban_candidates:
            global_ban = engine.config.get("auto_ban", "")
            if isinstance(global_ban, str) and global_ban.strip():
                ban_candidates.append(global_ban.strip())
            for i in range(1, 4):
                ban_str = engine.config.get(f"auto_ban_{i}", "")
                if ban_str:
                    ban_candidates.append(ban_str)
        
        auto_lock_ban = engine.config.get("auto_lock_in", False) or engine.config.get("auto_ban", False)
        for ban_str in ban_candidates:
            ban_id = engine.assets.name_to_id.get(ban_str.lower(), 0)
            if not ban_id: continue
            
            if ban_id in banned_champ_ids: continue
            if ban_id in teammate_hovers:
                engine._log(f"Draft: Skipping ban {ban_str} because a teammate is hovering it.")
                continue
            
            if my_action.get("championId") != ban_id and (now - getattr(engine, "_last_draft_action_time", 0) > 0.5):
                engine._log(f"Draft: Hovering Ban {ban_str}")
                engine.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": ban_id})
                engine._last_draft_action_time = now
            elif my_action.get("championId") == ban_id and auto_lock_ban:
                if now - getattr(engine, "_last_draft_action_time", 0) > 0.5:
                    engine._log(f"Draft: Locking Ban {ban_str}")
                    engine.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": ban_id, "completed": True})
                    engine._last_draft_action_time = now
            break

    elif action_type == "pick":
        from itertools import chain
        enemy_team = session.get("theirTeam", [])
        picked_ids = {cid for p in chain(my_team, enemy_team) if (cid := p.get("championId", 0)) > 0}
        
        my_cell_id = me.get("cellId")
        teammate_hovers = {
            champ_id
            for p in my_team
            if p.get("cellId") != my_cell_id
            for champ_id in (p.get("championPickIntent", 0), p.get("championId", 0))
            if champ_id > 0
        }
                
        pick_candidates = []
        for i in range(1, 4):
            pick_str = engine.config.get(f"pick_{assigned}_{i}", "")
            if pick_str:
                pick_candidates.append(pick_str)
                
        if not pick_candidates:
            global_pick = engine.config.get("auto_pick", "")
            if isinstance(global_pick, str) and global_pick.strip():
                pick_candidates.append(global_pick.strip())
            priority_list = engine.config.get("priority_picker", {}).get("list", [])
            if priority_list:
                pick_candidates.extend(priority_list)

        auto_lock_pick = (
            engine.config.get("auto_lock_in", False)
            or engine.config.get("auto_pick", False) is True
            or engine.config.get("auto_lockin", False)
        )

        for pick_str in pick_candidates:
            if not isinstance(pick_str, str) or not pick_str.strip(): continue
            pick_id = engine.assets.name_to_id.get(pick_str.lower(), 0)
            if not pick_id: continue
            
            if pick_id in banned_champ_ids or pick_id in picked_ids or pick_id in teammate_hovers:
                if pick_id in teammate_hovers:
                    engine._log(f"Draft: Skipping pick {pick_str} because a teammate is hovering it.")
                continue
            
            if my_action.get("championId") != pick_id and (now - getattr(engine, "_last_draft_action_time", 0) > 0.5):
                engine._log(f"Draft: Hovering Pick {pick_str}")
                engine.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": pick_id})
                engine._last_draft_action_time = now
            elif my_action.get("championId") == pick_id and auto_lock_pick:
                if now - getattr(engine, "_last_draft_action_time", 0) > 0.5:
                    engine._log(f"Draft: Locking Pick {pick_str}")
                    engine.lcu.request("PATCH", f"/lol-champ-select/v1/session/actions/{action_id}", data={"championId": pick_id, "completed": True})
                    engine._last_draft_action_time = now
            break

def perform_priority_sniper(engine, session, priority_list):
    if not priority_list: return
    bench = session.get("benchChampions", [])
    if not bench: return

    me = get_local_player(engine, session)
    my_champ_id = me.get("championId", 0) if me else 0
    my_champ_name = engine.assets.get_champ_name(my_champ_id) if my_champ_id else ""
    
    bench_map = {}
    for champ in bench:
        cid = champ.get("championId")
        cname = engine.assets.get_champ_name(cid)
        if cname:
            bench_map[cname] = cid

    my_priority_idx = 9999
    try:
        my_priority_idx = priority_list.index(my_champ_name)
    except ValueError:
        pass

    best_bench_champ = None
    best_bench_id = 0
    best_bench_idx = 9999

    for i, target_name in enumerate(priority_list):
        if i >= my_priority_idx:
            break

        if target_name in bench_map:
            best_bench_champ = target_name
            best_bench_id = bench_map[target_name]
            best_bench_idx = i
            break

    if best_bench_id != 0:
        now = time.time()

        if now - getattr(engine, "_last_priority_swap", 0) < PRIORITY_SWAP_COOLDOWN: return
        
        engine._log(f"Sniper: Found {best_bench_champ}! Swapping...")
        engine.lcu.request("POST", f"/lol-champ-select/v1/session/bench/swap/{best_bench_id}")
        engine._last_priority_swap = now
        engine._skin_equipped = False
