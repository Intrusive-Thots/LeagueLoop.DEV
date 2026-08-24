"""
One LeagueLoop at a time — and the second launch raises the first.

The 2026-08-24 logs recorded four sessions starting within five minutes
(06:49:07, 06:49:35, 06:50:11, 06:54:26). Four processes shared one `cache/`,
one `config.json` and one `accounts.json`, which produced:

* `[Errno 13] Permission denied: champion_X.png.tmp` — two downloaders
  writing the same temp file
* `[WinError 32] ... used by another process` — one process replacing a
  cached PNG another had open
* a settings write in one window silently overwritten by another
* four automation engines all willing to accept the same Ready Check

Nothing in the app noticed. Double-clicking the shortcut again looked like it
did nothing — the first window was behind the League Client — so it got
double-clicked again.

How it works
------------
`QLocalServer`, not a mutex or a pid file:

* it is cross-platform, so the behaviour is the same everywhere and testable
  on the machine this is developed on;
* it gives the second launch somewhere to *send* something, so "already
  running" can mean **raise the window you already have** rather than a
  dialog saying no;
* a crashed process leaves a stale socket, and `QLocalSocket.connectToServer`
  distinguishes "someone is listening" from "the name is just lying around"
  — a pid file cannot, because pids are recycled.

Usage::

    instance = SingleInstance()
    if not instance.acquire():
        instance.raise_existing()
        return 0
    instance.activated.connect(window.surface_now)

Running two on purpose stays possible: `run_qt.py --allow-multiple` skips
this entirely.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from utils.logger import Logger

TAG = "SingleInstance"

#: The socket name. Per-user on Windows by nature; on Unix it lands in the
#: user's runtime directory. Changing it splits old and new builds into
#: separate "instances", which is the correct behaviour for a rename.
SERVER_NAME = "LeagueLoop.SingleInstance"

#: What the second launch sends. The content does not matter; that a byte
#: arrived at all is the message.
ACTIVATE = b"activate\n"

#: Connecting to a live server on a local socket is sub-millisecond. This is
#: generous enough to absorb a loaded machine and short enough that a launch
#: never appears to hang.
CONNECT_TIMEOUT_MS = 500

#: How long to wait for the second launch's payload once it has connected.
#: It is one short write that has already been sent.
READ_TIMEOUT_MS = 200


class SingleInstance(QObject):
    """Holds the "I am the running LeagueLoop" claim for this process."""

    #: Emitted when another launch asked us to come to the front.
    activated = Signal()

    def __init__(self, name: str = SERVER_NAME, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._name = name
        self._server: Optional[QLocalServer] = None
        self._owner = False

    # ------------------------------------------------------------- claiming
    @property
    def is_owner(self) -> bool:
        """True when this process is the one instance."""
        return self._owner

    def another_is_running(self) -> bool:
        """Is something actually listening on the name right now?

        Distinguishing this from a leftover socket file is the whole reason
        for connecting rather than checking for the name's existence.
        """
        probe = QLocalSocket(self)
        try:
            probe.connectToServer(self._name)
            connected = probe.waitForConnected(CONNECT_TIMEOUT_MS)
            probe.abort()
            return bool(connected)
        finally:
            # Parented and deleted explicitly. A `QLocalSocket` left to
            # Python's garbage collector is destroyed at an arbitrary moment,
            # possibly with events still queued against it — which is a
            # segfault later, in whatever happens to be running then. This is
            # the same lifetime mistake as an unparented signal carrier, and
            # it reproduced reliably: building a window after this function
            # returned crashed the interpreter.
            probe.deleteLater()

    def acquire(self) -> bool:
        """Claim the name. False means another LeagueLoop already has it."""
        if self.another_is_running():
            Logger.info(TAG, "LeagueLoop is already running.")
            return False

        # Nobody answered, so any socket left with this name is debris from a
        # process that crashed. Removing it is safe *because* the probe above
        # failed; removing it unconditionally would evict a live instance.
        QLocalServer.removeServer(self._name)

        server = QLocalServer(self)
        # Belt and braces on Unix, where a socket file can survive a SIGKILL.
        try:
            server.setSocketOptions(QLocalServer.UserAccessOption)
        except Exception as exc:
            Logger.debug(TAG, "Could not set socket options", exc=exc)

        if not server.listen(self._name):
            Logger.warning(
                TAG,
                "Could not claim the single-instance name, so a second copy "
                "cannot be detected: " + server.errorString(),
            )
            # Fail open. Refusing to start because the guard itself broke
            # would be a worse failure than the one it prevents.
            self._owner = True
            return True

        server.newConnection.connect(self._on_connection)
        self._server = server
        self._owner = True
        Logger.debug(TAG, "Single-instance name claimed.")
        return True

    def release(self) -> None:
        """Give up the name. Safe to call more than once."""
        server, self._server = self._server, None
        self._owner = False
        if server is None:
            return
        try:
            server.close()
            server.deleteLater()
        except Exception as exc:
            Logger.debug(TAG, "Could not close the instance server", exc=exc)
        QLocalServer.removeServer(self._name)

    # ------------------------------------------------------------- signalling
    def raise_existing(self) -> bool:
        """Ask the running instance to show itself. True if it heard us.

        This is what turns "the shortcut does nothing" into "the window comes
        forward", which is the behaviour that stops people launching it four
        times.
        """
        socket = QLocalSocket(self)
        try:
            socket.connectToServer(self._name)
            if not socket.waitForConnected(CONNECT_TIMEOUT_MS):
                Logger.debug(TAG, "No running instance answered.")
                return False
            socket.write(ACTIVATE)
            delivered = socket.waitForBytesWritten(CONNECT_TIMEOUT_MS)
            # Wait for the close to complete rather than abandoning a socket
            # mid-teardown; see the note in `another_is_running`.
            socket.disconnectFromServer()
            if socket.state() != QLocalSocket.UnconnectedState:
                socket.waitForDisconnected(CONNECT_TIMEOUT_MS)
            if delivered:
                Logger.info(TAG, "Asked the running LeagueLoop to come forward.")
            return bool(delivered)
        finally:
            socket.deleteLater()

    def _on_connection(self) -> None:
        """Drain the connection here and now, then let it go.

        Read synchronously rather than wiring `readyRead` to a lambda that
        captures the connection. That lambda outlives the connection: when the
        server closes, Qt deletes its children, and the next invocation calls
        through a Python wrapper whose C++ object is gone — a segfault, in
        whatever code happens to be running at the time. It reproduced every
        run once a window was built afterwards.

        The payload is one short write, so a bounded wait costs nothing and
        removes the lifetime question entirely.
        """
        if self._server is None:
            return
        connection = self._server.nextPendingConnection()
        if connection is None:
            return
        payload = b""
        try:
            connection.waitForReadyRead(READ_TIMEOUT_MS)
            payload = bytes(connection.readAll())
        except Exception as exc:
            Logger.debug(TAG, "Could not read the activation message", exc=exc)
        finally:
            try:
                connection.disconnectFromServer()
            except Exception as exc:
                Logger.debug(TAG, "Could not close the connection", exc=exc)
            connection.deleteLater()

        # Only a connection that actually said something is a request. The
        # "is anything listening?" probe connects and immediately aborts
        # without writing, and treating that as an activation made the window
        # jump to the front twice for a single second launch — once for the
        # probe, once for the real message.
        if not payload:
            Logger.debug(TAG, "A probe connected and said nothing; ignoring.")
            return

        Logger.info(TAG, "Another launch asked for the window; surfacing.")
        self.activated.emit()


__all__ = ["ACTIVATE", "SERVER_NAME", "SingleInstance"]
