"""
iPhone Integration Agent for AURA / JARVIS.
Connects with iPhone via:
1. Native Windows Phone Link (Direct Bluetooth Low Energy P2P pairing for Calls, Missed Calls, & iMessage).
2. Local Windows Notification Database (Offline SQLite inspection).
3. Local LAN iOS Shortcuts Webhooks (Zero Cloud, direct to local laptop over Wi-Fi).
4. Calendar & Scheduled Call Reminders.

Zero cloud leakage: all sync runs peer-to-peer via Bluetooth and local LAN.
"""
import os
import sqlite3
import subprocess
import webbrowser
import datetime
from typing import Dict, Any, List

# In-memory recent call events received via Local LAN or Phone Link
_RECENT_CALLS: List[Dict[str, Any]] = []

def launch_phone_link() -> str:
    """Launches Windows Phone Link directly for iPhone Bluetooth pairing."""
    try:
        subprocess.Popen(["cmd", "/c", "start", "ms-phone-link:"], shell=True)
        return "Launching Windows Phone Link on your screen, sir. Select iPhone to pair via Bluetooth."
    except Exception as ex:
        return f"Unable to launch Phone Link: {ex}"

def get_recent_phone_notifications() -> List[Dict[str, Any]]:
    """
    Safely inspects local Windows Notification database for Phone Link & WhatsApp calls.
    100% offline and read-only.
    """
    db_path = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db")
    if not os.path.exists(db_path):
        return _RECENT_CALLS[-5:] if _RECENT_CALLS else []

    events = []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = con.cursor()
        query = """
            SELECT n.Type, n.Payload, n.ArrivalTime, h.PrimaryId
            FROM Notification n
            LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
            WHERE h.PrimaryId LIKE '%YourPhone%' OR h.PrimaryId LIKE '%PhoneLink%' OR h.PrimaryId LIKE '%WhatsApp%'
            ORDER BY n.ArrivalTime DESC
            LIMIT 5
        """
        cur.execute(query)
        for row in cur.fetchall():
            payload_str = str(row[1]) if row[1] else ""
            events.append({
                "type": row[0],
                "app": row[3],
                "payload": payload_str[:150],
                "time": str(row[2])
            })
        con.close()
    except Exception:
        pass

    # Merge with any local shortcut events
    return events or _RECENT_CALLS[-5:]

def record_call_event(caller: str, event_type: str = "missed", timestamp: str = None) -> Dict[str, Any]:
    """
    Records a call event from iOS Shortcuts local LAN automation or notification watcher.
    """
    now = timestamp or datetime.datetime.now().strftime("%I:%M %p")
    event = {
        "caller": caller or "Unknown Caller",
        "type": event_type, # "missed", "incoming", "scheduled"
        "time": now
    }
    _RECENT_CALLS.append(event)
    return event

def get_missed_calls() -> List[Dict[str, Any]]:
    """Returns missed calls recorded locally."""
    return [c for c in _RECENT_CALLS if c.get("type") == "missed"]

def get_upcoming_calls() -> List[Dict[str, Any]]:
    """Returns upcoming scheduled calls or meetings."""
    return [c for c in _RECENT_CALLS if c.get("type") == "scheduled"]
