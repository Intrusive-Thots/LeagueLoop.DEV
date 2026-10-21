"""
Account switching preflight.

Verifies everything the new switch sequence depends on WITHOUT signing anyone
in or out, so you can confirm the plumbing before risking your session or a
Riot rate limit.

    python tools/check_accounts.py                 # read-only preflight
    python tools/check_accounts.py --json          # machine-readable JSON output
    python tools/check_accounts.py --round-trip    # sign out + back in (live)
    python tools/check_accounts.py --switch 1      # actually switch (destructive)
    python tools/check_accounts.py --sign-out      # actually sign out

Preflight touches only read-only endpoints: process scan, connect, session
state and userinfo. It never calls sign_in or sign_out.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Force UTF-8 encoding on stdout and stderr for Windows compatibility
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OK = "  OK   "
WARN = "  WARN "
FAIL = "  FAIL "
INFO = "       "


def line(mark: str, text: str) -> None:
    print(mark + text, flush=True)


def run_account_preflight(manager: Optional[Any] = None) -> Dict[str, Any]:
    """Runs a non-destructive read-only account switching preflight inspection.

    Returns structured dictionary with connection state, account counts, and problem tally.
    """
    from services.account_manager import AccountManager
    from services.accounts import RiotSession

    if manager is None:
        manager = AccountManager()

    problems = 0
    switcher = getattr(manager, "_switcher", None)
    switcher_wired = switcher is not None
    switcher_phase = (
        getattr(getattr(switcher, "phase", None), "value", "unknown")
        if switcher_wired
        else "unavailable"
    )
    switcher_busy = getattr(switcher, "busy", False) if switcher_wired else False
    if not switcher_wired:
        problems += 1

    session = RiotSession(getattr(manager, "riot_client", None))
    running = session.client_running()
    if not running:
        problems += 1

    connected = session.connect()
    if running and not connected:
        problems += 1

    signed_in = False
    current = ""
    if connected:
        signed_in = session.is_signed_in()
        if signed_in:
            current = session.current_login_name() or ""

    raw_accounts = manager.get_accounts() or []
    accounts_report: List[Dict[str, Any]] = []
    default_idx = manager.get_default_account_index()

    for i, acct in enumerate(raw_accounts):
        label = acct.get("label") or acct.get("username") or "?"
        username = acct.get("username") or ""
        has_pw = False
        try:
            has_pw = bool(manager.get_password(i))
        except Exception:
            has_pw = False

        is_active = bool(username and current and username.lower() == current.lower())
        is_default = i == default_idx
        if not username or not has_pw:
            problems += 1

        accounts_report.append({
            "index": i,
            "label": label,
            "username": username,
            "has_password": has_pw,
            "is_active": is_active,
            "is_default": is_default,
        })

    return {
        "status": "HEALTHY" if problems == 0 else "ATTENTION_REQUIRED",
        "problems_count": problems,
        "account_manager_wired": True,
        "switcher_wired": switcher_wired,
        "switcher_phase": switcher_phase,
        "switcher_busy": switcher_busy,
        "riot_client_running": running,
        "api_reachable": connected,
        "signed_in": signed_in,
        "current_user": current,
        "accounts_count": len(raw_accounts),
        "accounts": accounts_report,
    }


def preflight(as_json: bool = False, manager: Optional[Any] = None) -> int:
    from services.account_manager import AccountManager
    from services.accounts import RiotSession

    if as_json:
        res = run_account_preflight(manager=manager)
        print(json.dumps(res, indent=2))
        return 0 if res["problems_count"] == 0 else 1

    problems = 0

    print("=" * 62)
    print(" LeagueLoop - account switching preflight (read-only)")
    print("=" * 62)
    print()

    # --- 1. manager + switcher -------------------------------------------
    print("[1] Account manager")
    if manager is None:
        manager = AccountManager()
    line(OK, "AccountManager constructed")

    switcher = getattr(manager, "_switcher", None)
    if switcher is None:
        line(FAIL, "AccountSwitcher was not built - switching is unavailable")
        problems += 1
    else:
        line(OK, "AccountSwitcher wired ({})".format(type(switcher).__name__))
        line(INFO, "phase: {}  busy: {}".format(switcher.phase.value, switcher.busy))
    print()

    # --- 2. Riot Client ---------------------------------------------------
    print("[2] Riot Client")
    session = RiotSession(manager.riot_client)

    running = session.client_running()
    line(OK if running else WARN,
         "Riot Client process: {}".format("running" if running else "not running"))
    if not running:
        line(INFO, "Start the Riot Client to test the rest.")
        problems += 1

    connected = session.connect()
    line(OK if connected else (WARN if not running else FAIL),
         "Local API reachable: {}".format(connected))
    if running and not connected:
        problems += 1

    if connected:
        signed_in = session.is_signed_in()
        line(OK, "Signed in: {}".format(signed_in))
        if signed_in:
            who = session.current_login_name()
            line(OK if who else WARN,
                 "Current login username: {}".format(who or "(could not read)"))
    print()

    # --- 3. stored accounts -----------------------------------------------
    print("[3] Stored accounts")
    accounts = manager.get_accounts() or []
    if not accounts:
        line(WARN, "No stored accounts")
    else:
        line(OK, "{} account(s)".format(len(accounts)))

    # Distinguish "nobody is signed in" from "we could not look". Reporting
    # an unknown state as signed-out is how a preflight ends up promising a
    # switch that will actually hit a live session.
    current = session.current_login_name() if connected else ""
    known = bool(connected)
    for i, acct in enumerate(accounts):
        label = acct.get("label") or acct.get("username") or "?"
        username = acct.get("username") or ""
        has_pw = False
        try:
            has_pw = bool(manager.get_password(i))
        except Exception:
            has_pw = False

        marks = []
        if username and current and username.lower() == current:
            marks.append("ACTIVE NOW")
        if i == manager.get_default_account_index():
            marks.append("default")

        line(OK if (username and has_pw) else WARN,
             "[{}] {:<18} user={:<16} password={} {}".format(
                 i, label[:18], (username or "(none)")[:16],
                 "saved" if has_pw else "MISSING",
                 ("- " + ", ".join(marks)) if marks else ""))
        if not username or not has_pw:
            problems += 1
    print()

    # --- 4. what a switch would do ----------------------------------------
    print("[4] What a switch would do (not doing it)")
    if not accounts:
        line(INFO, "Nothing to switch to.")
    else:
        for i, acct in enumerate(accounts):
            label = acct.get("label") or acct.get("username") or "?"
            username = (acct.get("username") or "").lower()
            if not username:
                line(WARN, "[{}] {} - cannot switch, no username".format(i, label))
                continue
            if not known:
                line(INFO, "[{}] {} - unknown; the client could not be read, "
                           "so I cannot say whether a sign-out is needed"
                           .format(i, label))
            elif current and username == current:
                line(INFO, "[{}] {} - already active, would be a no-op".format(i, label))
            elif current:
                line(INFO, "[{}] {} - would close League, sign out {}, "
                           "then sign in".format(i, label, current))
            else:
                line(INFO, "[{}] {} - would sign in directly "
                           "(nobody signed in)".format(i, label))
    print()

    # --- 5. the actual next step ------------------------------------------
    print("[5] How to test from here")
    others = [
        i for i, a in enumerate(accounts)
        if (a.get("username") or "").lower() and (a.get("username") or "").lower() != current
    ]
    if not accounts:
        line(INFO, "Add an account first - there is nothing to switch to.")
    elif not known:
        line(INFO, "Start the Riot Client, then run this again.")
    elif others:
        i = others[0]
        label = accounts[i].get("label") or accounts[i].get("username")
        line(INFO, "--switch {}   switches into {}".format(i, label))
    else:
        line(INFO, "Only one usable account, and it is the active one, so")
        line(INFO, "there is no *other* account to switch into.")
        line(INFO, "--round-trip   signs out and back in to the same account,")
        line(INFO, "               which exercises the identical sequence.")
    print()

    print("=" * 62)
    if problems:
        print(" {} thing(s) need attention above.".format(problems))
    else:
        print(" Preflight clean - a real switch should work.")
    print("=" * 62)
    return 0


def do_switch(index: int) -> int:
    from services.account_manager import AccountManager
    from services.accounts import (
        EVENT_SWITCH_PROGRESS,
    )
    from core.events import EventBus

    print("=" * 62)
    print(" LIVE account switch to index {} - this WILL sign you out".format(index))
    print("=" * 62)
    print()

    def on_progress(progress=None, *_a, **_kw):
        phase = getattr(getattr(progress, "phase", None), "value", "?")
        print("  [{}] {}".format(phase, getattr(progress, "message", "")), flush=True)

    EventBus.on(EVENT_SWITCH_PROGRESS, on_progress)

    manager = AccountManager()
    result = manager.switch_to(index, launch_league=False)

    print()
    print("  outcome : {}".format(result.outcome.value))
    print("  phase   : {}".format(result.phase.value))
    print("  message : {}".format(result.message))
    if result.detail:
        print("  detail  : {}".format(result.detail))
    print("  ok      : {}   retryable: {}".format(result.ok, result.retryable))
    return 0 if result.ok else 1


def do_sign_out() -> int:
    from services.account_manager import AccountManager
    from services.accounts import EVENT_SWITCH_PROGRESS
    from core.events import EventBus

    print("LIVE sign out - this WILL close League and sign you out.")
    print()

    def on_progress(progress=None, *_a, **_kw):
        print("  [{}] {}".format(
            getattr(getattr(progress, "phase", None), "value", "?"),
            getattr(progress, "message", "")), flush=True)

    EventBus.on(EVENT_SWITCH_PROGRESS, on_progress)

    manager = AccountManager()
    result = manager._switcher.sign_out()
    print()
    print("  outcome : {}".format(result.outcome.value))
    print("  message : {}".format(result.message))
    return 0 if result.ok else 1


def do_round_trip() -> int:
    """
    Sign out, verify, then sign back into the same account.

    With a single stored account there is no *other* account to switch into,
    but a switch is exactly this sequence with a different index at the end.
    Running it against the account that is already signed in exercises every
    phase - close League, sign out, wait for signed-out, authenticate,
    verify - without needing a second set of credentials.
    """
    from services.account_manager import AccountManager
    from services.accounts import EVENT_SWITCH_PROGRESS
    from core.events import EventBus

    print("=" * 62)
    print(" LIVE round trip - signs you out, then straight back in")
    print("=" * 62)
    print()

    def on_progress(progress=None, *_a, **_kw):
        print("  [{}] {}".format(
            getattr(getattr(progress, "phase", None), "value", "?"),
            getattr(progress, "message", "")), flush=True)

    handle = EventBus.on(EVENT_SWITCH_PROGRESS, on_progress)

    manager = AccountManager()
    switcher = manager._switcher
    if switcher is None:
        print("  AccountSwitcher unavailable - cannot run.")
        return 1

    # Which account is signed in right now, by username rather than by the
    # persisted index - the index is what we are trying to validate.
    from services.accounts import RiotSession
    session = RiotSession(manager.riot_client)
    session.connect()
    current = session.current_login_name()

    target = -1
    for i, acct in enumerate(manager.get_accounts()):
        if (acct.get("username") or "").lower() == (current or ""):
            target = i
            break
    if target < 0:
        target = manager.get_default_account_index()
    if target < 0:
        target = 0

    label = "?"
    accounts = manager.get_accounts()
    if 0 <= target < len(accounts):
        label = accounts[target].get("label") or accounts[target].get("username")
    print("  Target: index {} ({})".format(target, label))
    print()

    print("  --- step 1: sign out ---")
    out = switcher.sign_out()
    print("  outcome : {}".format(out.outcome.value))
    print("  message : {}".format(out.message))
    if not out.ok:
        print()
        print("  Stopping - sign-out did not succeed, so signing back in")
        print("  would type into a client that is still signed in.")
        return 1

    print()
    print("  --- step 2: sign back in ---")
    back = switcher.switch_to(target, launch_league=False)
    print("  outcome : {}".format(back.outcome.value))
    print("  phase   : {}".format(back.phase.value))
    print("  message : {}".format(back.message))
    if back.detail:
        print("  detail  : {}".format(back.detail))

    print()
    print("  --- step 3: verify ---")
    session.connect()
    who = session.current_login_name()
    expected = (accounts[target].get("username") or "").lower() if accounts else ""
    match = bool(who) and who == expected
    print("  client reports : {}".format(who or "(nobody)"))
    print("  expected       : {}".format(expected or "(unknown)"))
    print("  MATCH" if match else "  MISMATCH - the client is not on the expected account")

    try:
        handle.dispose()
    except Exception:
        pass

    # 2FA is not a failure of the sequence - the sequence did its job and
    # handed off to you. Calling it FAILED would send you bug-hunting for
    # something that is working as designed.
    from services.accounts import SwitchOutcome
    print()
    print("=" * 62)
    if back.outcome is SwitchOutcome.NEEDS_2FA:
        print(" Round trip reached 2FA - sign-out and authentication both")
        print(" worked. Finish the code in the Riot Client; that part is")
        print(" not something LeagueLoop can or should automate.")
        rc = 0
    elif back.ok and match:
        print(" Round trip PASSED")
        rc = 0
    else:
        print(" Round trip FAILED")
        rc = 1
    print("=" * 62)
    return rc


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switch", type=int, metavar="INDEX",
                        help="Actually switch to this account index (destructive)")
    parser.add_argument("--sign-out", action="store_true",
                        help="Actually sign out (destructive)")
    parser.add_argument("--round-trip", action="store_true",
                        help="Sign out and back into the same account (live)")
    parser.add_argument("--json", action="store_true",
                        help="Output preflight report as structured JSON")
    args = parser.parse_args(argv)

    if args.switch is not None:
        return do_switch(args.switch)
    if args.sign_out:
        return do_sign_out()
    if args.round_trip:
        return do_round_trip()
    return preflight(as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
