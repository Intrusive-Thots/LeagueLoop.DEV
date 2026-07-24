"""
Status API Routes Module for LeagueLoop local HTTP server.

Handles server and client health and status endpoint responses.
"""

import time
from services.api.registry import register_get
from services.settings_service import get_settings_service
from services.league_service import get_league_service
from services.queue_service import get_queue_service
from utils.logger import Logger

@register_get('/status')
def handle_status(handler):
    phase = "Unknown"
    power_state = False
    queue_mode = "None"
    summoner_info = None
    lobby_info = None
    
    league = get_league_service()
    settings = get_settings_service()
    queue_service = get_queue_service()
    app = handler.app_instance
    
    if league and league.is_connected:
        phase = league.get_phase()
        now = time.time()
        if not getattr(handler.server, '_summoner_cache', None) or (now - getattr(handler.server, '_summoner_cache_time', 0) > 15):
            try:
                s_res = league.request('GET', '/lol-summoner/v1/current-summoner', silent=True)
                if s_res and s_res.status_code == 200:
                    sdata = s_res.json()
                    
                    tier = "UNRANKED"
                    rank = ""
                    lp = 0
                    r_res = league.request('GET', '/lol-ranked/v1/current-ranked-stats', silent=True)
                    if r_res and r_res.status_code == 200:
                        rdata = r_res.json()
                        for q in rdata.get('queues', []):
                            if q.get('queueType') == 'RANKED_SOLO_5x5':
                                tier = q.get('tier', 'UNRANKED')
                                rank = q.get('division', '')
                                lp = q.get('leaguePoints', 0)
                                break
                    
                    handler.server._summoner_cache = {
                        "summoner_name": sdata.get("displayName") or f"{sdata.get('gameName')}#{sdata.get('tagLine')}",
                        "profile_icon_id": sdata.get("profileIconId", 1),
                        "level": sdata.get("summonerLevel", 1),
                        "puuid": sdata.get("puuid"),
                        "tier": tier,
                        "rank": rank,
                        "lp": lp
                    }
                    handler.server._summoner_cache_time = now
            except Exception as e:
                Logger.debug("API", f"Error updating summoner cache: {e}")
        
        summoner_info = getattr(handler.server, '_summoner_cache', None)
        
        try:
            lobby_res = league.request('GET', '/lol-lobby/v2/lobby', silent=True)
            if lobby_res and lobby_res.status_code == 200:
                lobby_data = lobby_res.json()
                members = []
                for m in lobby_data.get('members', []):
                    m_name = m.get('summonerName')
                    if not m_name and m.get('gameName'):
                        m_name = f"{m.get('gameName')}#{m.get('tagLine')}"
                    if not m_name and summoner_info and m.get('puuid') == summoner_info.get("puuid"):
                        m_name = summoner_info.get("summoner_name")
                    if not m_name:
                        m_name = "Summoner"
                    
                    members.append({
                        "summonerName": m_name,
                        "isLeader": m.get('isLeader', False),
                        "position1": m.get('firstPositionPreference', 'UNSELECTED'),
                        "position2": m.get('secondPositionPreference', 'UNSELECTED')
                    })
                lobby_info = {
                    "queueId": lobby_data.get('gameConfig', {}).get('queueId', 0),
                    "members": members
                }
        except Exception as e:
            Logger.debug("API", f"Error fetching lobby info: {e}")

    if app and hasattr(app, "automation") and app.automation:
        power_state = app.automation.running and not app.automation.paused
    
    queue_mode = settings.get("aram_mode", "ARAM") if settings else "ARAM"
    queue_timer = queue_service.get_queue_time() if queue_service else 0
    queue_estimated = queue_service.get_estimated_time() if queue_service else 120
    
    data = {
        "phase": phase,
        "automation_enabled": power_state,
        "queue_mode": queue_mode,
        "queue_timer": queue_timer,
        "queue_estimated": queue_estimated,
        "summoner_name": summoner_info.get("summoner_name", "") if summoner_info else "",
        "summoner": summoner_info,
        "lobby": lobby_info
    }
    handler.send_json(data)

@register_get('/health')
def handle_health(handler):
    handler.send_json({"status": "ok"})
