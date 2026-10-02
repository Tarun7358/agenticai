"""
AURA / JARVIS Sovereign Autonomous Reminder & Scheduling Agent.
===============================================================
Manages natural language reminders, background alarms, and scheduled announcements.
- Parses relative and absolute timestamps (e.g. '7:00 a.m. today morning', 'in 15 minutes').
- Persists reminders locally to backend/data/reminders.json.
- Runs a background watchdog thread that fires callbacks / announcements on time.
- Fully sovereign and local: zero cloud dependency for scheduling.
"""

import os
import re
import json
import time
import uuid
import datetime
import threading
from typing import Dict, Any, List, Optional, Callable

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
REMINDERS_FILE = os.path.join(BACKEND_DIR, "data", "reminders.json")

_callbacks: List[Callable[[Dict[str, Any]], None]] = []
_watchdog_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_lock = threading.Lock()


def register_reminder_callback(cb: Callable[[Dict[str, Any]], None]) -> None:
    """Registers a listener function to be called when a reminder fires."""
    with _lock:
        if cb not in _callbacks:
            _callbacks.append(cb)


def _load_reminders() -> List[Dict[str, Any]]:
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_reminders(reminders: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ReminderAgent] Error saving reminders: {e}")


def parse_reminder_request(query: str, now: Optional[datetime.datetime] = None) -> Optional[Dict[str, Any]]:
    """
    Parses natural language queries like:
    - 'make a reminder at 7:00 a.m. today morning to go to marina'
    - 'remind me at 7 am to check the server'
    - 'set a reminder in 15 minutes to call Tarun'
    - 'remind me tomorrow morning at 8:30 am to attend standup'
    """
    if not now:
        now = datetime.datetime.now()

    q = query.lower().strip()
    
    # 1. Extract note/task text
    # Usually preceded by 'to', 'for', 'about', or 'saying'
    # E.g. "... at 7:00 am today morning to go to marina"
    task = ""
    task_match = re.search(r'\b(?:to|for|about|saying)\s+(.+)$', q, flags=re.IGNORECASE)
    if task_match:
        task = task_match.group(1).strip()
        # Remove trailing polite phrases
        task = re.sub(r'\b(?:sir|jarvis|aura|please)\b', '', task, flags=re.IGNORECASE).strip()

    # 2. Relative time: 'in X minutes/hours/seconds'
    rel_match = re.search(r'\bin\s+(\d+(?:\.\d+)?)\s*(second|seconds|sec|minute|minutes|min|hour|hours|hr)s?\b', q, flags=re.IGNORECASE)
    if rel_match:
        val = float(rel_match.group(1))
        unit = rel_match.group(2).lower()
        if 'sec' in unit:
            target_dt = now + datetime.timedelta(seconds=val)
        elif 'hour' in unit or 'hr' in unit:
            target_dt = now + datetime.timedelta(hours=val)
        else:
            target_dt = now + datetime.timedelta(minutes=val)

        if not task:
            task = re.sub(r'^.*?\bin\s+\d+\s*(?:second|minute|hour)s?\s*(?:to\s+)?', '', q, flags=re.IGNORECASE).strip() or "general reminder"

        return {
            "target_dt": target_dt,
            "task": task or "check your schedule",
            "time_str": target_dt.strftime("%I:%M %p")
        }

    # 3. Absolute time: e.g. '7:00 a.m.', '7:00am', '7 am', '7:30 pm', '07:00', '19:30'
    time_pattern = r'\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?|am|pm)?\b'
    matches = list(re.finditer(time_pattern, q, flags=re.IGNORECASE))
    
    time_match = None
    # Pick match that has am/pm or ':' or is preceded by 'at'
    for m in matches:
        raw = m.group(0).lower()
        start = m.start()
        prefix = q[max(0, start - 5):start]
        if "at" in prefix or "am" in raw or "pm" in raw or ":" in raw:
            time_match = m
            break
    
    if not time_match and matches:
        time_match = matches[0]

    if not time_match:
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2)) if time_match.group(2) else 0
    meridiem = time_match.group(3).lower().replace(".", "") if time_match.group(3) else None

    # Contextual clues: 'morning', 'night', 'evening', 'afternoon'
    is_morning = bool(re.search(r'\b(morning|today morning)\b', q))
    is_evening = bool(re.search(r'\b(evening|tonight|night)\b', q))
    is_afternoon = bool(re.search(r'\b(afternoon)\b', q))
    is_tomorrow = bool(re.search(r'\btomorrow\b', q))

    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    elif not meridiem:
        if is_morning and hour < 12:
            pass
        elif (is_evening or is_afternoon) and hour < 12:
            hour += 12
        elif hour < 7:  # E.g. user says 2 or 3 without am/pm, usually means PM
            hour += 12

    # Calculate target datetime
    target_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if is_tomorrow:
        target_dt += datetime.timedelta(days=1)
    else:
        # If target time is already in the past today:
        # e.g., current time is 12:06 AM, target is 7:00 AM today -> target_dt is in the FUTURE today!
        # If current time is 8:00 AM, and target was 7:00 AM -> target_dt has passed today, so schedule for tomorrow.
        if target_dt <= now:
            # If user explicitly said 'today' or 'today morning' but time has already passed:
            # We schedule for next occurrence (tomorrow).
            target_dt += datetime.timedelta(days=1)

    if not task:
        # Strip out the time and reminder command parts
        rem = re.sub(r'^(?:make|set|create|put)?\s*(?:a\s+)?(?:reminder|alarm)\s*(?:at|for|to)?\s*', '', q, flags=re.IGNORECASE)
        rem = re.sub(time_pattern, '', rem, flags=re.IGNORECASE)
        rem = re.sub(r'\b(today|tomorrow|morning|evening|night|afternoon|at|for|to)\b', '', rem, flags=re.IGNORECASE).strip()
        task = rem or "your scheduled task"

    return {
        "target_dt": target_dt,
        "task": task,
        "time_str": target_dt.strftime("%I:%M %p")
    }


