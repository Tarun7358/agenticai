"""
AURA LAN Node Sync — Multi-PC / Satellite Synchronization
Enables running JARVIS on multiple laptops/devices on the same Wi-Fi network:
- Auto-UDP Discovery (Zero manual IP configuration needed).
- Remote HUD Pop-Up: Laptop 2 triggers Laptop 1's holographic Arc Reactor HUD instantly.
- Remote Command Execution: Commands spoken on Laptop 2 execute on Laptop 1 (or vice versa).
- 100% Peer-to-Peer over local LAN (Zero cloud data leakage).
"""

import os
import sys
import json
import time
import socket
import ctypes
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any

UDP_DISCOVERY_PORT = 9998
LAN_HTTP_PORT = 9999

def get_local_ip() -> str:
    """Detects local LAN IPv4 address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not send real traffic, used to determine default outbound route
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def bring_hud_to_front():
    """Forces the AURA JARVIS HUD window to restore and focus on Windows."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "AURA JARVIS HUD")
        if hwnd:
            # 9 = SW_RESTORE, 5 = SW_SHOW
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            return True
    except Exception as ex:
        print(f"[LAN Sync] Window focus error: {ex}")
    return False


class JarvisLanHandler(BaseHTTPRequestHandler):
    """HTTP request handler for local network HUD triggers and remote commands."""
    app_ref = None  # Injected reference to JarvisApp instance

    def log_message(self, format, *args):
        # Silence default HTTP server access logs
        return

    def do_GET(self):
        if self.path in ["/status", "/ping"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "status": "online",
                "hostname": socket.gethostname(),
                "ip": get_local_ip(),
                "role": "master",
                "state": getattr(self.app_ref, "state", "idle")
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        if self.path in ["/hud/show", "/wake", "/popup"]:
            # 1. Force HUD window to foreground
            bring_hud_to_front()
            if self.app_ref:
                self.app_ref.show_hud()

            query = body.get("query", "").strip()
            if query and self.app_ref:
                # Execute command on this PC!
                print(f"[LAN Sync] Received remote command from network: '{query}'")
                self.app_ref._process_query(query)
            elif self.app_ref:
                # Trigger listening prompt ("Yes sir?")
                self.app_ref.trigger_listening()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {"status": "ok", "message": "HUD popped up on master PC", "query": query}
            self.wfile.write(json.dumps(resp).encode("utf-8"))

        elif self.path in ["/hud/hide"]:
            if self.app_ref and self.app_ref.window:
                try:
                    self.app_ref.window.hide()
                except Exception:
                    pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "message": "HUD hidden"}')
        else:
            self.send_response(404)
            self.end_headers()


def start_lan_server(app_instance, port=LAN_HTTP_PORT):
    """Starts the background LAN listener to accept remote HUD triggers from other laptops."""
    JarvisLanHandler.app_ref = app_instance
    try:
        server = HTTPServer(("0.0.0.0", port), JarvisLanHandler)
        local_ip = get_local_ip()
        print(f"[*] AURA LAN Node Listener active on http://{local_ip}:{port}")

        def _serve():
            try:
                server.serve_forever()
            except Exception:
                pass

        t = threading.Thread(target=_serve, daemon=True)
        t.start()
        return server
    except Exception as ex:
        print(f"[LAN Sync] Could not start HTTP server on port {port}: {ex}")
        return None


def start_udp_discovery_responder(discovery_port=UDP_DISCOVERY_PORT, http_port=LAN_HTTP_PORT):
    """Listens for 'JARVIS_DISCOVER' broadcast packets from other laptops and replies with IP."""
    def _listen():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", discovery_port))
            local_ip = get_local_ip()

            while True:
                data, addr = sock.recvfrom(1024)
                msg = data.decode("utf-8", errors="ignore").strip()
                if "JARVIS_DISCOVER" in msg:
                    reply = f"JARVIS_MASTER:{local_ip}:{http_port}:{socket.gethostname()}".encode("utf-8")
                    sock.sendto(reply, addr)
        except Exception as ex:
            print(f"[LAN Sync] UDP Discovery responder stopped: {ex}")

    t = threading.Thread(target=_listen, daemon=True)
    t.start()


def discover_master_pc(timeout=1.5, discovery_port=UDP_DISCOVERY_PORT) -> Optional[str]:
    """
    Called by Laptop 2 (Satellite). Broadcasts UDP query to find Laptop 1's IP on the Wi-Fi.
    Returns: 'http://<master-ip>:9999' or None if not found.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)

    try:
        msg = b"JARVIS_DISCOVER_REQUEST"
        sock.sendto(msg, ("<broadcast>", discovery_port))
        sock.sendto(msg, ("255.255.255.255", discovery_port))

        start = time.time()
        while time.time() - start < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                resp = data.decode("utf-8", errors="ignore")
                if resp.startswith("JARVIS_MASTER:"):
                    parts = resp.split(":")
                    master_ip = parts[1]
                    master_port = parts[2] if len(parts) > 2 else "9999"
                    return f"http://{master_ip}:{master_port}"
            except socket.timeout:
                break
    except Exception:
        pass
    finally:
        sock.close()
    return None


def trigger_remote_pc_hud(master_url: Optional[str] = None, query: str = "") -> Dict[str, Any]:
    """
    Pops up the HUD on the primary PC and optionally runs a command there.
    Auto-discovers the primary PC if master_url is not provided.
    """
    url = master_url or os.environ.get("JARVIS_MASTER_URL") or discover_master_pc()
    if not url:
        return {"status": "error", "message": "Primary PC not detected on local Wi-Fi"}

    endpoint = f"{url.rstrip('/')}/hud/show"
    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return {"status": "ok", "url": url, "data": res_data}
    except Exception as ex:
        return {"status": "error", "message": f"Connection failed: {ex}", "url": url}
