import random
from utils.logger import Logger
from core.events import EventBus
from core.constants import QUEUE_ARENA, QUEUE_ARENA_3V6, QUEUE_DRAFT, QUEUE_RANKED_SOLO, QUEUE_RANKED_FLEX, QUEUE_CLASSIC

def get_local_player(engine, session):
    local_cell_id = session.get("localPlayerCellId")
    my_team = session.get("myTeam", [])
    return next((p for p in my_team if p["cellId"] == local_cell_id), None)

def equip_random_skin(engine, session):
    try:
        me = engine._get_local_player(session)
        if not me:
            return
        champ_id = me.get("championId", 0)
        if not champ_id:
            return

        skins_req = engine.lcu.request("GET", f"/lol-champ-select/v1/skin-carousel-skins", silent=True)
        if not skins_req or skins_req.status_code != 200:
            return

        skins = skins_req.json()
        owned_skins = [
            s for s in skins
            if s.get("ownership", {}).get("owned", False)
            and not s.get("isBase", False)
            and s.get("id", 0) != (champ_id * 1000)
            and not s.get("disabled", False)
        ]

        if not owned_skins:
            engine._skin_equipped = True  # No skins available — stop polling
            return

        chosen = random.choice(owned_skins)
        skin_id = chosen.get("id", 0)

        engine.lcu.request(
            "PATCH",
            f"/lol-champ-select/v1/session/my-selection",
            data={"selectedSkinId": skin_id}
        )
        skin_name = chosen.get("name", f"Skin #{skin_id}")
        engine._log(f"Equipped: {skin_name}")
        engine._skin_equipped = True

    except Exception as e:
        Logger.error("Auto", f"Skin equip error: {e}")

def auto_equip_runes(engine, session):
    if not engine.config.get("auto_runes_enabled", False):
        engine._runes_equipped = True
        return

    try:
        me = engine._get_local_player(session)
        if not me: return
        champ_id = me.get("championId", 0)
        if not champ_id: return

        assigned = me.get("assignedPosition", "")
        pos = assigned if assigned else ""
        req = engine.lcu.request("GET", f"/lol-perks/v1/recommended-pages/{champ_id}?position={pos}", silent=True)
        if not req or req.status_code != 200: return
        
        recs = req.json()
        if not recs: return

        best_page = recs[0]
        
        apply_res = engine.lcu.request("POST", f"/lol-perks/v1/recommended-pages/{champ_id}/apply", data={"pageId": best_page.get("id")}, silent=True)
        if apply_res and apply_res.status_code in [200, 204]:
            engine._runes_equipped = True
            engine._log("Auto-Equipped Recommended Runes!")
    except Exception as e:
        Logger.debug("Auto", f"Rune equip error: {e}")

def handle_champ_select(engine, phase, session):
    if engine.paused: return
    if phase != "ChampSelect":
        engine.setup_done = False
        engine._skin_equipped = False
        engine._runes_equipped = False
        engine._chat_warden_warned = False
        engine._bravery_pick_id = 0
        engine._last_champ_id = 0
        EventBus.emit("automation_lobby_stats", [], [], None)
        return
        
    if not session:
        EventBus.emit("automation_lobby_stats", [], [], None)
        return

    me = engine._get_local_player(session)
    my_champ_id = me.get("championId", 0) if me else 0
    if my_champ_id != 0 and my_champ_id != getattr(engine, "_last_champ_id", 0):
        engine._last_champ_id = my_champ_id
        engine._skin_equipped = False
        engine._runes_equipped = False

    engine._handle_auto_dodge(session)
    engine._handle_chat_warden(session)

    my_team = session.get("myTeam", [])
    bench = session.get("benchChampions", [])
    
    local_cell_id = session.get("localPlayerCellId")
    me_player = next((p for p in my_team if p.get("cellId") == local_cell_id), None)
    EventBus.emit("automation_lobby_stats", my_team, bench, me_player)

    has_bench = len(bench) > 0
    is_arena = engine.current_queue_id in {QUEUE_ARENA, QUEUE_ARENA_3V6}
    is_draft = engine.current_queue_id in {QUEUE_DRAFT, QUEUE_RANKED_SOLO, QUEUE_RANKED_FLEX, QUEUE_CLASSIC}

    if has_bench and not is_arena:
        priority_cfg = engine.config.get("priority_picker", {})
        if priority_cfg.get("enabled", False):
            engine._perform_priority_sniper(session, priority_cfg.get("list", []))
    elif is_arena:
        if engine.config.get("arena_synergy_enabled", True):
            engine._perform_arena_synergy(session)
    elif is_draft:
        engine._perform_draft_assistant(session)

    if not engine._skin_equipped:
        engine._equip_random_skin(session)

    if not engine._runes_equipped:
        engine._auto_equip_runes(session)