def add_reminder(query: str) -> Dict[str, Any]:
    """Parses query and stores the new reminder in persistent JSON."""
    now = datetime.datetime.now()
    parsed = parse_reminder_request(query, now=now)
    if not parsed:
        return {
            "status": "error",
            "message": "Sir, I couldn't identify the specific time for the reminder. Please specify a time like 'at 7:00 am' or 'in 15 minutes'."
        }

    target_dt: datetime.datetime = parsed["target_dt"]
    task: str = parsed["task"]
    time_str = parsed["time_str"]

    is_today = target_dt.date() == now.date()
    day_str = "today" if is_today else ("tomorrow" if target_dt.date() == (now.date() + datetime.timedelta(days=1)) else target_dt.strftime("%A, %b %d"))

    reminder_entry = {
        "id": str(uuid.uuid4())[:8],
        "created_at": now.isoformat(),
        "target_iso": target_dt.isoformat(),
        "task": task,
        "time_str": time_str,
        "day_str": day_str,
        "status": "pending"
    }

    with _lock:
        reminders = _load_reminders()
        reminders.append(reminder_entry)
        _save_reminders(reminders)

    ensure_watchdog_running()

    return {
        "status": "ok",
        "reminder": reminder_entry,
        "message": f"Reminder set for {time_str} {day_str} to {task}, Sir. I will notify you right on time."
    }


def get_active_reminders() -> List[Dict[str, Any]]:
    """Returns list of pending reminders sorted by upcoming time."""
    now_iso = datetime.datetime.now().isoformat()
    with _lock:
        reminders = _load_reminders()
    pending = [r for r in reminders if r.get("status") == "pending" and r.get("target_iso", "") >= now_iso]
    pending.sort(key=lambda x: x.get("target_iso", ""))
    return pending


def format_reminders_summary() -> str:
    """Spoken summary of active reminders."""
    active = get_active_reminders()
    if not active:
        return "You have no active reminders scheduled right now, Sir."
    
    parts = []
    for r in active[:3]:
        parts.append(f"{r.get('task')} at {r.get('time_str')} {r.get('day_str')}")
    
    if len(active) == 1:
        return f"Sir, you have one scheduled reminder: {parts[0]}."
    return f"Sir, you have {len(active)} scheduled reminders: " + "; ".join(parts) + "."


def cancel_reminders(keyword: str = "") -> str:
    """Cancels matching or all reminders."""
    with _lock:
        reminders = _load_reminders()
        count = 0
        for r in reminders:
            if r.get("status") == "pending":
                if not keyword or keyword.lower() in r.get("task", "").lower() or keyword.lower() in ["all", "everything"]:
                    r["status"] = "cancelled"
                    count += 1
        _save_reminders(reminders)

    if count == 0:
        return "No pending reminders matched that description, Sir."
    return f"Cancelled {count} scheduled reminder{'s' if count > 1 else ''} for you, Sir."


def check_and_trigger_due_reminders() -> List[Dict[str, Any]]:
    """Checks for reminders that have matured and marks them completed."""
    now_iso = datetime.datetime.now().isoformat()
    due = []
    with _lock:
        reminders = _load_reminders()
        updated = False
        for r in reminders:
            if r.get("status") == "pending" and r.get("target_iso", "") <= now_iso:
                r["status"] = "triggered"
                r["triggered_at"] = now_iso
                due.append(r)
                updated = True
        if updated:
            _save_reminders(reminders)

    for item in due:
        for cb in _callbacks:
            try:
                cb(item)
            except Exception as e:
                print(f"[ReminderAgent] Callback error: {e}")

    return due


def _watchdog_loop():
    while not _stop_event.is_set():
        try:
            check_and_trigger_due_reminders()
        except Exception:
            pass
        time.sleep(3.0)


def ensure_watchdog_running():
    global _watchdog_thread
    if _watchdog_thread is None or not _watchdog_thread.is_alive():
        _watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True)
        _watchdog_thread.start()


# Start watchdog on module load
ensure_watchdog_running()
