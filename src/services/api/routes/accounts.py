"""
Accounts API Routes Module for LeagueLoop local HTTP server.

Handles endpoints for listing, adding, and switching stored Riot accounts.
"""

import json
from services.api.registry import register_get, register_post

@register_get('/accounts')
def handle_get_accounts(handler):
    app = handler.app_instance
    accounts = []
    active_index = -1
    if app and hasattr(app, 'account_manager') and app.account_manager:
        am = app.account_manager
        for i, a in enumerate(am.get_accounts()):
            accounts.append({
                "label": a.get("label", ""),
                "username": a.get("username", ""),
                "tagline": a.get("tagline", ""),
                "region": a.get("region", "NA1"),
                "wallet": a.get("wallet", {"be": 0, "rp": 0})
            })
        active_index = am.get_active_index()
    handler.send_json({"accounts": accounts, "active_index": active_index})


@register_post('/accounts/login')
def handle_login(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    post_data = handler.rfile.read(content_length)
    try:
        body = json.loads(post_data.decode('utf-8'))
        idx = int(body.get('index', -1))
    except (json.JSONDecodeError, ValueError):
        handler.send_json({'status': 'error', 'message': 'Invalid JSON or index'}, 400)
        return

    app = handler.app_instance
    if app and hasattr(app, 'account_manager') and app.account_manager:
        app.account_manager.login_account(idx, log_func=None, completion_func=None)

    handler.send_json({"status": "success", "message": "Login initiated"})


@register_post('/accounts/logout')
def handle_logout(handler):
    app = handler.app_instance
    if app and hasattr(app, 'account_manager') and app.account_manager:
        app.account_manager.sign_out(log_func=None, completion_func=None)

    handler.send_json({"status": "success", "message": "Logout initiated"})
