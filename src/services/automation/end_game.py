"""
End of Game Automation Handler for LeagueLoop.

Manages post-match screen dismissal, auto-honoring, and returning to lobby.
"""

import random
from utils.logger import Logger

def handle_end_of_game(engine, phase):
    if not hasattr(engine, "_party_puuids"):
        engine._party_puuids = set()
    if not hasattr(engine, "_honored_puuids"):
        engine._honored_puuids = set()
    if not hasattr(engine, "_honor_attempts"):
        engine._honor_attempts = 0

    if phase not in ["PreEndOfGame", "EndOfGame"]:
        engine._honor_handled = False
        engine._honor_attempts = 0
        engine._honored_puuids = set()
        return

    auto_honor = engine.config.get("auto_honor_enabled", False)
    skip_stats = engine.config.get("skip_stats_enabled", True)

    if not auto_honor and not skip_stats:
        return

    if getattr(engine, "_honor_handled", False):
        return

    try:
        eog = engine.lcu.request("GET", "/lol-end-of-game/v1/eog-stats-block", silent=True)
        if not eog or eog.status_code != 200:
            return
        
        data = eog.json()
        game_id = data.get("gameId")
        
        my_puuid = data.get("localPlayer", {}).get("puuid")
        if not my_puuid:
            me_req = engine.lcu.request("GET", "/lol-chat/v1/me")
            if me_req and me_req.status_code == 200:
                my_puuid = me_req.json().get("puuid")

        teams = data.get("teams", [])
        teammates = []
        
        for team in teams:
            players = team.get("players", [])

            is_my_team = team.get("isPlayerTeam", False)
            if not is_my_team and my_puuid:
                for p in players:
                    if p.get("puuid") == my_puuid:
                        is_my_team = True
                        break

            if is_my_team:
                for p in players:
                    puuid = p.get("puuid", "")
                    if puuid and puuid != my_puuid:
                        teammates.append(p)
                break

        if not teammates:
            engine._honor_handled = True
            return

        if auto_honor:
            strategy = engine.config.get("honor_strategy", "random")
            honor_party_first = engine.config.get("honor_party_first", False)

            party_teammates = [p for p in teammates if p.get("puuid", "") in getattr(engine, "_party_puuids", set())]

            def kda(p):
                k = p.get("stats", {}).get("CHAMPIONS_KILLED", 0)
                a = p.get("stats", {}).get("ASSISTS", 0)
                d = max(p.get("stats", {}).get("NUM_DEATHS", 1), 1)
                return (k + a) / d

            def score(p):
                s = p.get("stats", {})
                return s.get("CHAMPIONS_KILLED", 0) + s.get("ASSISTS", 0)

            def sort_players(players_list):
                if strategy == "best_kda":
                    return sorted(players_list, key=kda, reverse=True)
                elif strategy == "mvp":
                    return sorted(players_list, key=score, reverse=True)
                else:
                    lst = list(players_list)
                    random.shuffle(lst)
                    return lst

            if honor_party_first and party_teammates:
                targets = sort_players(party_teammates)
            else:
                friend_teammates = []
                friends_res = engine.lcu.request("GET", "/lol-chat/v1/friends")
                if friends_res and friends_res.status_code == 200:
                    friend_puuids = {f.get("puuid", "") for f in friends_res.json()}
                    friend_teammates = [p for p in teammates if p.get("puuid", "") in friend_puuids]
                
                candidates = friend_teammates if friend_teammates else teammates
                if not candidates:
                    engine._honor_handled = True
                    return
                
                sorted_cand = sort_players(candidates)
                targets = [sorted_cand[0]]

            rate_limited = False
            completed_all = True

            for target in targets:
                puuid = target.get("puuid", "")
                if not puuid or puuid in getattr(engine, "_honored_puuids", set()):
                    continue

                summoner_id = target.get("summonerId", 0)
                honor_body = {
                    "gameId": game_id,
                    "honorCategory": "HEART",
                    "honorType": "HEART",
                    "summonerId": summoner_id,
                    "puuid": puuid
                }
                res = engine.lcu.request("POST", "/lol-honor-v2/v1/honor-player", honor_body)
                name = target.get("summonerName", "teammate")

                if res and res.status_code in [200, 204]:
                    engine._log(f"Honored {name} ({strategy})")
                    engine._honored_puuids.add(puuid)
                elif res and res.status_code == 409:
                    engine._log(f"Honor already submitted or invalid: {name}")
                    engine._honored_puuids.add(puuid)
                elif res and res.status_code == 429:
                    engine._log(f"Honor rate limited (429). Retrying next tick...")
                    rate_limited = True
                    completed_all = False
                    break
                else:
                    Logger.debug("Auto", f"Honor request returned {res.status_code if res else 'None'}. Full target: {name}")
                    engine._honor_attempts = getattr(engine, "_honor_attempts", 0) + 1
                    if getattr(engine, "_honor_attempts", 0) >= 3:
                        engine._log(f"Honor failed after 3 attempts. Giving up.")
                        engine._honor_attempts = 0
                        engine._honor_handled = True
                    else:
                        completed_all = False
                        break

            if completed_all or rate_limited:
                if not rate_limited:
                    engine._honor_handled = True
        else:
            engine._honor_handled = True

        if getattr(engine, "_honor_handled", False):
            if skip_stats:
                play_again = engine.lcu.request("POST", "/lol-lobby/v2/play-again", silent=True)
                if play_again and play_again.status_code in [200, 204]:
                    engine._log("Proceeded to Lobby (Skipped Stats)")

            if engine.config.get("aram_auto_add_played", False):
                try:
                    local_player = data.get("localPlayer", {})
                    played_champ_id = local_player.get("championId", 0)
                    if played_champ_id:
                        played_name = engine.assets.get_champ_name(played_champ_id)
                        if played_name and played_name != str(played_champ_id):
                            priority_cfg = engine.config.get("priority_picker", {})
                            plist = priority_cfg.get("list", [])
                            played_lower = played_name.lower()
                            already_in = any(p.lower() == played_lower for p in plist)
                            if not already_in:
                                plist.append(played_name)
                                priority_cfg["list"] = plist
                                engine.config.set("priority_picker", priority_cfg)
                                engine._log(f"ARAM List: Auto-added {played_name}")
                except Exception as e:
                    Logger.debug("Auto", f"Auto-add played champion error: {e}")
            
    except Exception as e:
        Logger.debug("Auto", f"End of game error: {e}")
