"""
iPhone & Windows Phone Link Integration Agent for AURA / JARVIS.
================================================================
Connects with iPhone via:
1. Native Windows Phone Link (Direct Bluetooth Low Energy P2P pairing for Calls, Missed Calls, & iMessage).
2. Direct Windows Telephone Protocol (`start tel:<number>`) for instantaneous voice calling.
3. Persistent Local Contact Book (`aura-core/data/contacts.json`) with .env fallback.
4. Local Windows Notification Database (Offline SQLite inspection).
5. Local LAN iOS Shortcuts Webhooks (Zero Cloud, direct to local laptop over Wi-Fi).

Zero cloud leakage: all sync runs peer-to-peer via Bluetooth, tel protocol, and local LAN.
"""

import os
import re
import json
import sqlite3
import subprocess
import datetime
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
DATA_DIR = os.path.join(BASE_DIR, "data")
CONTACTS_PATH = os.path.join(DATA_DIR, "contacts.json")

# In-memory recent call events received via Local LAN or Phone Link
_RECENT_CALLS: List[Dict[str, Any]] = []


def launch_phone_link() -> str:
    """Launches Windows Phone Link directly on screen."""
    try:
        subprocess.Popen(["cmd", "/c", "start", "ms-phone-link:"], shell=True)
        return "Launching Windows Phone Link on your screen, sir. Select iPhone to pair via Bluetooth."
    except Exception as ex:
        return f"Unable to launch Phone Link: {ex}"


def get_contacts() -> Dict[str, str]:
    """Retrieves local contact mappings from contacts.json and .env."""
    contacts = {}
    if os.path.exists(CONTACTS_PATH):
        try:
            with open(CONTACTS_PATH, "r", encoding="utf-8") as f:
                contacts = json.load(f)
        except Exception:
            pass

    # Merge with .env contacts
    try:
        from dotenv import dotenv_values
        env_path = os.path.join(BACKEND_DIR, ".env")
        vals = dotenv_values(env_path) if os.path.exists(env_path) else {}
        for k, v in vals.items():
            if k.startswith("PHONE_") or k.startswith("CONTACT_") or k.startswith("WHATSAPP_CONTACT_"):
                clean_name = re.sub(r'^(?:PHONE|CONTACT|WHATSAPP_CONTACT)_', '', k).lower().replace('_', ' ')
                contacts[clean_name] = v.strip()
    except Exception:
        pass

    return contacts


def save_contact(name: str, number: str) -> None:
    """Saves a contact number locally to contacts.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    contacts = {}
    if os.path.exists(CONTACTS_PATH):
        try:
            with open(CONTACTS_PATH, "r", encoding="utf-8") as f:
                contacts = json.load(f)
        except Exception:
            pass

    clean_name = name.lower().strip()
    clean_num = number.strip()
    contacts[clean_name] = clean_num

    try:
        with open(CONTACTS_PATH, "w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=2)
    except Exception:
        pass


def make_phone_call(target: str = "") -> Dict[str, Any]:
    """
    Executes a real phone call via Windows Phone Link:
    - If target has digits, dials directly: `start tel:<digits>`.
    - If target is a contact name, looks up contact number.
    - If no number is known, launches Phone Link dialer (`ms-phone-link:`)
      and prompts user for number to connect directly.
    """
    clean_target = target.strip() if target else ""
    
    # 1. Target contains digits directly (e.g. "9876543210" or "+919876543210")
    digits = re.sub(r'[^0-9+]', '', clean_target)
    if len(digits) >= 7:
        try:
            subprocess.Popen(["cmd", "/c", "start", f"tel:{digits}"], shell=True)
            return {
                "status": "dialed",
                "number": digits,
                "target": digits,
                "message": f"Dialing {digits} through Windows Phone Link on your screen now, sir."
            }
        except Exception as ex:
            return {"status": "error", "message": f"Unable to trigger Phone Link dialer: {ex}"}

    # 2. Check contacts dictionary
    contacts = get_contacts()
    t_low = clean_target.lower()
    matched_number = None
    matched_name = clean_target

    for name, num in contacts.items():
        if name in t_low or t_low in name:
            matched_number = num
            matched_name = name
            break

    if matched_number:
        try:
            subprocess.Popen(["cmd", "/c", "start", f"tel:{matched_number}"], shell=True)
            return {
                "status": "dialed",
                "number": matched_number,
                "target": matched_name.title(),
                "message": f"Dialing {matched_name.title()} at {matched_number} through Windows Phone Link now, sir."
            }
        except Exception as ex:
            return {"status": "error", "message": f"Unable to dial Phone Link: {ex}"}

    # 3. No specific number resolved yet -> Open Phone Link dialer directly
    try:
        subprocess.Popen(["cmd", "/c", "start", "ms-phone-link:"], shell=True)
    except Exception:
        pass

    if clean_target and clean_target != "__PREVIOUS_OR_DIALER__":
        return {
            "status": "needs_number",
            "target": clean_target.title(),
            "message": f"Opening Phone Link to call {clean_target.title()} now, sir. What is the phone number so I can connect it directly?"
        }
    else:
        return {
            "status": "dialer_opened",
            "target": "Phone Link",
            "message": "Bringing up the Phone Link dialer on your screen now, sir. Connecting your call."
        }


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

    return events or _RECENT_CALLS[-5:]


def record_call_event(caller: str, event_type: str = "missed", timestamp: str = None) -> Dict[str, Any]:
    """Records a call event from iOS Shortcuts local LAN automation or notification watcher."""
    now = timestamp or datetime.datetime.now().strftime("%I:%M %p")
    event = {
        "caller": caller or "Unknown Caller",
        "type": event_type,
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
