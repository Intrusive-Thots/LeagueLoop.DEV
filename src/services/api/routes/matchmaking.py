"""
Matchmaking API Routes Module for LeagueLoop local HTTP server.

Handles matchmaking actions such as queueing, ready-check acceptance, and lobby management.
"""

import json
from services.api.registry import register_post
from core.events import EventBus
from services.settings_service import get_settings_service
from services.queue_service import get_queue_service

@register_post('/action')
def handle_action(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    post_data = handler.rfile.read(content_length)
    
    action = ""
    try:
        body = json.loads(post_data.decode('utf-8'))
        action = body.get("action", "")
    except (json.JSONDecodeError, UnicodeDecodeError):
        handler.send_json({"status": "error", "message": "Invalid JSON"}, 400)
        return

    valid_actions = {"find_match", "launch_client", "toggle_automation", "dodge_queue", "toggle_honor",
                     "requeue", "play_again", "cancel_matchmaking", "change_queue_mode", "set_status", "mass_invite",
                     "leave_lobby", "create_lobby"}
    if action not in valid_actions:
        handler.send_json({"status": "error", "message": f"Unknown action: {action}"}, 400)
        return

    settings = get_settings_service()
    queue_service = get_queue_service()
    app = handler.app_instance

    if action == "find_match":
        EventBus.emit("action:find_match")
    elif action == "launch_client":
        EventBus.emit("action:launch_client")
    elif action == "toggle_automation":
        EventBus.emit("action:toggle_automation")
    elif action == "dodge_queue":
        if queue_service:
            queue_service.cancel_matchmaking()
    elif action == "toggle_honor":
        if settings:
            current = settings.get('auto_honor_enabled', False)
            settings.set('auto_honor_enabled', not current)
    elif action == 'requeue':
        if queue_service:
            queue_service.find_match()
    elif action == 'play_again':
        if queue_service:
            queue_service.play_again()
    elif action == 'cancel_matchmaking':
        if queue_service:
            queue_service.cancel_matchmaking()
    elif action == 'change_queue_mode':
        queue_mode = body.get('queue_mode', '')
        if settings and queue_mode:
            settings.set('aram_mode', queue_mode)
            EventBus.emit("action:change_queue_mode", queue_mode)
    elif action == 'set_status':
        message = body.get('message', '')
        if message:
            EventBus.emit("action:set_status", message)
    elif action == 'mass_invite':
        EventBus.emit("action:mass_invite")
    elif action == 'leave_lobby':
        if queue_service:
            queue_service.leave_lobby()
    elif action == 'create_lobby':
        queue_mode = body.get('queue_mode', '')
        if queue_mode and queue_service:
            queue_service.create_lobby(queue_mode)
    
    handler.send_json({"status": "success", "action": action})


@register_post('/ready-check/accept')
def handle_ready_accept(handler):
    _handle_ready_check(handler, 'accept')

@register_post('/ready-check/decline')
def handle_ready_decline(handler):
    _handle_ready_check(handler, 'decline')

def _handle_ready_check(handler, action_type):
    app = handler.app_instance
    result = {'status': 'error', 'message': 'Not connected'}
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

    handler.send_json(result, status_code)
