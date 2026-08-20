"""
Account switching preflight.

Verifies everything the new switch sequence depends on WITHOUT signing anyone
in or out, so you can confirm the plumbing before risking your session or a
Riot rate limit.

    python tools/check_accounts.py                 # read-only preflight
    python tools/check_accounts.py --switch 1      # actually switch (destructive)
    python tools/check_accounts.py --sign-out      # actually sign out

Preflight touches only read-only endpoints: process scan, connect, session
state and userinfo. It never calls sign_in or sign_out.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "src")
)

OK = "  OK   "
WARN = "  WARN "
FAIL = "  FAIL "
INFO = "       "


def line(mark: str, text: str) -> None:
    print(mark + text, flush=True)


def preflight() -> int:
    from services.account_manager import AccountManager
    from services.accounts import RiotSession

    problems = 0

    print("=" * 62)
    print(" LeagueLoop - account switching preflight (read-only)")
    print("=" * 62)
    print()

    # --- 1. manager + switcher -------------------------------------------
    print("[1] Account manager")
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

    current = session.current_login_name() if connected else ""
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
            if current and username == current:
                line(INFO, "[{}] {} - already active, would be a no-op".format(i, label))
            elif current:
                line(INFO, "[{}] {} - would close League, sign out {}, "
                           "then sign in".format(i, label, current))
            else:
                line(INFO, "[{}] {} - would sign in directly "
                           "(nobody signed in)".format(i, label))
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
        EVENT_SWITCH_FINISHED,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switch", type=int, metavar="INDEX",
                        help="Actually switch to this account index (destructive)")
    parser.add_argument("--sign-out", action="store_true",
                        help="Actually sign out (destructive)")
    args = parser.parse_args()

    if args.switch is not None:
        return do_switch(args.switch)
    if args.sign_out:
        return do_sign_out()
    return preflight()


if __name__ == "__main__":
    raise SystemExit(main())
