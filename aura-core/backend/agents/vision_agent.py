"""
AURA / JARVIS Autonomous Vision & Screen Perception Agent.
==========================================================
Captures active desktop/window context, analyzes errors or UI elements,
and invokes Gemini Flash Vision for intelligent spoken analysis.
"""

import os
import io
import re
import base64
import requests
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

# Try loading GEMINI_API_KEY
try:
    from dotenv import dotenv_values
    env_path = os.path.join(BACKEND_DIR, ".env")
    _env_vals = dotenv_values(env_path) if os.path.exists(env_path) else {}
except Exception:
    _env_vals = {}

GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or _env_vals.get("GEMINI_API_KEY", "")).strip()


def capture_desktop_screenshot() -> Optional[bytes]:
    """Captures screenshot as PNG bytes."""
    # Method 1: mss
    try:
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(monitor)
            from PIL import Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.thumbnail((1280, 720))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            return buf.getvalue()
    except Exception:
        pass

    # Method 2: PIL ImageGrab
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.thumbnail((1280, 720))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return buf.getvalue()
    except Exception:
        pass

    return None


def get_active_window_summary() -> str:
    """Gets titles of active foreground applications."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        if title:
            return f"Active foreground window: '{title}'."
    except Exception:
        pass
    return "Desktop session active."


def analyze_screen(prompt: str = "Explain what is on Sir's screen and diagnose any errors or active work.") -> str:
    """Takes a screenshot and asks Gemini Vision to analyze it."""
    if not GEMINI_API_KEY:
        return "Sir, Gemini API key is required for visual screen analysis."

    img_bytes = capture_desktop_screenshot()
    win_summary = get_active_window_summary()

    if not img_bytes:
        return f"Sir, I could not capture the physical screen buffer ({win_summary}). However, your desktop session is active."

    b64_img = base64.b64encode(img_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"You are JARVIS. Speak directly to Sir in 2 to 3 concise, clear spoken sentences. {win_summary}\n\nTask: {prompt}"},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": b64_img
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 300,
            "temperature": 0.4
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    ans = parts[0]["text"].strip()
                    ans = re.sub(r'[*_~`]', '', ans).strip()
                    return ans
        return f"Sir, I captured your screen ({win_summary}), but the visual analysis service returned status {resp.status_code}."
    except Exception as e:
        return f"Sir, screen analysis encountered an error: {e}"
