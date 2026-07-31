"""
Local API Server Module for LeagueLoop.

Runs an HTTP server locally to allow web apps, companion scripts, and external tools to interact with LeagueLoop.
"""

import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from utils.logger import Logger
from services.api.registry import GET_ROUTES, POST_ROUTES

class LeagueLoopAPIHandler(BaseHTTPRequestHandler):
    @property
    def app_instance(self):
        return self.server.app_instance

    def log_message(self, format, *args):
        pass

    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def send_json(self, data, status=200):
        self.send_response(status)
        self._set_cors_headers()
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        handler_func = GET_ROUTES.get(self.path)
        if handler_func:
            try:
                handler_func(self)
            except Exception as e:
                Logger.error("API", f"Error in GET {self.path}: {e}")
                self.send_json({"error": str(e)}, 500)
        else:
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()

    def do_POST(self):
        handler_func = POST_ROUTES.get(self.path)
        if handler_func:
            try:
                handler_func(self)
            except Exception as e:
                Logger.error("API", f"Error in POST {self.path}: {e}")
                self.send_json({"error": str(e)}, 500)
        else:
            self.send_json({"status": "error", "message": "Not found"}, 404)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def ensure_firewall_rule(port):
    if sys.platform != 'win32':
        return
    rule_name = 'LeagueLoop Remote'
    try:
        check = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', f'name={rule_name}'],
            capture_output=True, text=True, timeout=5
        )
        if check.returncode == 0 and rule_name in check.stdout:
            Logger.info("API", "Firewall rule already exists")
            return
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
            Logger.warn("API", f"Firewall rule creation returned: {result.stderr.strip()}")
    except Exception as e:
        Logger.warn("API", f"Could not auto-configure firewall: {e}")

def start_api_server(app_instance, port=8337):
    host = '0.0.0.0'
    try:
        ensure_firewall_rule(port)
        server = ThreadingHTTPServer((host, port), LeagueLoopAPIHandler)
        server.app_instance = app_instance
        server._summoner_cache = None
        server._summoner_cache_time = 0

        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        local_ip = get_local_ip()
        Logger.info("API", f"Remote Link API started on http://{local_ip}:{port}")
        return local_ip, port
    except Exception as e:
        Logger.error("API", f"Failed to start API server: {e}")
        return None, None
