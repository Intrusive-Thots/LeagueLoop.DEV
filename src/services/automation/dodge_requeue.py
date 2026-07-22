import sys
import time
import subprocess
from utils.logger import Logger

def handle_dodge_requeue(engine, phase):
    if phase == "Lobby" and engine.last_phase in ("ChampSelect", "ReadyCheck"):
        now = time.time()
        if engine._cached_search_state and (now - engine._last_search_state_time < 3.0):
            state = engine._cached_search_state
        else:
            search_state = engine.lcu.request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state", silent=True)
            state = search_state.json() if search_state and search_state.status_code == 200 else None
            engine._cached_search_state = state
            engine._last_search_state_time = now
        
        if not state or state.get("searchState") != "Searching":
            engine.lcu.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
            engine._log("Dodge detected. Restarting Matchmaking...")
            engine._last_search_state_time = 0

def handle_auto_dodge(engine, session):
    if not engine._blacklist: return
    
    my_cell = session.get("localPlayerCellId")
    my_team = session.get("myTeam", [])
    
    for p in my_team:
        if p.get("cellId") == my_cell: continue
        
        su_id = p.get("summonerId", 0)
        if not su_id: continue
        
        req = engine.lcu.request("GET", f"/lol-summoner/v1/summoners/{su_id}", silent=True)
        if req and req.status_code == 200:
            summoner_data = req.json()
            name = summoner_data.get("gameName", "").lower()
            tag = summoner_data.get("tagLine", "").lower()
            full_name = f"{name}#{tag}"
            
            if name in engine._blacklist or full_name in engine._blacklist:
                engine._log(f"BLACKLIST MATCH: {full_name}. Dodging immediately.")
                try:
                    kwargs = {}
                    if sys.platform == "win32":
                        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    subprocess.run(["taskkill", "/IM", "LeagueClient.exe", "/F"], **kwargs)
                except Exception as e:
                    Logger.error("Automation", f"Failed to terminate LeagueClient process: {e}")
                return

