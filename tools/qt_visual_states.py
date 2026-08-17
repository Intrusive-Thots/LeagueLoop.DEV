"""
Render the Qt shell across representative states (UI/UX Master Plan §70).

Produces the reference screenshots the plan asks for, without touching the
League Client: the window is built with `with_services=False` and driven by
synthetic `ApplicationState` snapshots pushed through `ShellViewModel`.

Usage
-----
    python tools/qt_visual_states.py [--out DIR] [--size WxH]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "src")
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.state import (  # noqa: E402
    ApplicationState,
    AutomationState,
    ClientState,
    ConnectionStateEnum,
    GameflowPhase,
    QueueState,
)


def settle(app, window, rounds: int = 5) -> None:
    """
    Let pending layout work finish before grabbing a frame.

    Pushing a new state marks layouts dirty; a single processEvents() is not
    always enough for widgets to be resized to their new sizeHint, which
    produces references with text clipped mid-word ("In que"). Flushing
    posted events and explicitly activating the top-level layout makes the
    capture deterministic.
    """
    for _ in range(rounds):
        app.sendPostedEvents()
        app.processEvents()
    layout = window.layout()
    if layout is not None:
        layout.activate()
    app.processEvents()


def _states():
    """(name, ApplicationState) pairs covering the states that must look right."""
    return [
        (
            "disconnected",
            ApplicationState(
                client=ClientState(
                    connected=False,
                    connection_state=ConnectionStateEnum.DISCONNECTED,
                    phase=GameflowPhase.NONE.value,
                ),
                automation=AutomationState(running=False),
            ),
        ),
        (
            "reconnecting",
            ApplicationState(
                client=ClientState(
                    connected=False,
                    connection_state=ConnectionStateEnum.RECONNECTING,
                    phase=GameflowPhase.NONE.value,
                ),
                automation=AutomationState(running=True, paused=True),
            ),
        ),
        (
            "lobby",
            ApplicationState(
                client=ClientState(
                    connected=True,
                    connection_state=ConnectionStateEnum.CONNECTED,
                    phase=GameflowPhase.LOBBY.value,
                    summoner_name="Malcolm",
                ),
                queue=QueueState(queue_id=420, queue_name="Ranked Solo"),
                automation=AutomationState(running=True, auto_accept=True),
            ),
        ),
        (
            "matchmaking",
            ApplicationState(
                client=ClientState(
                    connected=True,
                    connection_state=ConnectionStateEnum.CONNECTED,
                    phase=GameflowPhase.MATCHMAKING.value,
                    summoner_name="Malcolm",
                ),
                queue=QueueState(queue_id=420, queue_name="Ranked Solo", is_searching=True),
                automation=AutomationState(
                    running=True, auto_accept=True, active_action="Waiting for match"
                ),
            ),
        ),
        (
            "champ_select",
            ApplicationState(
                client=ClientState(
                    connected=True,
                    connection_state=ConnectionStateEnum.CONNECTED,
                    phase=GameflowPhase.CHAMP_SELECT.value,
                    summoner_name="Malcolm",
                ),
                queue=QueueState(queue_id=420, queue_name="Ranked Solo"),
                automation=AutomationState(
                    running=True, auto_accept=True, auto_lock=True,
                    active_action="Select Jinx",
                ),
            ),
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="src/ui/testing/screenshots")
    parser.add_argument("--size", default="980x660")
    args = parser.parse_args()

    try:
        width, height = (int(v) for v in args.size.lower().split("x"))
    except ValueError:
        print(f"Invalid --size {args.size!r}; expected WxH", file=sys.stderr)
        return 2

    os.makedirs(args.out, exist_ok=True)

    from ui.qt.app.application import build

    app, window, _ = build(with_services=False)
    window.resize(width, height)
    window.show()

    written = []
    for name, state in _states():
        window.view_model.push_state(state)
        settle(app, window)
        path = os.path.join(args.out, f"shell_{name}.png")
        window.grab().save(path)
        written.append(path)
        print(f"  {name:<14} -> {path}")

    print(f"\n{len(written)} reference screenshots written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
