"""
AURA / JARVIS Unified Autonomous Tools & Action Engine.
======================================================
Central execution registry enabling multi-step tool calls,
autonomous diagnostics, executive briefings, and system mastery.
"""

import os
import re
import datetime
import subprocess
import psutil
from typing import Dict, Any, List, Optional


def lock_workstation() -> str:
    """Locks Windows session immediately."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "Workstation locked successfully, Sir. Have a good rest."
    except Exception as e:
        return f"Error locking workstation: {e}"


def sleep_system() -> str:
    """Puts PC to sleep."""
    try:
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=True)
        return "Putting your PC into sleep mode now, Sir."
    except Exception as e:
        return f"Could not sleep PC: {e}"


def set_audio_volume(action: str) -> str:
    """Adjusts system volume: mute, unmute, up, down."""
    import ctypes
    a = action.lower()
    if "mute" in a and "unmute" not in a:
        ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
        return "Audio muted, Sir."
    elif "unmute" in a:
        ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
        return "Audio unmuted, Sir."
    elif "up" in a or "louder" in a or "increase" in a:
        for _ in range(5):
            ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
        return "Volume increased, Sir."
    elif "down" in a or "softer" in a or "lower" in a:
        for _ in range(5):
            ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
        return "Volume decreased, Sir."
    return "Volume command unrecognized, Sir."


def get_executive_briefing() -> str:
    """Compiles a complete, cinema-grade executive briefing for Sir."""
    now = datetime.datetime.now()
    hour = now.hour
    time_str = now.strftime("%I:%M %p")
    day_str = now.strftime("%A, %B %d")

    if 4 <= hour < 12:
        sal = "Good morning"
    elif 12 <= hour < 17:
        sal = "Good afternoon"
    elif 17 <= hour < 22:
        sal = "Good evening"
    else:
        sal = "Good evening, Sir, working late tonight"

    parts = [f"{sal}, Sir. It is {time_str} on {day_str}."]

    # 1. Reminders
    try:
        from agents import reminder_agent
        active = reminder_agent.get_active_reminders()
        if active:
            r_texts = [f"{r.get('task')} at {r.get('time_str')} {r.get('day_str')}" for r in active[:2]]
            parts.append(f"You have {len(active)} scheduled reminder{'s' if len(active)>1 else ''}: {'; '.join(r_texts)}.")
        else:
            parts.append("Your schedule has zero pending reminders.")
    except Exception:
        pass

    # 2. Server Telemetry & Health
    try:
        from agents import rage_agent
        violations = rage_agent.scan_rage_violations(limit=3)
        if violations:
            parts.append(f"RAGE Optimizer is operational, though security watcher flagged {len(violations)} recent log alerts.")
        else:
            parts.append("RAGE Optimizer is running smoothly with zero security violations.")
    except Exception:
        pass

    # 3. Unread Emails
    try:
        from agents import email_agent
        email_summary = email_agent.get_unread_emails_summary()
        if "unread" in email_summary.lower() and "zero" not in email_summary.lower():
            parts.append(email_summary)
    except Exception:
        pass

    # 4. System Specs
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    bat_str = f"battery at {battery.percent}%" if battery else "on AC power"
    parts.append(f"Workstation is running at {cpu}% CPU, {ram}% RAM, {bat_str}. All background agents standing by.")

    return " ".join(parts)


def execute_tool(tool_name: str, args: Dict[str, Any]) -> str:
    """Executes named tool with arguments."""
    t = tool_name.lower().strip()
    try:
        if t == "lock_workstation":
            return lock_workstation()
        elif t == "sleep_system":
            return sleep_system()
        elif t == "set_volume":
            return set_audio_volume(args.get("action", "up"))
        elif t == "executive_briefing":
            return get_executive_briefing()
        elif t == "create_reminder":
            from agents import reminder_agent
            res = reminder_agent.add_reminder(args.get("query", ""))
            return res.get("message", "Reminder created, Sir.")
        elif t == "list_reminders":
            from agents import reminder_agent
            return reminder_agent.format_reminders_summary()
        elif t == "cancel_reminder":
            from agents import reminder_agent
            return reminder_agent.cancel_reminders(args.get("keyword", "all"))
        elif t == "self_heal_server":
            from agents import self_healing_agent
            return self_healing_agent.auto_heal_server_issues()
        elif t == "save_memory":
            from agents import memory_agent
            return memory_agent.save_fact(args.get("fact", ""))
        elif t == "inspect_screen":
            from agents import vision_agent
            return vision_agent.analyze_screen(args.get("prompt", "Analyze Sir's active screen."))
        elif t == "search_web":
            from agents import research_agent
            res = research_agent.search_live_web(args.get("query", ""))
            return res.get("snippets", "No web results found.")
    except Exception as e:
        return f"Error executing tool {tool_name}: {e}"

    return f"Tool {tool_name} is not recognized, Sir."
