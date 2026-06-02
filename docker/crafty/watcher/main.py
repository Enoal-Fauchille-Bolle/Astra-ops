import socket
import threading
import json
import os
import requests
import urllib3
import time

# Disable SSL warnings to keep logs clean
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
LISTEN_PORT = 25500
TARGET_HOST = "crafty"
TARGET_PORT = 25566
CRAFTY_URL = "https://crafty:8443"

# Strip env vars to avoid invisible whitespace copied by mistake
CRAFTY_TOKEN = os.getenv("CRAFTY_TOKEN", "").strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()


def start_server_api():
    """Send the start command to the Crafty API."""
    print(f"[Watcher] 🚀 Attempting to start server {SERVER_ID}...")

    url = f"{CRAFTY_URL}/api/v2/servers/{SERVER_ID}/action/start_server"
    headers = {"Authorization": f"Bearer {CRAFTY_TOKEN}"}

    try:
        response = requests.post(
            url,
            json={"action": "start_server"},
            headers=headers,
            verify=False,
            timeout=5,
        )

        if response.status_code == 200:
            print("[Watcher] ✅ SUCCESS: Crafty is starting the server!")
        else:
            print(f"[Watcher] ❌ API FAILURE ({response.status_code})")
            print(f"[Watcher] Response: {response.text}")

    except Exception as e:
        print(f"[Watcher] ❌ Critical connection error: {e}")


def read_varint(sock):
    val = 0
    i = 0
    while True:
        try:
            byte = sock.recv(1)
            if not byte:
                return None
            byte = ord(byte)
            val |= (byte & 0x7F) << (i * 7)
            if (byte & 0x80) == 0:
                return val
            i += 1
        except Exception:
            return None


def write_varint(val):
    out = b""
    while True:
        byte = val & 0x7F
        val >>= 7
        if val != 0:
            byte |= 0x80
        out += bytes([byte])
        if val == 0:
            break
    return out


def send_packet(sock, packet_id, data):
    pid = write_varint(packet_id)
    length = write_varint(len(pid) + len(data))
    sock.sendall(length + pid + data)


def make_json_response(text, color="yellow"):
    return json.dumps({"text": text, "color": color})


def handle_client(client_socket):
    try:
        # Check if the server is already online
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.settimeout(0.5)
        is_online = False
        try:
            server_socket.connect((TARGET_HOST, TARGET_PORT))
            is_online = True
        except Exception:
            is_online = False

        # If online: act as a transparent proxy
        if is_online:
            server_socket.settimeout(None)
            import select

            sockets = [client_socket, server_socket]
            while True:
                r, _, _ = select.select(sockets, [], [])
                if client_socket in r:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    server_socket.sendall(data)
                if server_socket in r:
                    data = server_socket.recv(4096)
                    if not data:
                        break
                    client_socket.sendall(data)
            return

        # --- OFFLINE MODE ---

        # 1. Read the Handshake packet
        length = read_varint(client_socket)
        if length is None:
            return
        packet_id = read_varint(client_socket)
        read_varint(client_socket)  # Protocol version
        str_len = read_varint(client_socket)
        if str_len:
            client_socket.recv(str_len)  # Server address
        client_socket.recv(2)  # Port
        next_state = read_varint(client_socket)

        if next_state == 1:  # PING (server list)
            read_varint(client_socket)
            read_varint(client_socket)
            status_json = json.dumps({
                "version": {"name": "§cStandby", "protocol": -1},
                "players": {"max": 1, "online": 0},
                "description": {"text": "§bServer is in standby...\n§eJoin to wake it up!"},
            })
            send_packet(
                client_socket,
                0x00,
                write_varint(len(status_json)) + status_json.encode("utf-8"),
            )

        elif next_state == 2:  # LOGIN (connection attempt)
            # Read the Login Start packet sent by the client before replying,
            # otherwise the client interprets a premature response as a network error
            pkt_len = read_varint(client_socket)
            if pkt_len:
                client_socket.recv(pkt_len)  # Discard payload (player name, etc.)

            # Trigger server start
            start_server_api()

            # Send a clean Disconnect packet (0x00)
            msg = make_json_response(
                "§6Starting up...\n§fPlease wait ~30s and reconnect!", "gold"
            )
            send_packet(
                client_socket,
                0x00,
                write_varint(len(msg)) + msg.encode("utf-8"),
            )

            # Short pause to ensure the packet is flushed before closing
            time.sleep(0.5)

    except Exception:
        pass
    finally:
        client_socket.close()


def main():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", LISTEN_PORT))
    listener.listen(10)
    print(f"[Watcher] Ready — server ID: {SERVER_ID}")
    while True:
        client, addr = listener.accept()
        threading.Thread(target=handle_client, args=(client,)).start()


if __name__ == "__main__":
    main()
