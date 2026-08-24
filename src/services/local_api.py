import json
import time
import threading
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from utils.logger import Logger
from utils.riot_id import resolve_riot_id

class LeagueLoopAPIHandler(BaseHTTPRequestHandler):
    # Task 137: Pre-serialized static byte buffers for high-frequency endpoints
    _HEALTH_OK_BYTES = b'{"status":"ok"}'
    _QUEUE_MODES_BYTES = json.dumps({
        'modes': {
            'ARAM': 450, 'Ranked Solo/Duo': 420, 'Ranked Flex': 440,
            'Draft Pick': 400, 'Quickplay': 490, 'Arena': 1700, 'Arena 3v6': 1710,
            'ARAM Mayhem': 2400, 'Brawl': 2300, 'URF': 900, 'ARURF': 1010,
            'Nexus Blitz': 1300, 'One For All': 1020, 'Ultimate Spellbook': 1400,
            'TFT Normal': 1090, 'TFT Ranked': 1100
        }
    }, separators=(',', ':')).encode('utf-8')

    # Pass the app instance via the server object
    @property
    def app_instance(self):
        return self.server.app_instance

    def log_message(self, format, *args):
        """Suppress default stderr logging for API requests."""
        pass

    def _set_cors_headers(self):
        """Set CORS headers with configured allowed origins."""
        # Get origin from request headers
        origin = self.headers.get('Origin', '')
        server = getattr(self.server, 'allowed_origins', ['http://localhost', 'http://127.0.0.1'])
        
        # Check if origin is in allowed list
        if origin and origin in server:
            self.send_header('Access-Control-Allow-Origin', origin)
        else:
            # Default to localhost for security
            self.send_header('Access-Control-Allow-Origin', 'http://localhost')
        
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')  # Cache preflight for 24 hours

    def _send_json(self, data, status_code=200):
        """Task 137: Optimized JSON response writer with compact serialization buffers to minimize GC and string allocations."""
        self.send_response(status_code)
        self._set_cors_headers()
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        if isinstance(data, (bytes, bytearray)):
            self.wfile.write(data)
        else:
            compact_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
            self.wfile.write(compact_bytes)

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == '/status':
            self.send_response(200)
            self._set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Fetch data safely from the app
            phase = "Unknown"
            power_state = False
            queue_mode = "None"
            summoner_info = None
            lobby_info = None
            
            app = self.app_instance
            if app:
                if hasattr(app, "automation") and app.automation:
                    phase = app.automation.last_phase
                    lcu = app.automation.lcu
                    if lcu and lcu.is_connected:
                        now = time.time()
                        # Refresh summoner info cache every 15 seconds
                        if not getattr(self.server, '_summoner_cache', None) or (now - getattr(self.server, '_summoner_cache_time', 0) > 15):
                            try:
                                s_res = lcu.request('GET', '/lol-summoner/v1/current-summoner', silent=True)
                                if s_res and s_res.status_code == 200:
                                    sdata = s_res.json()
                                    
                                    # Fetch ranked stats
                                    tier = "UNRANKED"
                                    rank = ""
                                    lp = 0
                                    r_res = lcu.request('GET', '/lol-ranked/v1/current-ranked-stats', silent=True)
                                    if r_res and r_res.status_code == 200:
                                        rdata = r_res.json()
                                        for q in rdata.get('queues', []):
                                            if q.get('queueType') == 'RANKED_SOLO_5x5':
                                                tier = q.get('tier', 'UNRANKED')
                                                rank = q.get('division', '')
                                                lp = q.get('leaguePoints', 0)
                                                break
                                    
                                    self.server._summoner_cache = {
                                        "summoner_name": resolve_riot_id(sdata),
                                        "profile_icon_id": sdata.get("profileIconId", 1),
                                        "level": sdata.get("summonerLevel", 1),
                                        "puuid": sdata.get("puuid"),
                                        "tier": tier,
                                        "rank": rank,
                                        "lp": lp
                                    }
                                    self.server._summoner_cache_time = now
                            except Exception as e:
                                Logger.debug("API", f"Error updating summoner cache: {e}")
                        
                        summoner_info = getattr(self.server, '_summoner_cache', None)
                        
                        # Fetch lobby info
                        try:
                            lobby_res = lcu.request('GET', '/lol-lobby/v2/lobby', silent=True)
                            if lobby_res and lobby_res.status_code == 200:
                                lobby_data = lobby_res.json()
                                members = []
                                for m in lobby_data.get('members', []):
                                    m_name = resolve_riot_id(m)
                                    if not m_name and summoner_info and m.get('puuid') == summoner_info.get("puuid"):
                                        m_name = summoner_info.get("summoner_name") or "Summoner"
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

                if hasattr(app, "sidebar") and app.sidebar:
                    power_state = getattr(app.sidebar, "power_state", False)
                    queue_mode = getattr(app.sidebar, "queue_label_text", "None")
                    if callable(queue_mode):
                        queue_mode = queue_mode()

            ws_telemetry = None
            if app and hasattr(app, "automation") and app.automation and hasattr(app.automation, "lcu") and app.automation.lcu:
                ws_telemetry = app.automation.lcu.get_ws_telemetry()

            sidebar = getattr(app, 'sidebar', None) if app else None
            data = {
                "phase": phase,
                "automation_enabled": power_state,
                "queue_mode": queue_mode,
                "queue_timer": getattr(sidebar, '_current_queue_time', 0) if sidebar else 0,
                "queue_estimated": getattr(sidebar, '_estimated_queue_time', 120) if sidebar else 120,
                "summoner_name": getattr(app, '_summoner_name', '') if app else '',
                "summoner": summoner_info,
                "lobby": lobby_info,
                "telemetry": ws_telemetry
            }
            self._send_json(data)
        elif self.path == '/health':
            # Item #49 & Task 137: Pre-serialized static health check endpoint
            self._send_json(self._HEALTH_OK_BYTES)
        elif self.path == '/healthz':
            # Structured health check endpoint for local API server monitoring
            app = self.app_instance
            lcu_connected = False
            automation_running = False
            phase = "Unknown"
            if app and hasattr(app, "automation") and app.automation:
                automation_running = getattr(app.automation, "running", False)
                phase = getattr(app.automation, "last_phase", "Unknown")
                lcu = getattr(app.automation, "lcu", None)
                if lcu:
                    lcu_connected = getattr(lcu, "is_connected", False)

            start_time = getattr(self.server, "start_time", time.time())
            uptime = round(time.time() - start_time, 2)

            health_data = {
                "status": "healthy",
                "uptime_seconds": uptime,
                "lcu_connected": lcu_connected,
                "automation_running": automation_running,
                "phase": phase,
                "timestamp": int(time.time())
            }
            self._send_json(health_data)
        elif self.path == '/telemetry':
            telemetry_data = {"websocket": None, "request_diagnostics": None, "status": "ok"}
            app = self.app_instance
            if app and hasattr(app, 'automation') and app.automation and hasattr(app.automation, 'lcu') and app.automation.lcu:
                telemetry_data["websocket"] = app.automation.lcu.get_ws_telemetry()
                req_diag = app.automation.lcu.get_request_diagnostics()
                if isinstance(req_diag, dict):
                    telemetry_data["request_diagnostics"] = req_diag
            self._send_json(telemetry_data)
        elif self.path == '/config':
            # Mobile Remote: expose current config toggles
            config_data = {}
            app = self.app_instance
            if app and hasattr(app, 'config'):
                cfg = app.config.cfg
                config_data = {
                    "auto_accept": cfg.get("auto_accept", False),
                    "auto_pick": cfg.get("auto_pick", ""),
                    "auto_ban": cfg.get("auto_ban", ""),
                    "auto_lock_in": cfg.get("auto_lock_in", False),
                    "auto_random_skin": cfg.get("auto_random_skin", False),
                    "auto_honor_enabled": cfg.get("auto_honor_enabled", False),
                    "auto_aram_swap": cfg.get("auto_aram_swap", False),
                    "auto_requeue": cfg.get("auto_requeue", False),
                    "aram_mode": cfg.get("aram_mode", "ARAM Mayhem"),
                    "skip_stats_enabled": cfg.get("skip_stats_enabled", False),
                    "priority_picker_enabled": cfg.get('priority_picker', {}).get('enabled', False),
                    "auto_join_enabled": cfg.get('auto_join_enabled', False),
                    "auto_runes_enabled": cfg.get('auto_runes_enabled', False),
                    "discord_rpc_enabled": cfg.get('discord_rpc_enabled', True),
                    "accept_delay": cfg.get('accept_delay', 0),
                    "honor_strategy": cfg.get('honor_strategy', 'random'),
                    "auto_hover": cfg.get('auto_hover', False),
                    "arena_auto_lock": cfg.get('arena_auto_lock', False),
                    "arena_synergy_enabled": cfg.get('arena_synergy_enabled', False)
                }
            self._send_json(config_data)
        elif self.path == '/aram-list':
            app = self.app_instance
            aram_list = []
            if app and hasattr(app, 'config'):
                pp = app.config.cfg.get('priority_picker', {})
                aram_list = pp.get('list', [])
            self._send_json({'list': aram_list})
        elif self.path == '/queue-modes':
            # Task 137: Pre-serialized static byte buffer for queue modes
            self._send_json(self._QUEUE_MODES_BYTES)
        elif self.path == '/champions':
            app = self.app_instance
            champs = []
            if app and hasattr(app, 'automation') and app.automation:
                champs = sorted(list(app.automation.assets.name_to_id.keys()))
            champs = [c.title() for c in champs]
            self._send_json({'champions': champs})
        elif self.path == '/champ-select':
            self.send_response(200)
            self._set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            app = self.app_instance
            result = {'active': False}

            if app and hasattr(app, 'automation') and app.automation and app.automation.lcu.is_connected:
                auto = app.automation
                try:
                    # Get session from LCU
                    sess_req = auto.lcu.request('GET', '/lol-champ-select/v1/session', silent=True)
                    if sess_req and sess_req.status_code == 200:
                        session = sess_req.json()
                        local_cell = session.get('localPlayerCellId', -1)

                        # Resolve champion names for teams
                        def resolve_team(team):
                            resolved = []
                            for p in team:
                                cid = p.get('championId', 0)
                                resolved.append({
                                    'cellId': p.get('cellId'),
                                    'championId': cid,
                                    'championName': auto.assets.get_champ_name(cid) if cid else '',
                                    'assignedPosition': p.get('assignedPosition', ''),
                                    'summonerId': p.get('summonerId', 0),
                                    'spell1Id': p.get('spell1Id', 0),
                                    'spell2Id': p.get('spell2Id', 0),
                                    'championPickIntent': p.get('championPickIntent', 0),
                                    'completed': False
                                })
                            return resolved

                        # Find my current action
                        current_action = None
                        action_phase = 'none'
                        for row in session.get('actions', []):
                            for action in row:
                                if action.get('actorCellId') == local_cell and not action.get('completed'):
                                    current_action = {
                                        'actionId': action.get('id'),
                                        'type': action.get('type', ''),
                                        'isMyTurn': action.get('isInProgress', False),
                                        'championId': action.get('championId', 0),
                                        'completed': action.get('completed', False)
                                    }
                                    action_phase = action.get('type', 'pick')
                                    break
                            if current_action:
                                break

                        # Resolve banned champions
                        bans = []
                        for b in session.get('bannedChampions', []):
                            if isinstance(b, dict):
                                bid = b.get('championId', 0)
                            else:
                                bid = b
                            if bid and bid > 0:
                                bans.append({'championId': bid, 'championName': auto.assets.get_champ_name(bid) or str(bid)})

                        # Resolve bench (ARAM)
                        bench = []
                        for b in session.get('benchChampions', []):
                            bid = b.get('championId', 0)
                            if bid:
                                bench.append({'championId': bid, 'championName': auto.assets.get_champ_name(bid) or str(bid)})

                        # Get pickable champions
                        pickable = []
                        pick_req = auto.lcu.request('GET', '/lol-champ-select/v1/pickable-champion-ids', silent=True)
                        if pick_req and pick_req.status_code == 200:
                            pick_ids = pick_req.json()
                            for pid in pick_ids:
                                name = auto.assets.get_champ_name(pid)
                                if name:
                                    pickable.append({'id': pid, 'name': name, 'key': name})

                        # Timer
                        timer = session.get('timer', {})
                        time_left = int(timer.get('adjustedTimeLeftInPhase', 0) / 1000)

                        result = {
                            'active': True,
                            'phase': action_phase,
                            'timer': time_left,
                            'localCellId': local_cell,
                            'myTeam': resolve_team(session.get('myTeam', [])),
                            'theirTeam': resolve_team(session.get('theirTeam', [])),
                            'bannedChampions': bans,
                            'benchChampions': bench,
                            'currentAction': current_action,
                            'pickableChampions': pickable,
                            'queueId': getattr(auto, 'current_queue_id', 0) or 0,
                            'rerollsRemaining': session.get('rerollsRemaining', 0)
                        }
                except Exception as e:
                    result = {'active': False, 'error': str(e)}

            self._send_json(result)
        elif self.path == '/accounts':
            app = self.app_instance
            accounts = []
            active_index = -1
            if app and hasattr(app, 'account_manager') and app.account_manager:
                am = app.account_manager
                # Return accounts excluding passwords
                for i, a in enumerate(am.get_accounts()):
                    accounts.append({
                        "label": a.get("label", ""),
                        "username": a.get("username", ""),
                        "tagline": a.get("tagline", ""),
                        "region": a.get("region", "NA1"),
                        "wallet": a.get("wallet", {"be": 0, "rp": 0})
                    })
                active_index = am.get_active_index()
            self._send_json({"accounts": accounts, "active_index": active_index})
        else:
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()

    def do_POST(self):
        if self.path == '/action':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            action = ""
            try:
                body = json.loads(post_data.decode('utf-8'))
                action = body.get("action", "")
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json({"status": "error", "message": "Invalid JSON"}, 400)
                return

            valid_actions = {"find_match", "launch_client", "toggle_automation", "dodge_queue", "toggle_honor",
                             "requeue", "play_again", "cancel_matchmaking", "change_queue_mode", "set_status", "mass_invite",
                             "leave_lobby", "create_lobby"}
            if action not in valid_actions:
                self._send_json({"status": "error", "message": f"Unknown action: {action}"}, 400)
                return

            app = self.app_instance
            if app:
                if action == "find_match":
                    app.after(0, app._hotkey_find_match)
                elif action == "launch_client":
                    app.after(0, app._hotkey_launch_client)
                elif action == "toggle_automation":
                    app.after(0, app._hotkey_toggle_automation)
                elif action == "dodge_queue":
                    # Cancel matchmaking / leave queue
                    if hasattr(app, 'automation') and app.automation:
                        app.after(0, lambda: app.automation.lcu.request('DELETE', '/lol-lobby/v2/matchmaking/search'))
                elif action == "toggle_honor":
                    # Toggle the auto_honor_enabled config flag
                    if hasattr(app, 'config'):
                        current = app.config.cfg.get('auto_honor_enabled', False)
                        app.config.cfg['auto_honor_enabled'] = not current
                        app.config.save()
                elif action == 'requeue':
                    if hasattr(app, 'sidebar') and app.sidebar:
                        app.after(0, app.sidebar._force_requeue)
                elif action == 'play_again':
                    if hasattr(app, 'sidebar') and app.sidebar:
                        app.after(0, app.sidebar._play_again)
                elif action == 'cancel_matchmaking':
                    if hasattr(app, 'automation') and app.automation:
                        app.after(0, lambda: app.automation.lcu.request('DELETE', '/lol-lobby/v2/lobby/matchmaking/search'))
                elif action == 'change_queue_mode':
                    queue_mode = body.get('queue_mode', '')
                    if hasattr(app, 'sidebar') and app.sidebar and queue_mode:
                        app.after(0, lambda: app.sidebar._on_mode_change(queue_mode))
                elif action == 'set_status':
                    message = body.get('message', '')
                    if hasattr(app, 'automation') and app.automation and message:
                        threading.Thread(target=lambda: app.automation.set_custom_status(message), daemon=True).start()
                elif action == 'mass_invite':
                    if hasattr(app, 'automation') and app.automation:
                        threading.Thread(target=lambda: app.automation.mass_invite_friends(), daemon=True).start()
                elif action == 'leave_lobby':
                    if hasattr(app, 'automation') and app.automation:
                        app.after(0, lambda: app.automation.lcu.request('DELETE', '/lol-lobby/v2/lobby'))
                elif action == 'create_lobby':
                    queue_mode = body.get('queue_mode', '')
                    if queue_mode and hasattr(app, 'sidebar') and app.sidebar:
                        target_q_id = app.sidebar._get_queue_id_for_mode(queue_mode)
                        if target_q_id:
                            app.after(0, lambda: app.automation.lcu.request("POST", "/lol-lobby/v2/lobby", {"queueId": target_q_id}))
            
            self._send_json({"status": "success", "action": action})
        elif self.path == '/config':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
                key = body.get('key', '')
                value = body.get('value')
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json({'status': 'error', 'message': 'Invalid JSON'}, 400)
                return

            # Whitelist of remotely-writable config keys
            writable_keys = {
                'auto_accept', 'auto_lock_in', 'auto_random_skin', 'auto_honor_enabled',
                'auto_join_enabled', 'skip_stats_enabled', 'auto_runes_enabled',
                'accept_delay', 'honor_strategy',
                'auto_hover', 'arena_auto_lock', 'arena_synergy_enabled',
                'aram_mode'
            }

            if key not in writable_keys:
                self._send_json({'status': 'error', 'message': f'Key not writable: {key}'}, 403)
                return

            app = self.app_instance
            if app and hasattr(app, 'config'):
                app.config.cfg[key] = value
                app.config.save()

            self._send_json({'status': 'success', 'key': key, 'value': value})
        elif self.path == '/accounts/login':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
                idx = int(body.get('index', -1))
            except (json.JSONDecodeError, ValueError):
                self._send_json({'status': 'error', 'message': 'Invalid JSON or index'}, 400)
                return

            app = self.app_instance
            if app and hasattr(app, 'account_manager') and app.account_manager:
                app.account_manager.login_account(idx, log_func=None, completion_func=None)

            self._send_json({"status": "success", "message": "Login initiated"})
        elif self.path == '/accounts/logout':
            app = self.app_instance
            if app and hasattr(app, 'account_manager') and app.account_manager:
                app.account_manager.sign_out(log_func=None, completion_func=None)

            self._send_json({"status": "success", "message": "Logout initiated"})
        elif self.path == '/champ-select/pick' or self.path == '/champ-select/ban':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
                champ_id = body.get('championId', 0)
            except:
                self._send_json({'status': 'error', 'message': 'Invalid JSON'}, 400)
                return

            app = self.app_instance
            result = {'status': 'error', 'message': 'Not in champ select'}
            status_code = 400

            if app and hasattr(app, 'automation') and app.automation:
                auto = app.automation
                try:
                    sess_req = auto.lcu.request('GET', '/lol-champ-select/v1/session', silent=True)
                    if sess_req and sess_req.status_code == 200:
                        session = sess_req.json()
                        local_cell = session.get('localPlayerCellId')
                        action_type = 'pick' if '/pick' in self.path else 'ban'

                        # Find the active action for this type
                        target_action = None
                        for row in session.get('actions', []):
                            for action in row:
                                if (action.get('actorCellId') == local_cell and
                                    not action.get('completed') and
                                    action.get('type') == action_type):
                                    target_action = action
                                    break
                            if target_action:
                                break

                        if target_action:
                            action_id = target_action.get('id')
                            res = auto.lcu.request('PATCH', f'/lol-champ-select/v1/session/actions/{action_id}',
                                                  data={'championId': champ_id})
                            if res and res.status_code in (200, 204):
                                name = auto.assets.get_champ_name(champ_id) or str(champ_id)
                                result = {'status': 'success', 'championName': name}
                                status_code = 200
                            else:
                                result = {'status': 'error', 'message': f'LCU returned {res.status_code if res else "no response"}'}
                        else:
                            result = {'status': 'error', 'message': f'No active {action_type} action found'}
                except Exception as e:
                    result = {'status': 'error', 'message': str(e)}

            self._send_json(result, status_code)

        elif self.path == '/champ-select/lock':
            app = self.app_instance
            result = {'status': 'error', 'message': 'Not in champ select'}
            status_code = 400

            if app and hasattr(app, 'automation') and app.automation:
                auto = app.automation
                try:
                    sess_req = auto.lcu.request('GET', '/lol-champ-select/v1/session', silent=True)
                    if sess_req and sess_req.status_code == 200:
                        session = sess_req.json()
                        local_cell = session.get('localPlayerCellId')

                        # Find any active (in-progress) action for me
                        target_action = None
                        for row in session.get('actions', []):
                            for action in row:
                                if (action.get('actorCellId') == local_cell and
                                    not action.get('completed')):
                                    target_action = action
                                    break
                            if target_action:
                                break

                        if target_action and target_action.get('championId', 0) > 0:
                            action_id = target_action.get('id')
                            champ_id = target_action.get('championId')
                            res = auto.lcu.request('PATCH', f'/lol-champ-select/v1/session/actions/{action_id}',
                                                  data={'championId': champ_id, 'completed': True})
                            if res and res.status_code in (200, 204):
                                result = {'status': 'success'}
                                status_code = 200
                            else:
                                result = {'status': 'error', 'message': f'Lock failed: {res.status_code if res else "no response"}'}
                        else:
                            result = {'status': 'error', 'message': 'No champion selected to lock'}
                except Exception as e:
                    result = {'status': 'error', 'message': str(e)}

            self._send_json(result, status_code)

        elif self.path == '/champ-select/bench-swap':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
                champ_id = body.get('championId', 0)
            except:
                self.send_response(400)
                self._set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': 'Invalid JSON'}).encode('utf-8'))
                return

            app = self.app_instance
            result = {'status': 'error', 'message': 'Not in champ select'}
            status_code = 400

            if app and hasattr(app, 'automation') and app.automation:
                auto = app.automation
                try:
                    res = auto.lcu.request('POST', f'/lol-champ-select/v1/session/bench/swap/{champ_id}')
                    if res and res.status_code in (200, 204):
                        name = auto.assets.get_champ_name(champ_id) or str(champ_id)
                        result = {'status': 'success', 'championName': name}
                        status_code = 200
                    else:
                        result = {'status': 'error', 'message': f'Swap failed: {res.status_code if res else "no response"}'}
                except Exception as e:
                    result = {'status': 'error', 'message': str(e)}

            self.send_response(status_code)
            self._set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))

        elif self.path == '/champ-select/spells':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
                spell1_id = body.get('spell1Id')
                spell2_id = body.get('spell2Id')
            except:
                self.send_response(400)
                self._set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': 'Invalid JSON'}).encode('utf-8'))
                return

            app = self.app_instance
            result = {'status': 'error', 'message': 'Not in champ select'}
            status_code = 400

            if app and hasattr(app, 'automation') and app.automation:
                auto = app.automation
                try:
                    payload = {}
                    if spell1_id is not None:
                        payload['spell1Id'] = int(spell1_id)
                    if spell2_id is not None:
                        payload['spell2Id'] = int(spell2_id)
                    
                    res = auto.lcu.request('PATCH', '/lol-champ-select/v1/session/my-selection', data=payload)
                    if res and res.status_code in (200, 204):
                        result = {'status': 'success'}
                        status_code = 200
                    else:
                        result = {'status': 'error', 'message': f'LCU returned {res.status_code if res else "no response"}'}
                except Exception as e:
                    result = {'status': 'error', 'message': str(e)}

            self.send_response(status_code)
            self._set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))

        elif self.path == '/champ-select/reroll':
            app = self.app_instance
            result = {'status': 'error', 'message': 'Not in champ select'}
            status_code = 400

            if app and hasattr(app, 'automation') and app.automation:
                auto = app.automation
                try:
                    res = auto.lcu.request('POST', '/lol-champ-select/v1/session/my-selection/reroll')
                    if res and res.status_code in (200, 204):
                        result = {'status': 'success'}
                        status_code = 200
                    else:
                        result = {'status': 'error', 'message': f'Reroll failed: {res.status_code if res else "no response"}'}
                except Exception as e:
                    result = {'status': 'error', 'message': str(e)}

            self.send_response(status_code)
            self._set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))

        elif self.path == '/ready-check/accept' or self.path == '/ready-check/decline':
            app = self.app_instance
            action_type = 'accept' if '/accept' in self.path else 'decline'
            result = {'status': 'error', 'message': 'Not in champ select'}
            status_code = 400

            if app and hasattr(app, 'automation') and app.automation:
                auto = app.automation
                try:
                    res = auto.lcu.request('POST', f'/lol-matchmaking/v1/ready-check/{action_type}')
                    if res and res.status_code in (200, 204):
                        result = {'status': 'success'}
                        status_code = 200
                    else:
                        result = {'status': 'error', 'message': f'Ready check {action_type} failed: {res.status_code if res else "no response"}'}
                except Exception as e:
                    result = {'status': 'error', 'message': str(e)}

            self.send_response(status_code)
            self._set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))

        elif self.path == '/aram-list':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
                aram_list = body.get('list', [])
            except:
                self.send_response(400)
                self._set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': 'Invalid JSON'}).encode('utf-8'))
                return

            app = self.app_instance
            if app and hasattr(app, 'config'):
                pp = app.config.cfg.get('priority_picker', {})
                pp['list'] = aram_list
                app.config.cfg['priority_picker'] = pp
                app.config.save()
                
                try:
                    from core.events import EventBus
                    EventBus.emit("config_event", app.config.cfg)
                except Exception as exc:
                    Logger.debug("LocalApi", "do_POST suppressed an error", exc=exc)

            self.send_response(200)
            self._set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))

        else:
            self.send_response(404)
            self._set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": "Not found"}).encode('utf-8'))

    # Disable default logging to avoid terminal spam
    def log_message(self, format, *args):
        pass

