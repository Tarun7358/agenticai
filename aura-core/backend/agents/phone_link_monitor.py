"""
Phone Link Monitor for AURA — Laptop 2 Service
================================================
Watches Windows Phone Link notifications in real-time.
When a call comes in (missed/incoming), it pushes an event
to the AURA backend so Jarvis can announce it on System 1.

Works with iPhone via Phone Link Bluetooth pairing.
Runs as a background daemon on Laptop 2.
"""

import os
import sqlite3
import time
import threading
import json
import requests
import datetime
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

# ─── CONFIG ───────────────────────────────────────────
AURA_BACKEND_URL = "http://127.0.0.1:8000"          # Local backend
SYSTEM1_URL      = "http://192.168.0.7:8000"       # System 1 (your main PC)
POLL_INTERVAL    = 3                                  # seconds between DB checks
WINDOWS_NOTIF_DB = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db"
)
PHONE_LINK_DB = os.path.expandvars(
    r"%LOCALAPPDATA%\Packages\Microsoft.YourPhone_8wekyb3d8bbwe\LocalState\phone.db"
)

# Track already-seen notification IDs so we don't repeat
_seen_notification_ids: set = set()
_last_call_check: str = ""

# ─── NOTIFICATION WATCHER ─────────────────────────────

def _parse_call_from_payload(payload: str) -> Optional[Dict[str, Any]]:
    """Extract caller name and call type from notification XML payload."""
    try:
        root = ET.fromstring(payload)
        texts = [el.get("content", "") for el in root.iter("text")]
        full_text = " | ".join(t for t in texts if t)

        caller = "Unknown"
        call_type = "incoming"

        # Detect missed call
        if "missed" in full_text.lower():
            call_type = "missed"
        elif "calling" in full_text.lower() or "incoming" in full_text.lower():
            call_type = "incoming"

        # Try to extract a name/number
        for t in texts:
            if t and not any(kw in t.lower() for kw in ["missed", "call", "phone", "link"]):
                caller = t.strip()
                break

        # Fallback: extract phone number pattern
        if caller == "Unknown":
            match = re.search(r'[\+\d][\d\s\-\(\)]{7,}', full_text)
            if match:
                caller = match.group().strip()

        return {"caller": caller, "type": call_type, "raw": full_text[:120]}
    except Exception:
        return None


def read_windows_notifications() -> List[Dict[str, Any]]:
    """
    Read the Windows notification SQLite DB for Phone Link call events.
    Read-only and safe — never modifies the DB.
    """
    if not os.path.exists(WINDOWS_NOTIF_DB):
        return []

    results = []
    try:
        con = sqlite3.connect(f"file:{WINDOWS_NOTIF_DB}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute("""
            SELECT n.RecordId, n.Type, n.Payload, n.ArrivalTime, h.PrimaryId
            FROM Notification n
            LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
            WHERE (
                h.PrimaryId LIKE '%YourPhone%'
                OR h.PrimaryId LIKE '%PhoneLink%'
                OR h.PrimaryId LIKE '%phone%'
            )
            ORDER BY n.ArrivalTime DESC
            LIMIT 20
        """)
        for row in cur.fetchall():
            record_id, ntype, payload, arrival, app = row
            if record_id in _seen_notification_ids:
                continue
            payload_str = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload or "")
            parsed = _parse_call_from_payload(payload_str)
            if parsed:
                results.append({
                    "id": record_id,
                    "app": app,
                    "time": arrival,
                    **parsed
                })
        con.close()
    except Exception as e:
        pass  # DB may be locked; retry next cycle

    return results


def read_phone_link_calls() -> List[Dict[str, Any]]:
    """
    Read call logs directly from Phone Link's local phone.db if available.
    This gives richer data (contact names, duration, number).
    """
    if not os.path.exists(PHONE_LINK_DB):
        return []

    results = []
    try:
        con = sqlite3.connect(f"file:{PHONE_LINK_DB}?mode=ro", uri=True)
        cur = con.cursor()

        # Try common table names used by Phone Link
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        call_tables = [t for t in tables if "call" in t.lower()]

        for table in call_tables:
            try:
                cur.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 10")
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    row_dict = dict(zip(cols, row))
                    results.append(row_dict)
            except Exception:
                continue

        con.close()
    except Exception:
        pass

    return results


# ─── EVENT PUSHER ─────────────────────────────────────

def push_call_event(event: Dict[str, Any]):
    """Push a call event to AURA backend and optionally to System 1."""
    caller = event.get("caller", "Unknown")
    call_type = event.get("type", "incoming")

    now = datetime.datetime.now().strftime("%I:%M %p")

    payload = {
        "caller": caller,
        "type": call_type,
        "time": now,
        "source": "phone_link"
    }

    # Push to local backend (Laptop 2)
    try:
        requests.post(f"{AURA_BACKEND_URL}/phone/call-event", json=payload, timeout=3)
    except Exception:
        pass

    # Also push to System 1 so Jarvis can announce
    try:
        requests.post(f"{SYSTEM1_URL}/phone/call-event", json=payload, timeout=3)
    except Exception:
        pass

    print(f"[PHONE LINK] 📞 {call_type.upper()} call from {caller} at {now}")


# ─── MONITOR LOOP ─────────────────────────────────────

def monitor_loop():
    """Main background loop — polls notifications every few seconds."""
    print("[PHONE LINK MONITOR] 🟢 Started — watching for calls from your iPhone...")
    print(f"[PHONE LINK MONITOR] DB: {WINDOWS_NOTIF_DB}")

    while True:
        try:
            notifs = read_windows_notifications()
            for notif in notifs:
                nid = notif.get("id")
                if nid and nid not in _seen_notification_ids:
                    _seen_notification_ids.add(nid)
                    push_call_event(notif)

        except Exception as e:
            print(f"[PHONE LINK MONITOR] Error: {e}")

        time.sleep(POLL_INTERVAL)


def start_monitor_background():
    """Start the Phone Link monitor in a background thread."""
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    return t


# ─── STANDALONE RUN ───────────────────────────────────

if __name__ == "__main__":
    # Test mode: print what's currently in the DB
    print("=" * 60)
    print("AURA Phone Link Monitor — Test Mode")
    print("=" * 60)

    print("\n[1] Checking Windows Notification DB...")
    notifs = read_windows_notifications()
    if notifs:
        for n in notifs:
            print(f"  • {n.get('type','?').upper()} from {n.get('caller','?')} | {n.get('raw','')[:80]}")
    else:
        print("  No Phone Link call notifications found yet.")
        print("  Make sure Phone Link is running and paired with your iPhone.")

    print("\n[2] Checking Phone Link call DB...")
    calls = read_phone_link_calls()
    if calls:
        for c in calls[:5]:
            print(f"  • {c}")
    else:
        print("  Phone Link call DB not found or empty.")
        print(f"  Expected: {PHONE_LINK_DB}")

    print("\n[3] Starting live monitor (Ctrl+C to stop)...")
    monitor_loop()
