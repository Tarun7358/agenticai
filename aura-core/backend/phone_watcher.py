"""
Phone Link Real-Time Call Monitor for Laptop 2
Watches for iPhone incoming and missed calls via Windows Phone Link
and forwards them immediately to AURA & JARVIS.
"""
import os
import sqlite3
import time
import requests
import datetime
import re
import xml.etree.ElementTree as ET

LOCAL_BACKEND = "http://127.0.0.1:8000"
NOTIF_DB = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db")

seen_ids = set()

def parse_payload(payload):
    try:
        root = ET.fromstring(payload)
        texts = [el.get("content", "") for el in root.iter("text")]
        full = " | ".join(t for t in texts if t)
        if not full:
            return None

        caller = "Unknown"
        ctype = "incoming"
        lower = full.lower()

        if "missed" in lower:
            ctype = "missed"
        elif "calling" in lower or "incoming" in lower or "call" in lower:
            ctype = "incoming"
        else:
            return None

        for t in texts:
            if t and not any(k in t.lower() for k in ["missed", "call", "phone", "link"]):
                caller = t.strip()
                break

        if caller == "Unknown":
            m = re.search(r'[\+\d][\d\s\-\(\)]{7,}', full)
            if m:
                caller = m.group().strip()

        return {"caller": caller, "type": ctype, "raw": full[:100]}
    except Exception:
        return None

def check_calls():
    if not os.path.exists(NOTIF_DB):
        return
    try:
        con = sqlite3.connect(f"file:{NOTIF_DB}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute("""
            SELECT n.RecordId, n.Payload, h.PrimaryId
            FROM Notification n
            LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
            WHERE (h.PrimaryId LIKE '%YourPhone%' OR h.PrimaryId LIKE '%PhoneLink%' OR h.PrimaryId LIKE '%phone%')
            ORDER BY n.ArrivalTime DESC
            LIMIT 10
        """)
        rows = cur.fetchall()
        con.close()

        for rid, payload, app in rows:
            if rid in seen_ids:
                continue
            seen_ids.add(rid)

            if isinstance(payload, bytes):
                p_str = payload.decode("utf-8", errors="ignore")
            else:
                p_str = str(payload or "")

            parsed = parse_payload(p_str)
            if parsed:
                now = datetime.datetime.now().strftime("%I:%M %p")
                event = {
                    "caller": parsed["caller"],
                    "type": parsed["type"],
                    "time": now,
                    "source": "phone_link"
                }
                print(f"[PHONE] 📞 Detected {parsed['type'].upper()} call from {parsed['caller']} at {now}")
                try:
                    requests.post(f"{LOCAL_BACKEND}/phone/call-event", json=event, timeout=3)
                except Exception as ex:
                    print(f"[PHONE] Error posting event: {ex}")
    except Exception:
        pass

if __name__ == "__main__":
    print("[PHONE MONITOR] 🟢 Watching Phone Link for incoming & missed calls...")
    while True:
        check_calls()
        time.sleep(2)
