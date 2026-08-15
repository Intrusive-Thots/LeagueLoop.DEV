"""
API Route Registry Module for LeagueLoop local HTTP server.

Registers GET and POST route handlers using function decorators.
"""

from typing import Callable, Dict, Any

GET_ROUTES: Dict[str, Callable] = {}
POST_ROUTES: Dict[str, Callable] = {}
