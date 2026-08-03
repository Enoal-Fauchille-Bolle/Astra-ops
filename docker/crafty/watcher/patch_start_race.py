"""Patch the upstream Crafty Server Watcher at image build time.

Fixes a race condition where the proxy listener re-binds the Minecraft port
while a server start is in flight, so the real MC server dies with
"FAILED TO BIND TO PORT — Address already in use". See README.md.

Each replacement is anchored on the exact upstream source. If upstream changes
any of these blocks the build fails loudly instead of silently dropping their
changes — that is the signal to re-check whether this fork is still needed.
"""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path

PKG = Path("/app/crafty_server_watcher")

# (file, old, new) — `old` must appear exactly once.
REPLACEMENTS: list[tuple[str, str, str]] = [
    # 1) Mark the server as STARTING *before* the 5s sleep. ensure_listeners()
    #    runs concurrently every poll interval; while the state was still
    #    STOPPED it cleared the lockout and re-bound the port inside this
    #    window, stealing the port from the MC server about to boot.
    (
        "proxy_listener.py",
        """            # Lock out this server from ensure_listeners re-binding.
            self._start_lockout.add(name)

            # Give the OS a moment to fully release the socket.
            await asyncio.sleep(5)
""",
        """            # Lock out this server from ensure_listeners re-binding.
            self._start_lockout.add(name)

            # Transition BEFORE sleeping: a concurrent ensure_listeners() poll
            # landing in the window below would otherwise see state == STOPPED,
            # clear the lockout and re-bind the port under the MC server.
            sm.transition(State.STARTING)

            # Give the OS a moment to fully release the socket.
            await asyncio.sleep(5)
""",
    ),
    # 2) The transition moved above; drop the now-redundant one.
    (
        "proxy_listener.py",
        """                await self._api.start_server(sm.cfg.crafty_server_id)
                sm.transition(State.STARTING)
""",
        """                await self._api.start_server(sm.cfg.crafty_server_id)
""",
    ),
    # 3) Roll the optimistic transition back if the start call fails.
    (
        "proxy_listener.py",
        """                log.exception(f"Failed to start server '{name}' via Crafty API")
                # Clear lockout and re-bind the proxy so players can still see the MOTD.
                self._start_lockout.discard(name)
""",
        """                log.exception(f"Failed to start server '{name}' via Crafty API")
                # Roll back the optimistic transition, clear the lockout and
                # re-bind the proxy so players can still see the MOTD.
                sm.transition(State.STOPPED)
                self._start_lockout.discard(name)
""",
    ),
    # 4) Allow CRASHED -> STARTING. _handle_login() starts servers from both
    #    STOPPED and CRASHED, but the graph rejected the CRASHED edge, so the
    #    transition in (1) would be ignored and the race would come right back
    #    for a server that had just crashed.
    (
        "server_state.py",
        "    State.CRASHED: {State.STOPPED, State.ONLINE},\n",
        "    State.CRASHED: {State.STOPPED, State.ONLINE, State.STARTING},\n",
    ),
]


def main() -> int:
    for filename, old, new in REPLACEMENTS:
        path = PKG / filename
        source = path.read_text(encoding="utf-8")

        occurrences = source.count(old)
        if occurrences != 1:
            print(
                f"ERROR: expected exactly 1 match in {path}, found {occurrences}.\n"
                "Upstream has changed — re-check the patch against the new source.\n"
                f"--- anchor ---\n{old}",
                file=sys.stderr,
            )
            return 1

        path.write_text(source.replace(old, new), encoding="utf-8")
        print(f"patched {path}")

    for filename in {filename for filename, _, _ in REPLACEMENTS}:
        py_compile.compile(str(PKG / filename), doraise=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
