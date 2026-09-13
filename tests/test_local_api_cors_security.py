import pytest
from src.services.local_api import LeagueLoopAPIHandler

class DummyServer:
    allowed_origins = ['http://localhost', 'http://127.0.0.1']

class MockRequest:
    def makefile(self, *args, **kwargs):
        from io import BytesIO
        return BytesIO(b"GET / HTTP/1.0\r\nOrigin: http://evil.com\r\n\r\n")

class MockAPIHandler(LeagueLoopAPIHandler):
    def __init__(self, request, client_address, server):
        self.headers_sent = {}
        self.server = server
        self.requestline = 'GET / HTTP/1.0'
        self.request_version = 'HTTP/1.0'
        self.command = 'GET'
        self.headers = {'Origin': 'http://evil.com'}

    def send_header(self, keyword, value):
        self.headers_sent[keyword] = value

def test_cors_headers_unauthorized_origin():
    h = MockAPIHandler(MockRequest(), ('127.0.0.1', 80), DummyServer())
    h._set_cors_headers()
    assert 'Access-Control-Allow-Origin' not in h.headers_sent

def test_cors_headers_authorized_origin():
    h = MockAPIHandler(MockRequest(), ('127.0.0.1', 80), DummyServer())
    h.headers = {'Origin': 'http://127.0.0.1'}
    h._set_cors_headers()
    assert 'Access-Control-Allow-Origin' in h.headers_sent
    assert h.headers_sent['Access-Control-Allow-Origin'] == 'http://127.0.0.1'
