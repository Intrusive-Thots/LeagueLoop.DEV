"""
HTTP Session Factory
Provides shared, pooled requests.Session instances to minimize socket and TLS negotiation overhead.
"""
from __future__ import annotations

import requests
import urllib3
from typing import Optional

# Suppress insecure HTTPS request warnings for local LCU self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_shared_session: Optional[requests.Session] = None


def create_pooled_session(
    pool_connections: int = 20,
    pool_maxsize: int = 20,
    max_retries: int = 1,
    verify_ssl: bool = False,
) -> requests.Session:
    """Create a new requests.Session configured with connection pooling and custom retry logic."""
    session = requests.Session()
    session.verify = verify_ssl

    adapter = requests.adapters.HTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=max_retries,
        pool_block=False,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_shared_session() -> requests.Session:
    """Returns a singleton shared requests.Session for general outbound HTTP requests."""
    global _shared_session
    if _shared_session is None:
        _shared_session = create_pooled_session(pool_connections=20, pool_maxsize=20, max_retries=2, verify_ssl=False)
    return _shared_session
