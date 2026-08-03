"""Reproduce the crafty-server-watcher port-steal race.

Drives the real _handle_login() path: a client sends a Login Start, the watcher
releases the port and sleeps 5s before calling Crafty. A poll tick lands inside
that window (exactly what idle_monitor does every 30s). We then check whether
the port is actually free for the MC server that is about to boot.

Exit 0 = port free (fixed), exit 1 = port stolen (bug present).
"""

import asyncio
import socket
import sys

from crafty_server_watcher.config import CooldownConfig, ServerConfig
from crafty_server_watcher.mc_protocol import build_packet, write_utf, write_varint
from crafty_server_watcher.proxy_listener import ProxyManager
from crafty_server_watcher.server_state import ServerStateMachine, State

PORT = 25500


class FakeApi:
    """Stands in for CraftyApiClient; records the start call."""

    def __init__(self):
        self.started = []

    async def start_server(self, server_id):
        self.started.append(server_id)


def port_is_free() -> bool:
    """True if a fresh listener can bind PORT — i.e. the MC server could boot."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Netty (and every real server) sets SO_REUSEADDR, so TIME_WAIT sockets
    # left by the kicked player must not count as "port taken" — only a live
    # listener does.
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("0.0.0.0", PORT))
        return True
    except OSError:
        return False
    finally:
        probe.close()


async def main() -> int:
    cfg = ServerConfig(name="server-1", crafty_server_id="uuid-1", listen_port=PORT)
    initial = State[sys.argv[1]] if len(sys.argv) > 1 else State.STOPPED
    sm = ServerStateMachine(cfg=cfg, cooldowns=CooldownConfig())
    sm.transition(initial)

    api = FakeApi()
    pm = ProxyManager({"server-1": sm}, api)

    await pm.ensure_listeners()
    assert not port_is_free(), "setup failed: proxy should hold the port while STOPPED"

    # A player connects: handshake (next_state=2) then Login Start.
    reader, writer = await asyncio.open_connection("127.0.0.1", PORT)
    handshake = write_varint(770) + write_utf("mc.example.org") + PORT.to_bytes(2, "big") + write_varint(2)
    writer.write(build_packet(0x00, handshake))
    writer.write(build_packet(0x00, write_utf("TestPlayer") + b"\x00" * 16))
    await writer.drain()

    # Let _handle_login get into its 5s sleep, then fire the poll tick.
    await asyncio.sleep(1)
    await pm.ensure_listeners()

    free_during_window = port_is_free()
    print(f"state during start window : {sm.state.value}")
    print(f"port {PORT} free for MC    : {free_during_window}")

    # Let the start sequence finish so we can check the API was still called.
    await asyncio.sleep(5)
    print(f"start_server called       : {api.started}")

    writer.close()
    await pm.stop_all()

    if not free_during_window:
        print("\nFAIL: the proxy re-bound the port — MC would die with 'Address already in use'")
        return 1
    if not api.started:
        print("\nFAIL: the server start was never requested")
        return 1
    print("\nOK: port stayed free through the start window and Crafty was asked to start")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
