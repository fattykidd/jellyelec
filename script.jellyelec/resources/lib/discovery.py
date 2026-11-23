"""Find Jellyfin servers on the local network.

Jellyfin servers listen on UDP port 7359 and answer a broadcast
"who is JellyfinServer?" message with their name and address.
"""

import json
import socket
import time

DISCOVERY_PORT = 7359
DISCOVERY_MESSAGE = b"who is JellyfinServer?"


def discover_servers(timeout=2.0):
    """Broadcast a discovery request and return the servers that answer.

    Each server is a dict with "id", "name" and "address".
    Returns an empty list if nothing answers or the network is unavailable.
    """
    servers = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.5)
        sock.sendto(DISCOVERY_MESSAGE, ("255.255.255.255", DISCOVERY_PORT))

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, _sender = sock.recvfrom(4096)
            except socket.timeout:
                continue
            server = _parse_reply(data)
            if server:
                servers[server["id"]] = server
    except OSError:
        pass
    finally:
        sock.close()

    return sorted(servers.values(), key=lambda server: server["name"].lower())


def _parse_reply(data):
    try:
        reply = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None

    server_id = reply.get("Id")
    address = reply.get("Address")
    if not server_id or not address:
        return None
    return {"id": server_id, "name": reply.get("Name") or address, "address": address}