def get_local_ip():
    try:
        # Create a dummy socket to find the local IP acting towards the internet
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def ensure_firewall_rule(port):
    """Auto-create a Windows Firewall inbound rule so mobile devices can connect."""
    if sys.platform != 'win32':
        return
    rule_name = 'LeagueLoop Remote'
    try:
        # Check if rule already exists
        check = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', f'name={rule_name}'],
            capture_output=True, text=True, timeout=5
        )
        if check.returncode == 0 and rule_name in check.stdout:
            Logger.info("API", "Firewall rule already exists")
            return
        # Create the rule
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
             f'name={rule_name}',
             'dir=in', 'action=allow', 'protocol=TCP',
             f'localport={port}',
             'profile=private,public',
             'description=Allows LeagueLoop mobile remote connections over LAN'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            Logger.info("API", f"Firewall rule created for port {port}")
        else:
            Logger.warning("API", f"Firewall rule creation returned: {result.stderr.strip()}")
    except Exception as e:
        Logger.warning("API", f"Could not auto-configure firewall: {e}")

def start_api_server(app_instance, port=8337, bind_local=True):
    """
    Start the Local API HTTP server.
    
    Args:
        app_instance: The LeagueLoopApp instance
        port: Port number (default 8337)
        bind_local: If True, bind to localhost only (more secure). 
                    If False, bind to 0.0.0.0 to allow LAN access.
    
    Returns:
        Tuple of (host_ip, port) or (None, None) on failure
    """
    # Security: Default to localhost-only binding unless remote access is explicitly enabled
    # Port 8337 = LEET -> L E E T -> 8337 (sort of)
    host = '127.0.0.1' if bind_local else '0.0.0.0'
    
    try:
        # Only configure firewall if binding to all interfaces
        if not bind_local:
            ensure_firewall_rule(port)

        server = ThreadingHTTPServer((host, port), LeagueLoopAPIHandler)
        server.app_instance = app_instance
        server.start_time = time.time()
        server._summoner_cache = None
        server._summoner_cache_time = 0
        server.allowed_origins = [
            'http://localhost',
            'http://127.0.0.1',
            # Add mobile companion origins here when pairing is implemented
        ]
        
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        
        if bind_local:
            Logger.info("API", f"Local API started on http://localhost:{port} (localhost only)")
            local_ip = get_local_ip()
            return local_ip, port
        else:
            local_ip = get_local_ip()
            Logger.info("API", f"Remote Link API started on http://{local_ip}:{port}")
            Logger.warning("API", "Remote access enabled - ensure proper authentication is configured")
            return local_ip, port
    except Exception as e:
        Logger.error("API", f"Failed to start API server: {e}")
        return None, None
