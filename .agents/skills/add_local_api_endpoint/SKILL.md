---
name: Add Local API Endpoint
description: Add an HTTP route to the LeagueLoop Local API (port 8337) used by the Mobile Companion
---

# Add Local API Endpoint

The Local API is the HTTP control surface the **Mobile Companion**
(`LeagueLoopMobile/`, Capacitor/Vite) talks to. It lives in
`src/services/local_api.py`, served by `LeagueLoopAPIHandler`
(a `ThreadingHTTPServer`) on **port 8337**, localhost-only by default.

> Not the same as the LCU. Reaching into the League Client → use the
> `add_lcu_api_endpoint` skill. This skill is the desktop↔mobile contract.

## How routing works

Routing is an explicit `if / elif self.path == ...` chain inside two methods:

- `do_GET(self)` — read endpoints (`/status`, `/health`, `/config`,
  `/champ-select`, `/accounts`, ...)
- `do_POST(self)` — commands (`/action`, `/config`, `/champ-select/pick`, ...)

Helpers on the handler: `self._send_json(data, status=200)`,
`self._set_cors_headers()`, `self.app_instance` (the running desktop app).
`registry.py`'s `GET_ROUTES`/`POST_ROUTES` dicts exist but are not the live
dispatch path — follow the `if/elif` chain.

## Add a GET endpoint

In `do_GET`, add a branch (keep it before any catch-all 404):

```python
elif self.path == '/loot':
    app = self.app_instance
    data = {"items": []}
    if app and hasattr(app, 'automation') and app.automation:
        lcu = app.automation.lcu
        if lcu and lcu.is_connected:
            res = lcu.request('GET', '/lol-loot/v1/player-loot', silent=True)
            if res and res.status_code == 200:
                data = {"items": res.json()}
    self._send_json(data)
```

## Add a POST command

Prefer extending the existing `/action` endpoint for simple fire-and-forget
commands: add the name to the `valid_actions` set in `do_POST`, then handle it.
GUI-affecting work must be marshalled onto the desktop app's main loop with
`app.after(0, ...)`:

```python
valid_actions = {..., "disenchant_all"}
...
elif action == "disenchant_all":
    if hasattr(app, 'automation') and app.automation:
        app.after(0, app.automation.disenchant_all)
```

For a command with its own body/path, add a dedicated `elif self.path == ...`
branch that reads the body:

```python
elif self.path == '/loot/disenchant':
    length = int(self.headers.get('Content-Length', 0))
    try:
        body = json.loads(self.rfile.read(length).decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        self._send_json({"status": "error", "message": "Invalid JSON"}, 400)
        return
    champ_id = body.get("championId")
    ...
    self._send_json({"status": "ok"})
```

## Rules

- **Always** return via `self._send_json(...)` so CORS headers + content-type
  are set consistently. Add a `do_OPTIONS` preflight branch only if you
  introduce new headers.
- **Never** block the HTTP thread on GUI work — hand it to `app.after(0, ...)`.
- **Never** touch the desktop app's Qt/Tk widgets directly from the handler
  thread (THREAD-001). Go through `app.after` / the automation engine.
- Validate and guard every field from the request body; assume the mobile
  client can send anything.
- Keep default binding localhost-only. LAN exposure (`bind_local=False`) is
  opt-in and firewall-gated in `start_api_server`.
- Scope: LCU only. No port 2999 / Live Client Data.

## Verify

- Start the app, then `curl http://localhost:8337/loot` (GET) or
  `curl -X POST http://localhost:8337/action -d '{"action":"disenchant_all"}'`.
- Add coverage in `tests/test_services_local_api.py` and run the suite.
- Update the Mobile Companion client to consume the new route.
