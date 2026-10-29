"""
Which account is the League client signed in as?

After a switch the Riot Client can hand League the *previous* account's
product tokens (seen live: Riot Client on the new account, League logged in
as the old one). A switch is only a success when both agree, so this reads
League's own login session - GET only, never a write.

Nothing here returns or logs a token: callers get a PUUID or None.
"""
from __future__ import annotations

import warnings
from typing import Any, Callable, Dict, Optional

from utils.logger import Logger

TAG = "LeagueIdentity"
LOGIN_SESSION = "/lol-login/v1/session"


def _default_credentials() -> Dict[str, Any]:
    from utils.client_detector import scan_clients
    return (scan_clients(force=True) or {}).get("league") or {}


def _default_get(url: str, token: str, timeout: float):
    import requests
    import urllib3
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        return requests.get(url, auth=("riot", token), verify=False, timeout=timeout)


def league_login_puuid(
    credentials: Optional[Callable[[], Dict[str, Any]]] = None,
    http_get: Optional[Callable[..., Any]] = None,
    timeout: float = 3.0,
) -> Optional[str]:
    """League's signed-in PUUID once its login has finished, else None.

    None covers "League isn't running", "still logging in" and "unreadable";
    the caller decides how long to wait.
    """
    try:
        creds = (credentials or _default_credentials)() or {}
        port, token = creds.get("port"), creds.get("token")
        if not port or not token:
            return None
        res = (http_get or _default_get)(
            "https://127.0.0.1:{}{}".format(port, LOGIN_SESSION), token, timeout
        )
        if res is None or getattr(res, "status_code", 0) != 200:
            return None
        body = res.json()
        if not isinstance(body, dict):
            return None
        if str(body.get("state") or "").upper() != "SUCCEEDED":
            return None
        puuid = str(body.get("puuid") or "").strip().lower()
        return puuid or None
    except Exception as exc:
        Logger.debug(TAG, "Could not read League's login session", exc=exc)
        return None
