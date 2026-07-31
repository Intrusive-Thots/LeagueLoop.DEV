"""
Champion Select API Routes Module for LeagueLoop local HTTP server.

Handles endpoints for inspecting champion select session state, intent, bans, and picks.
"""

import json
from services.api.registry import register_get, register_post

@register_get('/champ-select')
def handle_get_champ_select(handler):
    app = handler.app_instance
    result = {'active': False}

    if app and hasattr(app, 'automation') and app.automation and app.automation.lcu.is_connected:
        auto = app.automation
        try:
            sess_req = auto.lcu.request('GET', '/lol-champ-select/v1/session', silent=True)
            if sess_req and sess_req.status_code == 200:
                session = sess_req.json()
                local_cell = session.get('localPlayerCellId', -1)

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

                bans = []
                for b in session.get('bannedChampions', []):
                    if isinstance(b, dict):
                        bid = b.get('championId', 0)
                    else:
                        bid = b
                    if bid and bid > 0:
                        bans.append({'championId': bid, 'championName': auto.assets.get_champ_name(bid) or str(bid)})

                bench = []
                for b in session.get('benchChampions', []):
                    bid = b.get('championId', 0)
                    if bid:
                        bench.append({'championId': bid, 'championName': auto.assets.get_champ_name(bid) or str(bid)})

                pickable = []
                pick_req = auto.lcu.request('GET', '/lol-champ-select/v1/pickable-champion-ids', silent=True)
                if pick_req and pick_req.status_code == 200:
                    pick_ids = pick_req.json()
                    for pid in pick_ids:
                        name = auto.assets.get_champ_name(pid)
                        if name:
                            pickable.append({'id': pid, 'name': name, 'key': name})

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

    handler.send_json(result)


@register_post('/champ-select/pick')
def handle_pick(handler):
    _handle_pick_ban(handler, 'pick')

@register_post('/champ-select/ban')
def handle_ban(handler):
    _handle_pick_ban(handler, 'ban')

def _handle_pick_ban(handler, action_type):
    content_length = int(handler.headers.get('Content-Length', 0))
    post_data = handler.rfile.read(content_length)
    try:
        body = json.loads(post_data.decode('utf-8'))
        champ_id = body.get('championId', 0)
    except:
        handler.send_json({'status': 'error', 'message': 'Invalid JSON'}, 400)
        return

    app = handler.app_instance
    result = {'status': 'error', 'message': 'Not in champ select'}
    status_code = 400

    if app and hasattr(app, 'automation') and app.automation:
        auto = app.automation
        try:
            sess_req = auto.lcu.request('GET', '/lol-champ-select/v1/session', silent=True)
            if sess_req and sess_req.status_code == 200:
                session = sess_req.json()
                local_cell = session.get('localPlayerCellId')

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

    handler.send_json(result, status_code)


@register_post('/champ-select/lock')
def handle_lock(handler):
    app = handler.app_instance
    result = {'status': 'error', 'message': 'Not in champ select'}
    status_code = 400

    if app and hasattr(app, 'automation') and app.automation:
        auto = app.automation
        try:
            sess_req = auto.lcu.request('GET', '/lol-champ-select/v1/session', silent=True)
            if sess_req and sess_req.status_code == 200:
                session = sess_req.json()
                local_cell = session.get('localPlayerCellId')

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

    handler.send_json(result, status_code)


@register_post('/champ-select/bench-swap')
def handle_bench_swap(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    post_data = handler.rfile.read(content_length)
    try:
        body = json.loads(post_data.decode('utf-8'))
        champ_id = body.get('championId', 0)
    except:
        handler.send_json({'status': 'error', 'message': 'Invalid JSON'}, 400)
        return

    app = handler.app_instance
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

    handler.send_json(result, status_code)


@register_post('/champ-select/spells')
def handle_spells(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    post_data = handler.rfile.read(content_length)
    try:
        body = json.loads(post_data.decode('utf-8'))
        spell1_id = body.get('spell1Id')
        spell2_id = body.get('spell2Id')
    except:
        handler.send_json({'status': 'error', 'message': 'Invalid JSON'}, 400)
        return

    app = handler.app_instance
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

    handler.send_json(result, status_code)


@register_post('/champ-select/reroll')
def handle_reroll(handler):
    app = handler.app_instance
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

    handler.send_json(result, status_code)
