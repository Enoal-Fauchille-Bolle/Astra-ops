import socket
import threading
import json
import os
import requests
import urllib3
import time

# Désactive les warnings SSL (pour ne pas polluer les logs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
LISTEN_PORT = 25500
TARGET_HOST = "crafty"
TARGET_PORT = 25566
CRAFTY_URL = "https://crafty:8443"

# On nettoie les variables (strip) pour éviter les espaces invisibles copiés par erreur
CRAFTY_TOKEN = os.getenv("CRAFTY_TOKEN", "").strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()

def start_server_api():
    """Envoie l'ordre de démarrage."""
    print(f"[Watcher] 🚀 Tentative de démarrage du serveur {SERVER_ID}...")
    
    url = f"{CRAFTY_URL}/api/v2/servers/{SERVER_ID}/action/start_server"
    headers = {"Authorization": f"Bearer {CRAFTY_TOKEN}"}
    
    try:
        # On tente l'action
        response = requests.post(url, json={"action": "start_server"}, headers=headers, verify=False, timeout=5)
        
        if response.status_code == 200:
            print("[Watcher] ✅ SUCCÈS : Crafty démarre le serveur !")
        else:
            # Si ça échoue, on affiche tout pour comprendre
            print(f"[Watcher] ❌ ÉCHEC API ({response.status_code})")
            print(f"[Watcher] Réponse : {response.text}")
            
    except Exception as e:
        print(f"[Watcher] ❌ Erreur critique de connexion : {e}")

# --- (Le reste est le code réseau Minecraft standard) ---

def read_varint(sock):
    val = 0; i = 0
    while True:
        try:
            byte = sock.recv(1)
            if not byte: return None
            byte = ord(byte)
            val |= (byte & 0x7F) << (i * 7)
            if (byte & 0x80) == 0: return val
            i += 1
        except: return None

def write_varint(val):
    out = b""; 
    while True:
        byte = val & 0x7F; val >>= 7
        if val != 0: byte |= 0x80
        out += bytes([byte])
        if val == 0: break
    return out

def send_packet(sock, packet_id, data):
    pid = write_varint(packet_id)
    length = write_varint(len(pid) + len(data))
    sock.sendall(length + pid + data)

def make_json_response(text, color="yellow"):
    return json.dumps({"text": text, "color": color})

def handle_client(client_socket):
    try:
        # Vérification si le serveur est DÉJÀ en ligne
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.settimeout(0.5)
        is_online = False
        try:
            server_socket.connect((TARGET_HOST, TARGET_PORT))
            is_online = True
        except:
            is_online = False

        # Si en ligne : on laisse passer (Proxy)
        if is_online:
            server_socket.settimeout(None)
            import select
            sockets = [client_socket, server_socket]
            while True:
                r, _, _ = select.select(sockets, [], [])
                if client_socket in r:
                    data = client_socket.recv(4096)
                    if not data: break
                    server_socket.sendall(data)
                if server_socket in r:
                    data = server_socket.recv(4096)
                    if not data: break
                    client_socket.sendall(data)
            return

        # --- MODE HORS LIGNE (C'est ici que ça change) ---
        
        # 1. Lecture du Handshake
        length = read_varint(client_socket)
        if length is None: return
        packet_id = read_varint(client_socket)
        read_varint(client_socket) # Version Proto
        str_len = read_varint(client_socket)
        if str_len: client_socket.recv(str_len) # Adresse
        client_socket.recv(2) # Port
        next_state = read_varint(client_socket)

        if next_state == 1: # PING (Liste des serveurs)
            read_varint(client_socket); read_varint(client_socket)
            status_json = json.dumps({
                "version": {"name": "§cEn Veille", "protocol": -1},
                "players": {"max": 1, "online": 0},
                "description": {"text": "§bLe serveur est en veille...\n§eRejoins pour l'allumer !"}
            })
            send_packet(client_socket, 0x00, write_varint(len(status_json)) + status_json.encode('utf-8'))
            
        elif next_state == 2: # LOGIN (Connexion)
            # IMPORTANT : On doit lire le paquet "Login Start" envoyé par le client
            # Sinon, si on répond trop vite sans lire, le client croit à une erreur réseau
            pkt_len = read_varint(client_socket)
            if pkt_len:
                client_socket.recv(pkt_len) # On vide le buffer (nom du joueur, etc.)

            # On lance le serveur
            start_server_api()
            
            # On envoie le Kick propre (Disconnect Packet 0x00)
            msg = make_json_response("§6Démarrage en cours...\n§fPatiente ~30s et reviens !", "gold")
            send_packet(client_socket, 0x00, write_varint(len(msg)) + msg.encode('utf-8'))
            
            # Petite pause pour s'assurer que le paquet est bien parti avant de couper
            time.sleep(0.5)
            
    except Exception as e:
        pass
    finally:
        client_socket.close()

def main():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", LISTEN_PORT))
    listener.listen(10)
    print(f"[Watcher] Prêt pour le serveur ID : {SERVER_ID}")
    while True:
        client, addr = listener.accept()
        threading.Thread(target=handle_client, args=(client,)).start()

if __name__ == "__main__":
    main()
