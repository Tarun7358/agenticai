"""
AURA / JARVIS Active Voice Dictation & Ghostwriter.
===================================================
Instantly types text, emails, code, or AI-ghostwritten drafts directly
into the active focused Windows window (Word, VS Code, Browser, Discord, etc.).
"""

import time
import pyperclip
import pyautogui
from typing import Dict, Any, Optional


def type_into_focused_window(text: str) -> str:
    """Copies text to the clipboard and pastes it into the active input cursor."""
    if not text:
        return "No text provided to type, Sir."

    # Save prior clipboard content to restore later if desired
    try:
        prior_clip = pyperclip.paste()
    except Exception:
        prior_clip = ""

    pyperclip.copy(text)
    time.sleep(0.05)
    import ctypes
    # VK_CONTROL = 0x11, ord('V') = 0x56
    ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)
    time.sleep(0.02)
    ctypes.windll.user32.keybd_event(0x56, 0, 2, 0)
    ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
    time.sleep(0.05)

    return f"Typed {len(text)} characters directly into your active window, Sir."


def ghostwrite_and_type(prompt: str) -> str:
    """Uses Gemini Flash to compose an intelligent message/reply and types it directly."""
    try:
        from agents import gemini_agent
        system_prompt = (
            "You are an expert executive ghostwriter for Sir. Write the exact text, reply, or code Sir requested. "
            "Do NOT include conversational meta-chatter, preamble, or quotes like 'Here is your reply:'. "
            "Output ONLY the exact words ready to be pasted directly into an email, chat, or document."
        )
        if gemini_agent.is_gemini_active():
            draft = gemini_agent.query_gemini(
                prompt=f"Ghostwrite this for me: {prompt}",
                system_prompt=system_prompt,
                max_tokens=400,
                timeout=8
            )
            if draft:
                return type_into_focused_window(draft.strip())
    except Exception as ex:
        print(f"[Ghostwriter] Gemini error: {ex}")

    # Fallback direct type if ghostwrite LLM fails
    return type_into_focused_window(prompt)
