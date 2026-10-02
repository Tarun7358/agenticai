"""
AURA Network Agent
Scans your local WiFi network for connected devices, monitors bandwidth,
detects unknown/intruder devices, and tracks device history.
"""

import subprocess
import socket
import json
import datetime
import asyncio
import re
from typing import Optional
import psutil
from config import settings
from memory.store import get_db, log_agent_event


def get_mac_vendor(mac: str) -> str:
    """Simple MAC vendor lookup via OUI prefix."""
    OUI_MAP = {
        "00:50:56": "VMware", "00:0c:29": "VMware",
        "dc:a6:32": "Raspberry Pi", "b8:27:eb": "Raspberry Pi",
        "00:17:f2": "Apple", "3c:22:fb": "Apple", "a4:83:e7": "Apple",
        "00:1a:7d": "Intel", "8c:8d:28": "Intel",
        "00:16:3e": "Xen/AWS", "02:42": "Docker",
        "fc:fb:fb": "Synology", "00:11:32": "Synology",
        "18:60:24": "Samsung", "04:4b:ed": "Samsung",
        "40:b0:76": "OnePlus", "e0:b9:ba": "Xiaomi",
    }
    prefix = mac[:8].upper()
    for key, vendor in OUI_MAP.items():
        if prefix.startswith(key.upper()):
            return vendor
    return "Unknown"


def arp_scan() -> list[dict]:
    """Use ARP table to discover devices on local network."""
    devices = []
    try:
        # Windows: arp -a
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.splitlines()
        for line in lines:
            # Parse: 192.168.1.5  dc-a6-32-xx-xx-xx  dynamic
            match = re.search(
                r'(\d+\.\d+\.\d+\.\d+)\s+([\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2})',
                line
            )
            if match:
                ip = match.group(1)
                mac = match.group(2).replace("-", ":").lower()
                if mac == "ff:ff:ff:ff:ff:ff":
                    continue
                # Try reverse DNS
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except Exception:
                    hostname = ""
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "hostname": hostname,
                    "vendor": get_mac_vendor(mac),
                })
    except Exception as e:
        print(f"[Network] ARP scan error: {e}")
    return devices


def get_network_stats() -> dict:
    """Get current network bandwidth stats."""
    net = psutil.net_io_counters()
    return {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "packets_sent": net.packets_sent,
        "packets_recv": net.packets_recv,
        "mb_sent": round(net.bytes_sent / 1024 / 1024, 2),
        "mb_recv": round(net.bytes_recv / 1024 / 1024, 2),
    }


def get_active_interfaces() -> list[dict]:
    """List active network interfaces with their IPs."""
    interfaces = []
    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                stats = psutil.net_if_stats().get(name)
                interfaces.append({
                    "name": name,
                    "ip": addr.address,
                    "netmask": addr.netmask,
                    "is_up": stats.isup if stats else False,
                    "speed_mbps": stats.speed if stats else 0,
                })
    return interfaces


def scan_and_update_db() -> dict:
    """
    Full network scan: discover devices, update DB, flag unknowns.
    Returns scan summary.
    """
    devices = arp_scan()
    now = datetime.datetime.now().isoformat()
    new_devices = []
    conn = get_db()

    for dev in devices:
        existing = conn.execute(
            "SELECT * FROM network_devices WHERE mac_address=?", (dev["mac"],)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE network_devices SET ip_address=?, hostname=?, last_seen=? WHERE mac_address=?",
                (dev["ip"], dev["hostname"], now, dev["mac"])
            )
        else:
            conn.execute(
                """INSERT INTO network_devices
                   (mac_address, ip_address, hostname, vendor, first_seen, last_seen, is_trusted)
                   VALUES (?,?,?,?,?,?,0)""",
                (dev["mac"], dev["ip"], dev["hostname"], dev["vendor"], now, now)
            )
            new_devices.append(dev)

    conn.commit()

    # Get all devices from DB
    all_devices = [dict(r) for r in conn.execute("SELECT * FROM network_devices ORDER BY last_seen DESC").fetchall()]
    unknown = [d for d in all_devices if not d["is_trusted"]]
    conn.close()

    result = {
        "total_devices": len(all_devices),
        "new_devices": new_devices,
        "unknown_count": len(unknown),
        "devices": all_devices,
        "scanned_at": now,
        "network_stats": get_network_stats(),
        "interfaces": get_active_interfaces(),
    }

    log_agent_event("network", "scan_complete", {
        "total": len(all_devices),
        "new": len(new_devices),
        "unknown": len(unknown)
    })

    if new_devices:
        log_agent_event("network", "new_device_alert", {"devices": new_devices}, status="alert")
        print(f"[Network] WARNING: {len(new_devices)} NEW device(s) detected!")

    return result


def get_all_devices() -> list[dict]:
    conn = get_db()
    devices = [dict(r) for r in conn.execute(
        "SELECT * FROM network_devices ORDER BY last_seen DESC"
    ).fetchall()]
    conn.close()
    return devices


def trust_device(mac: str, alias: str = "") -> bool:
    conn = get_db()
    conn.execute(
        "UPDATE network_devices SET is_trusted=1, alias=? WHERE mac_address=?",
        (alias, mac)
    )
    conn.commit()
    changes = conn.total_changes
    conn.close()
    return changes > 0
