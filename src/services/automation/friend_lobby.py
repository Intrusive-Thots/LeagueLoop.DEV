import time
import json
from utils.logger import Logger

def check_friend_lobby(engine, phase):
    if phase in ("InProgress", "ChampSelect", "ReadyCheck"):
        return

    if not engine.config.get("auto_join_enabled", True):
        return

    friend_list = engine.config.get("auto_join_list", [])
    active_friends = [f for f in friend_list if f.get("enabled") and f.get("name", "").strip()]
    if not active_friends:
        return

    from core.state import State
    friends = State.friends

    if not friends or not isinstance(friends, list):
        res = engine.lcu.request("GET", "/lol-chat/v1/friends", silent=True)
        if res and res.status_code == 200:
            friends = res.json()
            State.friends = friends
        else:
            return

    friend_map = {}
    for f in friends:
        game_name = f.get("gameName", "") or f.get("name", "")
        game_tag = f.get("gameTag", "")
        combo_name = f"{game_name}#{game_tag}" if game_tag else game_name
        
        friend_map[game_name.lower()] = f
        if combo_name:
            friend_map[combo_name.lower()] = f

    for target_dict in active_friends:
        target_friend = target_dict.get("name", "").strip().lower()
        
        f = friend_map.get(target_friend)
        if not f:
            continue

        game_name = f.get("gameName", "")
        lol = f.get("lol", {})
        if lol.get("ptyType") == "open":
            pty_str = lol.get("pty", "")
            if pty_str:
                try:
                    pty_data = json.loads(pty_str)
                    party_id = pty_data.get("partyId")
                    if party_id:
                        my_res = engine.lcu.request("GET", "/lol-lobby/v2/lobby")
                        if my_res and my_res.status_code == 200:
                            my_lobby = my_res.json()
                            if my_lobby.get("partyId") == party_id:
                                return

                        if phase == "Matchmaking":
                            engine.lcu.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")
                            time.sleep(0.5)

                        join_res = engine.lcu.request("POST", f"/lol-lobby/v2/party/{party_id}/join")
                        if join_res and join_res.status_code in [200, 204]:
                            engine._log(f"Auto-joined {game_name}'s Party!")
                            break
                except Exception as e:
                    Logger.debug("Auto", f"Failed parsing friend party: {e}")
