import json
from services.api.registry import register_get, register_post
from core.events import EventBus

@register_get('/aram-list')
def handle_get_aram_list(handler):
    app = handler.app_instance
    aram_list = []
    if app and hasattr(app, 'config'):
        pp = app.config.cfg.get('priority_picker', {})
        aram_list = pp.get('list', [])
    handler.send_json({'list': aram_list})

@register_post('/aram-list')
def handle_post_aram_list(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    post_data = handler.rfile.read(content_length)
    try:
        body = json.loads(post_data.decode('utf-8'))
        aram_list = body.get('list', [])
    except:
        handler.send_json({'status': 'error', 'message': 'Invalid JSON'}, 400)
        return

    app = handler.app_instance
    if app and hasattr(app, 'config'):
        pp = app.config.cfg.get('priority_picker', {})
        pp['list'] = aram_list
        app.config.cfg['priority_picker'] = pp
        app.config.save()
        
        try:
            EventBus.emit("config_event", app.config.cfg)
        except:
            pass

    handler.send_json({'status': 'success'})


@register_get('/queue-modes')
def handle_get_queue_modes(handler):
    modes = {
        'ARAM': 450, 'Ranked Solo/Duo': 420, 'Ranked Flex': 440,
        'Draft Pick': 400, 'Quickplay': 490, 'Arena': 1700, 'Arena 3v6': 1710,
        'ARAM Mayhem': 2400, 'Brawl': 2300, 'URF': 900, 'ARURF': 1010,
        'Nexus Blitz': 1300, 'One For All': 1020, 'Ultimate Spellbook': 1400,
        'TFT Normal': 1090, 'TFT Ranked': 1100
    }
    handler.send_json({'modes': modes})


@register_get('/champions')
def handle_get_champions(handler):
    app = handler.app_instance
    champs = []
    if app and hasattr(app, 'automation') and app.automation:
        champs = sorted(list(app.automation.assets.name_to_id.keys()))
    champs = [c.title() for c in champs]
    handler.send_json({'champions': champs})
