"""
API Route Registry Module for LeagueLoop local HTTP server.

Registers GET and POST route handlers using function decorators.
"""

from typing import Callable, Dict, Any

GET_ROUTES: Dict[str, Callable] = {}
POST_ROUTES: Dict[str, Callable] = {}

def register_get(path: str):
    def decorator(func: Callable):
        GET_ROUTES[path] = func
        return func
    return decorator

def register_post(path: str):
    def decorator(func: Callable):
        POST_ROUTES[path] = func
        return func
    return decorator
