"""
Configuration API Routes Module for LeagueLoop local HTTP server.

Handles reading and updating persistent configuration settings over local HTTP requests.
"""

import json
from services.api.registry import register_get, register_post
from core.events import EventBus

@register_get('/config')
def handle_get_config(handler):
    config_data = {}
    app = handler.app_instance
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
            "arena_synergy_enabled": cfg.get('arena_synergy_enabled', False),
            "honor_party_first": cfg.get("honor_party_first", False)
        }
    handler.send_json(config_data)

@register_post('/config')
def handle_post_config(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    post_data = handler.rfile.read(content_length)
    try:
        body = json.loads(post_data.decode('utf-8'))
        key = body.get('key', '')
        value = body.get('value')
    except (json.JSONDecodeError, UnicodeDecodeError):
        handler.send_json({'status': 'error', 'message': 'Invalid JSON'}, 400)
        return

    writable_keys = {
        'auto_accept', 'auto_lock_in', 'auto_random_skin', 'auto_honor_enabled',
        'auto_join_enabled', 'skip_stats_enabled', 'auto_runes_enabled',
        'discord_rpc_enabled', 'accept_delay', 'honor_strategy',
        'auto_hover', 'arena_auto_lock', 'arena_synergy_enabled',
        'aram_mode', 'honor_party_first'
    }

    if key not in writable_keys:
        handler.send_json({'status': 'error', 'message': f'Key not writable: {key}'}, 403)
        return

    app = handler.app_instance
    if app and hasattr(app, 'config'):
        app.config.cfg[key] = value
        app.config.save()
        try:
            EventBus.emit("config_event", app.config.cfg)
        except Exception:
            pass

    handler.send_json({'status': 'success', 'key': key, 'value': value})
