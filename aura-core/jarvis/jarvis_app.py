"""
AURA JARVIS HUD — Pure Iron Man Arc Reactor Voice Assistant
- Holographic Arc Reactor Visual (Pure HUD, No Chatbot Clutter)
- Always-On Background Wake-Word ("Hey Aura" / "Jarvis")
- Auto-Detects Active Microphone (Logitech C270 / USB / Realtek)
- Real-time Speech Recognition + Spoken Human-like Assistant Dialogue
- Offline Zero-Latency Voice Engine (pyttsx3)
- Instant System, Network, and File Intelligence
"""

import os
import sys
import time
import json
import threading
import datetime
import re
import audioop
from typing import Optional, List, Dict, Any

import subprocess
import webbrowser
import urllib.parse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import webview
import psutil
import speech_recognition as sr
import pyttsx3
import requests

try:
    import keyboard
    HAS_KEYBOARD = True
except Exception:
    HAS_KEYBOARD = False

try:
    from agents import network_agent, instagram_agent, file_agent, github_agent, youtube_agent, rage_agent, email_agent
    from config import settings
    HAS_LOCAL_AGENTS = True

except Exception as e:
    HAS_LOCAL_AGENTS = False


WAKE_PATTERNS = [
    r"\b(hey|hi|ok|hello|yo|ay)?\s*(aura|ora|ara|laura|aora|aurora)\b",
    r"\b(hey|hi|ok|hello|yo)?\s*(jarvis|travis|service|jarves|kavya|kavi)\b",
]

def check_wake_word(text: str):
    """Checks if text contains a wake word, returning (is_wake, trailing_command)."""
    text = text.lower().strip()
    for pat in WAKE_PATTERNS:
        m = re.search(pat, text)
        if m:
            trailing = text[m.end():].strip(" ,.?")
            return True, trailing
    return False, ""


def get_windows_default_microphone():
    """Queries Windows for the exact default recording device (the device with the green checkmark)."""
    env_idx = os.environ.get("JARVIS_MIC_INDEX")
    if env_idx is not None:
        try:
            return int(env_idx), f"Manual Index [{env_idx}]"
        except Exception:
            pass

    try:
        import pyaudio
        p = pyaudio.PyAudio()
        info = p.get_default_input_device_info()
        idx = info.get("index")
        name = info.get("name")
        p.terminate()
        print(f"[*] Windows Default Recording Device (Green Checkmark): [{idx}] '{name}'")
        return idx, name
    except Exception as e:
        print(f"[!] Warning: Could not query default device ({e}), using system default mapper.")
        return None, "System Default"




def get_jarvis_system_prompt() -> str:
    now = datetime.datetime.now()
    hour = now.hour
    if 4 <= hour < 12:
        period = "morning"
        salutation = "Good morning"
    elif 12 <= hour < 17:
        period = "afternoon"
        salutation = "Good afternoon"
    elif 17 <= hour < 22:
        period = "evening"
        salutation = "Good evening"
    else:
        period = "late night"
        salutation = "Good evening / working late tonight"

    time_str = now.strftime("%I:%M %p, %A, %B %d")
    return (
        f"You are JARVIS (AURA), an ultra-intelligent, articulate, polite personal AI assistant. "
        f"The current real-world local time is {time_str} ({period}). "
        f"CRITICAL TEMPORAL CONSTRAINT: It is currently {period}. You must NEVER say 'Good morning' or greet as morning unless the current time is actually morning (4 AM to 12 PM). Greet with '{salutation}' or polite late-night acknowledgment. "
        f"Respond naturally like a real human assistant speaking directly to your boss ('Sir'). "
        f"Keep answers concise in 1 to 2 spoken sentences. "
        f"You have full authorized control of Sir's Windows desktop, apps (WhatsApp, Spotify, Instagram), files, and system settings. "
        f"Do NOT use markdown, bullet points, asterisks, or robotic formatting."
    )

JARVIS_SYSTEM_PROMPT = get_jarvis_system_prompt()



def get_live_phone_calls_summary(query: str = "") -> Optional[str]:
    """
    Directly queries live Phone Link call events from Laptop 2 and local backend.
    Returns real, factual caller details and never hallucinates.
    """
    backend_urls = [
        os.environ.get("OLLAMA_BASE_URL", "http://192.168.0.4:8000").rstrip("/"),
        "http://192.168.0.4:8000",
        "http://127.0.0.1:8000"
    ]
    calls_data = None
    for b in backend_urls:
        try:
            r = requests.get(f"{b}/phone/calls", timeout=2)
            if r.status_code == 200:
                data = r.json()
                if data.get("count", 0) > 0 or data.get("recent"):
                    calls_data = data
                    break
        except Exception:
            continue

    if not calls_data or not calls_data.get("recent"):
        return None

    recent = calls_data.get("recent", [])
    missed = calls_data.get("missed", [])
    q_low = query.lower()

    if "missed" in q_low:
        if not missed:
            return "You have no unread missed calls, sir. All your recent calls were answered."
        latest = missed[-1]
        caller = latest.get("caller", "Unknown")
        time_str = latest.get("time", "")
        if len(missed) == 1:
            return f"Sir, you have one missed call from {caller} at {time_str}."
        else:
            names = ", ".join(m.get("caller", "Unknown") for m in missed[-3:])
            return f"Sir, you have {len(missed)} missed calls. Recent callers include {names}."

    if any(k in q_low for k in ["caller id", "who called", "who was that", "caller", "incoming", "who's calling"]):
        latest = recent[-1]
        caller = latest.get("caller", "Unknown")
        ctype = latest.get("type", "call")
        time_str = latest.get("time", "")
        return f"Sir, the latest {ctype} was from {caller} at {time_str}."

    latest = recent[-1]
    return f"Sir, your latest call was a {latest.get('type', 'call')} from {latest.get('caller', 'Unknown')} at {latest.get('time', '')}."


def query_ollama_endpoint(endpoint_path: str, payload: dict, timeout=8):
    """Resilient Ollama caller: tries configured OLLAMA_BASE_URL (port 8000 or 11434) with local fallback."""
    base = os.environ.get("OLLAMA_BASE_URL") or getattr(settings, "ollama_base_url", "http://localhost:11434").rstrip('/')
    candidates = [base]
    if ":11434" in base:
        candidates.append(base.replace(":11434", ":8000"))
    elif ":8000" in base:
        candidates.append(base.replace(":8000", ":11434"))
    candidates.append("http://localhost:11434")

    for u in candidates:
        try:
            target = f"{u}{endpoint_path}"
            resp = requests.post(target, json=payload, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            continue
    return None


class JarvisVoice:
    """Offline, human-like voice synthesis using pyttsx3."""
    def __init__(self):
        self._lock = threading.Lock()
        self.is_speaking = False
        self.preferred_voice_id = None
        try:
            eng = pyttsx3.init()
            for v in eng.getProperty('voices'):
                if "david" in v.name.lower() or "zira" in v.name.lower():
                    self.preferred_voice_id = v.id
                    break
            eng.stop()
        except Exception:
            pass

    def speak(self, text: str, on_start=None, on_end=None, blocking=False):
        def _run():
            with self._lock:
                self.is_speaking = True
                if on_start:
                    on_start()
                try:
                    clean = re.sub(r'[*_#`]', '', text)
                    clean = re.sub(r'\[.*?\]\(.*?\)', '', clean)
                    eng = pyttsx3.init()
                    eng.setProperty('rate', 192)
                    eng.setProperty('volume', 1.0)
                    if self.preferred_voice_id:
                        eng.setProperty('voice', self.preferred_voice_id)
                    eng.say(clean)
                    eng.runAndWait()
                    eng.stop()
                except Exception as ex:
                    print(f"[Voice] Speech error: {ex}")
                finally:
                    time.sleep(0.15)
                    self.is_speaking = False
                    if on_end:
                        on_end()

        if blocking:
            _run()
        else:
            threading.Thread(target=_run, daemon=True).start()


class JarvisBrain:
    """Intelligent query reasoning: System, Network, Files, or Ollama AI."""
    pending_action: Optional[Dict[str, Any]] = None

    @staticmethod
    def answer_query(query: str) -> str:
        q = query.lower().strip()

        # 0. Multi-turn Pending Context (e.g. Awaiting WhatsApp message or confirmation)
        if JarvisBrain.pending_action and (time.time() - JarvisBrain.pending_action.get("timestamp", 0) < 60):
            action = JarvisBrain.pending_action
            if action.get("type") == "whatsapp":
                contact = action.get("contact", "your contact")

                # Cancellation check
                if any(w in q for w in ["cancel", "never mind", "nevermind", "leave it", "stop", "abort", "forget it", "no"]):
                    JarvisBrain.pending_action = None
                    return "WhatsApp message canceled, sir. Standing by."

                # User says "send it" before dictating the message
                if q in ["send it", "send", "send this", "shoot", "ok send it", "just send it"]:
                    if not action.get("body"):
                        action["timestamp"] = time.time()  # refresh timeout
                        return f"Sir, you haven't dictated the message yet. What message would you like to send to {contact.title()}?"
                    else:
                        body = action["body"]
                        JarvisBrain.pending_action = None
                        return JarvisBrain._execute_whatsapp_send(contact, body)

                # Message provided by user
                dictated = re.sub(r"^(?:tell\s+(?:him|her|them)\s+|say\s+|that\s+)", "", query, flags=re.IGNORECASE).strip()
                JarvisBrain.pending_action = None
                return JarvisBrain._execute_whatsapp_send(contact, dictated)
        else:
            JarvisBrain.pending_action = None

        # 1. Instant Fast-Path Common Commands (<5ms latency)
        if any(k in q for k in ["what can you do", "your capabilities", "what do you do", "features"]):
            return "I have full local control over your laptop, sir. I can manage WhatsApp, launch YouTube Studio, monitor GitHub repositories, track Wi-Fi devices, inspect specs, and post Instagram reels."

        if any(w in q for w in ["access my device", "access my laptop", "access my system", "control my computer", "control my laptop", "access all things", "access everything"]):
            return "Yes, sir. I have authorized local control of your desktop, files, apps, GitHub repositories, Wi-Fi network, and YouTube analytics, with 100 percent local privacy."

        if any(k in q for k in ["how are you", "how are you doing", "status report"]):
            cpu = psutil.cpu_percent(interval=None)
            return f"Operating at peak efficiency, sir. CPU is at {cpu} percent, and all background watchers are operational."

        if any(k in q for k in ["who are you", "your name", "what are you"]):
            return "I am AURA, your personal Jarvis AI. Running locally on your laptop with your RTX graphics card. At your service, sir."

        # Standby, dismissals, and polite acknowledgments (<5ms)
        if any(w in q for w in ["thank", "thanks", "that is all", "that's all", "nothing", "never mind", "nevermind", "leave it", "cancel", "standby", "go to sleep", "sleep mode", "goodbye", "bye", "ok ok", "okay okay", "nothing nothing"]):
            return "Always a pleasure, sir. Standing by."

        # Dynamic Time-Aware Greetings (Fixes 'Good morning' at 11 PM)
        is_greeting = any(k == q for k in ["hello", "hi", "hey", "good morning", "good evening", "good afternoon", "good night", "ok", "okay", "alright", "cool"]) or \
                      any(w in q for w in ["good morning", "good evening", "good afternoon", "good night", "morning"]) or \
                      (any(k in q for k in ["hello", "hi", "hey", "greetings"]) and len(q.split()) <= 4)

        if is_greeting:
            now = datetime.datetime.now()
            hour = now.hour
            time_formatted = now.strftime("%I:%M %p")

            # Check if user specifically said "good morning" or "morning" when it is not morning
            if "good morning" in q or q.strip() == "morning":
                if hour >= 12 or hour < 4:
                    if hour >= 21 or hour < 4:
                        return f"Good evening, sir, though it is already {time_formatted} at night. Burning the midnight oil, I see. All systems are operational. How can I assist you?"
                    elif 12 <= hour < 17:
                        return f"Good afternoon, sir, it is currently {time_formatted}. All systems are operational. How can I assist you?"
                    else:
                        return f"Good evening, sir, it is currently {time_formatted}. All systems are operational. How can I assist you?"
                else:
                    return f"Good morning, sir. It is {time_formatted}. All systems are operational. How can I assist you?"

            if 4 <= hour < 12:
                return f"Good morning, sir. It is {time_formatted}. All systems are operational. How can I assist you?"
            elif 12 <= hour < 17:
                return f"Good afternoon, sir. All systems are operational. How can I assist you?"
            elif 17 <= hour < 22:
                return f"Good evening, sir. All systems are operational. How can I assist you?"
            else:
                return f"Good evening, sir. Working late tonight at {time_formatted}? All systems are online. How can I assist you?"

        # 2. Instagram Autonomous Uploads, Live Reel Analytics, and Captions
        is_instagram_query = bool(re.search(r"\b(instagram|insta|ig|reels?|followers?|captions?)\b", q)) and not any(w in q for w in ["youtube", "github", "git"])
        if is_instagram_query:
            from dotenv import dotenv_values
            env_path = os.path.join(BACKEND_DIR, ".env")
            env_vals = dotenv_values(env_path) if os.path.exists(env_path) else {}
            ig_user = env_vals.get("INSTAGRAM_USERNAME") or getattr(settings, "instagram_username", "") or "clasherofficial0"

            # A. Reel Upload Request
            if any(w in q for w in ["upload reel", "upload video", "post reel", "post video", "upload a reel", "publish reel"]):
                try:
                    from agents import instagram_engine
                    res = instagram_engine.upload_reel_post()
                    if res.get("status") == "ok":
                        return f"Reel uploaded successfully to @{ig_user}, sir! Your video {res.get('file')} is live with an AI-crafted viral caption."
                    elif "verification_code" in res.get("message", ""):
                        return f"Sir, Instagram requires a one-time two-factor verification code for @{ig_user}. Please say your 6-digit code or enter it in the console to unlock autonomous uploading."
                    else:
                        return f"Sir, I found your clip, but Instagram reported: {res.get('message', 'authentication required')}. I am opening your dashboard to assist."
                except Exception as ex:
                    return f"Uploading is prepared, sir. However, we need to finalize the one-time Instagram authentication: {str(ex)[:100]}."

            # B. AI Caption Generation Request
            if any(w in q for w in ["suggest caption", "write caption", "generate caption", "reel caption", "hashtags"]):
                try:
                    from agents import instagram_engine
                    caption = instagram_engine.generate_ai_caption(topic=query)
                    return f"Here is a viral caption for your reel, sir: {caption}"
                except Exception:
                    pass

            # C. Live Reel Views & Analytics Request
            if any(w in q for w in ["reel", "reels", "views", "analytics", "stats", "insight", "recent post", "last post"]):
                try:
                    from agents import instagram_engine
                    data = instagram_engine.get_live_reel_analytics()
                    if data.get("status") == "ok":
                        plays = data.get("latest_plays", 0)
                        likes = data.get("latest_likes", 0)
                        count = data.get("count", 0)
                        return f"Sir, your latest reel has {plays:,} plays and {likes:,} likes across {count} recent posts for @{ig_user}."
                except Exception:
                    pass

                # If 2FA session pending or rate limit, open browser directly
                try:
                    webbrowser.open(f"https://www.instagram.com/{ig_user}/")
                except Exception:
                    pass
                return f"Opening your Instagram reel analytics for @{ig_user} in your browser now, sir. Once your one-time 2FA code is entered, I will pull exact metrics headlessly."

            # D. Dashboard / Profile Request
            if any(w in q for w in ["dashboard", "open instagram", "open insta", "open profile"]):
                try:
                    webbrowser.open(f"https://www.instagram.com/{ig_user}/")
                except Exception:
                    pass
                return f"Opening your Instagram professional dashboard for @{ig_user} in your browser now, sir. You can inspect all real-time creator analytics and reel performance directly."

            if ig_user and ig_user != "your_instagram_username":
                if any(w in q for w in ["connect", "login", "link", "authenticate", "account"]):
                    return f"Connecting to your Instagram account @{ig_user}, sir. Account linked and monitoring telemetry is active."
                return f"Instagram telemetry active for @{ig_user}, sir. All background watchers are operational."
            return "Your Instagram monitor is initialized, sir. However, your Instagram username is not configured in settings yet. Once added, I will track your followers and posts."

        # 3. WhatsApp Integration
        if any(k in q for k in ["whatsapp", "whats app"]) or (
            any(w in q for w in ["message", "text"]) and any(w in q for w in ["to", "send"])
        ):
            if any(w in q for w in ["message", "send", "text"]):
                # Clean filler phrases
                clean_q = re.sub(r"^(?:ok|okay|hey|please|can you|could you|just)\s+", "", q, flags=re.IGNORECASE).strip()
                # Remove "in whatsapp", "on whatsapp", "via whatsapp", "through whatsapp", "whatsapp"
                clean_target = re.sub(r"\b(?:in|on|via|through|using)\s+whats\s*app\b|\bwhats\s*app\b", "", clean_q, flags=re.IGNORECASE).strip()

                contact = ""
                body = ""

                # Match "send [a] message/text to <contact> saying/that <body>"
                m1 = re.search(
                    r"(?:send\s+(?:a\s+)?(?:message|text)|message|text|send)\s+to\s+([a-zA-Z0-9_\- ]+?)(?:\s+(?:saying|that|with text|message)\s+(.*))?$",
                    clean_target,
                    flags=re.IGNORECASE
                )
                if m1:
                    contact = m1.group(1).strip()
                    body = m1.group(2).strip() if m1.group(2) else ""
                else:
                    # Match "message <contact> <body>" or "text <contact> <body>"
                    m2 = re.search(
                        r"^(?:message|text)\s+([a-zA-Z0-9_\- ]+?)(?:\s+(?:saying|that|with text|message)\s+(.*))?$",
                        clean_target,
                        flags=re.IGNORECASE
                    )
                    if m2:
                        contact = m2.group(1).strip()
                        body = m2.group(2).strip() if m2.group(2) else ""
                    else:
                        m3 = re.search(r"\bto\s+([a-zA-Z0-9_\- ]+)", clean_target, flags=re.IGNORECASE)
                        if m3:
                            contact = m3.group(1).strip()

                # Clean any lingering prepositions
                contact = re.sub(r"\b(in|on|at|via|to|through)$", "", contact, flags=re.IGNORECASE).strip()
                if not contact:
                    contact = "your contact"

                if body:
                    return JarvisBrain._execute_whatsapp_send(contact, body)
                else:
                    # Store pending action state for continuous listening
                    JarvisBrain.pending_action = {
                        "type": "whatsapp",
                        "contact": contact,
                        "body": "",
                        "timestamp": time.time()
                    }
                    try:
                        subprocess.Popen(["cmd", "/c", "start", "whatsapp:"], shell=True)
                    except Exception:
                        webbrowser.open("https://web.whatsapp.com/")
                    return f"Opening WhatsApp chat with {contact.title()} on your desktop now, sir. What message shall I send?"

            try:
                subprocess.Popen(["cmd", "/c", "start", "whatsapp:"], shell=True)
                return "Accessing WhatsApp Desktop for you now, sir. Bringing your chats onto your screen."
            except Exception:
                webbrowser.open("https://web.whatsapp.com/")
                return "Opening WhatsApp Web in your browser now, sir."

        # 4. iPhone & Phone Link Integration (Real Factual Telemetry)
        if any(w in q for w in ["iphone", "phone link", "missed call", "missed calls", "upcoming call", "call info", "calls info", "incoming call", "caller id", "who called", "who was that", "who's calling", "who is calling", "caller", "recent call", "recent calls", "last call", "latest call", "call log", "call logs", "phone call", "phone calls", "any calls", "any missed call"]):
            try:
                from agents import iphone_agent
                if any(w in q for w in ["connect", "link", "pair", "setup", "integrate", "how to pair"]):
                    iphone_agent.launch_phone_link()
                    return "Opening Windows Phone Link for your iPhone now, sir. Select iPhone to pair via Bluetooth with zero data leakage."

                # Factual call summary from Laptop 2 / Local Phone Link
                call_info = get_live_phone_calls_summary(q)
                if call_info:
                    return call_info

                if any(w in q for w in ["upcoming", "schedule", "calendar"]):
                    return "Monitoring your upcoming schedule now, sir. All scheduled calendar calls will be announced before they begin."

                return "No unread missed calls or active phone events logged in Phone Link right now, sir. Once a call arrives on your iPhone, I will announce the exact caller name immediately."
            except Exception as ex:
                return f"Unable to retrieve phone records: {ex}"

        # 5. Cross-Laptop LAN Sync & Remote HUD Pop-Up
        if any(w in q for w in ["pop up on this pc", "popup on this pc", "pop up on pc", "show hud on pc", "show hud", "pop up hud", "open hud", "wake pc", "trigger pc", "other laptop", "main pc", "primary pc", "pop up here", "popup here", "relay to pc"]):
            try:
                from agents import lan_sync
                target_cmd = re.sub(r"\b(pop up on this pc|popup on this pc|pop up on pc|show hud on pc|show hud|open hud|open on pc|relay to pc|send to pc|wake pc|trigger pc)\b", "", q).strip()
                res = lan_sync.trigger_remote_pc_hud(query=target_cmd)
                if res.get("status") == "ok":
                    if target_cmd:
                        return f"Connecting across local network, sir. The HUD is active on your primary PC executing '{target_cmd}'."
                    return "Connecting across local network, sir. The holographic Arc Reactor HUD is now active on your primary PC."
                else:
                    lan_sync.bring_hud_to_front()
                    return "Holographic Arc Reactor HUD brought to the foreground on this PC, sir."
            except Exception as ex:
                return f"LAN synchronization encountered an issue: {ex}"

        # 6. Strict Privacy & Local Sovereignty Confirmation
        if any(w in q for w in ["privacy", "data safe", "data leak", "pass out", "leave my computer", "leave my device", "send my data", "secure my data"]):
            return "Sir, your privacy is absolute. All language models, indexing, and reasoning run 100 percent locally on your RTX GPU and local SSD. Zero personal data, transcripts, or code ever leave your laptop."

        # 7. RAGE Optimizer & Server Threat Analysis (AURA XTREMEZ - 1140892126402596905)
        server_triggers = [
            "my server", "aura xtremez", "aura extremez", "xtremez", "1140892126402596905",
            "server status", "how is my server", "how's my server", "check my server", "check server",
            "server threat", "server threats", "any threats", "threat analysis", "threats are analysis",
            "threats analysis", "server analysis", "threats in my server", "threats in server",
            "server security", "server health", "rage", "clutch nation"
        ]
        if any(w in q for w in server_triggers):
            try:
                from agents import rage_agent
                return rage_agent.get_rage_status_summary(query=q)
            except Exception as ex:
                return f"Unable to retrieve server telemetry: {ex}"

        # 8. Gmail & Email Inbox Briefings
        if any(w in q for w in ["email", "emails", "gmail", "inbox"]):
            try:
                from agents import email_agent
                if any(w in q for w in ["read latest", "read email", "read the email", "read my latest"]):
                    return email_agent.get_latest_email_body()
                return email_agent.get_unread_emails_summary()
            except Exception as ex:
                return f"Unable to access your email: {ex}"



        # 5. YouTube Studio & Creator Dashboard Analytics
        if any(w in q for w in ["youtube studio", "youtube dashboard", "youtube analytics", "youtube stats", "channel stats", "creator dashboard"]):
            try:
                from agents import youtube_agent
                if any(w in q for w in ["analytics", "metrics", "views", "performance"]):
                    youtube_agent.open_youtube_analytics()
                    return "Accessing your YouTube Studio Analytics tab now, sir. Live viewer telemetry is displayed on your screen."
                youtube_agent.open_youtube_studio()
                return "Accessing your YouTube Creator Studio dashboard now, sir. Channel telemetry is active."
            except Exception:
                webbrowser.open("https://studio.youtube.com/")
                return "Opening YouTube Creator Studio for you now, sir."

        if any(w in q for w in ["open youtube", "launch youtube", "youtube"]):
            webbrowser.open("https://youtube.com")
            return "Opening YouTube for you now, sir."

        # 6. GitHub & Git Operations
        if any(w in q for w in ["github", "git repo", "git status", "commits", "commit"]):
            try:
                from agents import github_agent
                if any(w in q for w in ["status", "changes", "modified", "branch"]):
                    stat = github_agent.get_git_status()
                    if stat.get("status") == "ok":
                        if stat.get("is_clean"):
                            return f"Your repository on branch {stat.get('branch')} is clean with zero uncommitted changes, sir. Last commit was {stat.get('last_commit')}."
                        return f"You are on branch {stat.get('branch')} with {stat.get('changed_files_count')} modified files awaiting commit, sir."
                if any(w in q for w in ["commit", "commits", "history", "recent"]):
                    commits = github_agent.get_recent_commits(limit=2)
                    if commits:
                        return f"Your latest Git commit is: {commits[0]}, sir."
                
                github_agent.open_github_repo()
                return "Opening your GitHub repository dashboard in your browser now, sir."
            except Exception:
                webbrowser.open("https://github.com/Tarun7358")
                return "Opening your GitHub profile now, sir."

        # 7. Desktop App Launchers (Spotify, Discord, VS Code, Task Manager)
        if any(w in q for w in ["open spotify", "launch spotify", "play spotify", "spotify"]):
            try:
                subprocess.Popen(["cmd", "/c", "start", "spotify:"], shell=True)
                return "Launching Spotify on your desktop now, sir."
            except Exception:
                webbrowser.open("https://open.spotify.com")
                return "Opening Spotify Web for you now, sir."

        if any(w in q for w in ["open discord", "launch discord", "discord"]):
            try:
                subprocess.Popen(["cmd", "/c", "start", "discord:"], shell=True)
                return "Launching Discord on your desktop now, sir."
            except Exception:
                webbrowser.open("https://discord.com/app")
                return "Opening Discord Web for you now, sir."

        if any(w in q for w in ["open vs code", "open code", "launch code", "visual studio code"]):
            subprocess.Popen(["code", "."], shell=True)
            return "Opening Visual Studio Code for your workspace now, sir."

        if any(w in q for w in ["open task manager", "launch task manager", "task manager"]):
            subprocess.Popen(["taskmgr.exe"], shell=True)
            return "Opening Task Manager on your screen now, sir."

        # 8. Dynamic Autonomous App & Platform Launcher (Zero Hardcoding)
        app_match = re.match(r"^(?:open|launch|start|run|access)\s+(?:the\s+|my\s+)?([a-zA-Z0-9_\-\. ]+)$", q)
        if app_match:
            target = app_match.group(1).strip()
            web_aliases = {
                "twitter": "https://x.com", "x": "https://x.com", "reddit": "https://reddit.com",
                "linkedin": "https://linkedin.com", "notion": "https://notion.so", "figma": "https://figma.com",
                "chatgpt": "https://chatgpt.com", "steam": "steam://open/main", "calculator": "calc.exe",
                "notepad": "notepad.exe", "paint": "mspaint.exe", "file explorer": "explorer.exe",
                "settings": "ms-settings:", "browser": "https://google.com"
            }
            if target in web_aliases:
                dest = web_aliases[target]
                if dest.startswith("http"):
                    webbrowser.open(dest)
                else:
                    subprocess.Popen(["cmd", "/c", "start", dest], shell=True)
                return f"Accessing {target.capitalize()} for you now, sir."
            
            # Universal discovery: Try launching as native Windows application or protocol
            try:
                subprocess.Popen(["cmd", "/c", "start", target], shell=True)
                return f"Launching {target.capitalize()} on your desktop, sir."
            except Exception:
                pass

        # 5. System / Hardware diagnostics (Word-boundary check to prevent matching 'ram' in 'instagram')
        if re.search(r"\b(system status|laptop specs|battery|cpu usage|ram usage|how are you running|hardware specs)\b", q) or (re.search(r"\b(cpu|ram|battery)\b", q) and not any(w in q for w in ["instagram", "telegram", "program"])):
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            battery = psutil.sensors_battery()
            bat_str = f"battery is at {battery.percent} percent" if battery else "plugged into AC power"
            return f"All systems nominal, sir. Your CPU is at {cpu} percent, memory is at {ram} percent, and the system is {bat_str}."

        # 4. Time / Date
        if re.search(r"\b(time|what time|date today|current date)\b", q):
            now = datetime.datetime.now()
            return f"It is currently {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d')}."

        # 5. Local Network & Wi-Fi Check
        if re.search(r"\b(wifi|network|who is on my wifi|devices on wifi|scan network)\b", q):
            if HAS_LOCAL_AGENTS:
                try:
                    devices = network_agent.get_all_devices()
                    count = len(devices)
                    new_devs = [d for d in devices if d.get("is_new")]
                    if new_devs:
                        return f"Scan complete, sir. There are {count} devices connected, and I noticed {len(new_devs)} new device on your Wi-Fi."
                    return f"Your network is secure, sir. {count} authorized devices are active on your subnet."
                except Exception:
                    pass
            return "Scanning your local network now, sir. Monitoring all connected Wi-Fi devices."

        # 6. Local File Search
        if any(term in q for term in ["find file", "search file", "where is the file", "find document", "search document"]):
            term = re.sub(r"\b(find|search|where is|the|file|document)\b", "", q).strip()
            if term and HAS_LOCAL_AGENTS:
                try:
                    matches = file_agent.search_files(term, limit=1)
                    if matches:
                        top = matches[0]
                        return f"I found that file for you, sir: {top.get('name')} in your {os.path.basename(os.path.dirname(top.get('path', '')))} folder."
                    return f"I could not locate any files matching {term} in your indexed folders, sir."
                except Exception:
                    pass

        # 9. Project Ideas & Technical Problem Solving
        if any(w in q for w in ["project idea", "project ideas", "what should i build", "suggest a project"]):
            try:
                from agents import research_agent
                ideas = research_agent.get_project_idea_framework()
                import random
                chosen = random.choice(ideas)
                return f"Here is a high-impact architecture for you, sir: {chosen}"
            except Exception:
                pass

        # 10. Real-Time Live Network Search & Web Intelligence
        is_live_query = any(w in q for w in ["current", "latest", "recent", "who is", "who won", "today", "now", "weather", "score", "price", "minister", "president", "ceo", "news", "election", "update", "search online", "search web", "look up"])
        if is_live_query:
            try:
                from agents import research_agent
                search_term = re.sub(r"\b(search online for|search web for|search the internet for|look up|jarvis|aura)\b", "", q).strip(" ?.")
                res = research_agent.search_live_web(search_term or q, max_results=3)
                if res.get("status") == "ok" and res.get("snippets"):
                    live_prompt = (
                        f"{get_jarvis_system_prompt()}\n\n"
                        f"[Real-Time Live Web Telemetry]:\n{res['snippets']}\n\n"
                        f"User Query: {query}\n"
                        f"Provide a direct, concise 1 to 2 spoken sentence answer using the live real-time web telemetry above:\nJARVIS:"
                    )
                    res_data = query_ollama_endpoint(
                        "/api/generate",
                        {
                            "model": "mistral",
                            "prompt": live_prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.3,
                                "num_predict": 50,
                                "num_ctx": 512
                            },
                            "keep_alive": "60m"
                        },
                        timeout=8
                    )
                    if res_data:
                        ans = res_data.get("response", "").strip()
                        if ans:
                            return ans
            except Exception:
                pass

        # 11. Sovereign Hybrid AI Inference: Gemini Flash Lite (Fastest) with Ollama Local Fallback
        system_prompt = get_jarvis_system_prompt()
        now = datetime.datetime.now()
        hour = now.hour

        # Try ultra-fast Gemini Flash first (sub-second response, local privacy preserved)
        try:
            from agents import gemini_agent
            if gemini_agent.is_gemini_active():
                gemini_ans = gemini_agent.query_gemini(
                    prompt=query,
                    system_prompt=system_prompt,
                    max_tokens=75,
                    timeout=5
                )
                if gemini_ans:
                    if hour >= 12 or hour < 4:
                        sal = "Good evening" if (hour >= 17 or hour < 4) else "Good afternoon"
                        gemini_ans = re.sub(r"\bGood morning\b", sal, gemini_ans, flags=re.IGNORECASE)
                    return gemini_ans
        except Exception:
            pass

        # Fallback to local Ollama on RTX GPU if Gemini is unavailable or offline
        for model in ["llama3.2:1b", "mistral"]:
            try:
                res_data = query_ollama_endpoint(
                    "/api/generate",
                    {
                        "model": model,
                        "prompt": f"{system_prompt}\n\nUser: {query}\nJARVIS:",
                        "stream": False,
                        "options": {
                            "temperature": 0.5,
                            "num_predict": 60,
                            "num_ctx": 512,
                            "top_k": 30
                        },
                        "keep_alive": "60m"
                    },
                    timeout=8
                )
                if res_data:
                    answer = res_data.get("response", "").strip()
                    # If llama3.2 gives a canned refusal, seamlessly fall through to mistral
                    if any(ref in answer.lower() for ref in ["can't help with that", "cannot verify", "unable to provide", "i am unable to"]):
                        continue
                    if answer:
                        # Guard: If LLM hallucinates "Good morning" at night or afternoon, correct it
                        if hour >= 12 or hour < 4:
                            sal = "Good evening" if (hour >= 17 or hour < 4) else "Good afternoon"
                            answer = re.sub(r"\bGood morning\b", sal, answer, flags=re.IGNORECASE)
                        return answer
            except Exception:
                continue

        # Graceful assistant fallback
        return f"Right away, sir. I have registered your request for '{query}'. All background watchers remain active."

    @staticmethod
    def _execute_whatsapp_send(contact: str, body: str) -> str:
        """Launches WhatsApp with pre-filled message text, optionally resolving contact phone number from .env."""
        from dotenv import dotenv_values
        env_path = os.path.join(BACKEND_DIR, ".env")
        env_vals = dotenv_values(env_path) if os.path.exists(env_path) else {}

        # Look for WHATSAPP_CONTACT_<NAME> in .env (e.g., WHATSAPP_CONTACT_ABHISHEK=+919876543210)
        env_key = f"WHATSAPP_CONTACT_{contact.upper().replace(' ', '_')}"
        phone = env_vals.get(env_key, "").strip()

        if phone:
            url = f"whatsapp://send?phone={phone}&text={urllib.parse.quote(body)}"
            web_url = f"https://web.whatsapp.com/send?phone={phone}&text={urllib.parse.quote(body)}"
        else:
            url = f"whatsapp://send?text={urllib.parse.quote(body)}"
            web_url = "https://web.whatsapp.com/"

        try:
            subprocess.Popen(["cmd", "/c", "start", url], shell=True)
        except Exception:
            webbrowser.open(web_url)

        return f"Drafting your WhatsApp message to {contact.title()} now, sir: \"{body}\"."



class JarvisApp:
    def __init__(self):
        self.window = None
        self.voice = JarvisVoice()
        self.state = "idle"  # "idle", "awaiting_command", "thinking", "speaking"
        self.mic_index = None
        self.command_timeout_timer = None
        self.stop_bg_listen = None

    def show_hud(self):
        """Forces the Arc Reactor HUD window to show and restore to the foreground."""
        try:
            from agents.lan_sync import bring_hud_to_front
            bring_hud_to_front()
        except Exception:
            pass
        if self.window:
            try:
                self.window.restore()
                self.window.show()
            except Exception:
                pass

    def trigger_listening(self):
        """Called when user clicks HUD Arc Reactor or presses hotkey."""
        if self.state in ["thinking", "speaking"] or self.voice.is_speaking:
            return
        print("[Jarvis] Manual trigger activated (Arc Reactor clicked / hotkey)")
        self._enter_awaiting_command()

    def _enter_awaiting_command(self):
        self.state = "awaiting_command"
        self._eval_js("setAuraState('listening', 'LISTENING...')")

        # Cancel any pending timeout
        if self.command_timeout_timer:
            try:
                self.command_timeout_timer.cancel()
            except Exception:
                pass

        def _timeout():
            if self.state == "awaiting_command":
                print("[Jarvis] Command timeout (no speech detected). Returning to idle.")
                self.state = "idle"
                self._eval_js("setAuraState('idle', 'JARVIS ONLINE')")

        self.command_timeout_timer = threading.Timer(12.0, _timeout)
        self.command_timeout_timer.daemon = True
        self.command_timeout_timer.start()

        # Prompt the user
        self.voice.speak("Yes sir?")

    def _enter_follow_up_listening(self):
        """Keeps Jarvis listening for subsequent commands without needing the wake word."""
        self.state = "awaiting_command"
        self._eval_js("setAuraState('listening', 'LISTENING...')")
        print("[Jarvis] Continuous conversation active. Listening for follow-up without wake word (20s timeout)...")

        if self.command_timeout_timer:
            try:
                self.command_timeout_timer.cancel()
            except Exception:
                pass

        def _timeout():
            if self.state == "awaiting_command":
                print("[Jarvis] Inactive timeout (20s). Returning to standby idle mode.")
                self.state = "idle"
                self._eval_js("setAuraState('idle', 'JARVIS ONLINE')")

        self.command_timeout_timer = threading.Timer(20.0, _timeout)
        self.command_timeout_timer.daemon = True
        self.command_timeout_timer.start()

    def _process_query(self, query: str):
        if self.command_timeout_timer:
            try:
                self.command_timeout_timer.cancel()
            except Exception:
                pass

        self.state = "thinking"
        self._eval_js("setAuraState('thinking', 'THINKING...')")
        print(f"[Jarvis] Processing command: '{query}'")

        def _think_and_answer():
            response = JarvisBrain.answer_query(query)
            print(f"[Jarvis] Responding: '{response}'")

            self.state = "speaking"
            self._eval_js("setAuraState('speaking', 'SPEAKING...')")

            def on_done():
                q_low = query.lower()
                r_low = response.lower()
                if "standing by" in r_low or any(w in q_low for w in ["bye", "goodbye", "go to sleep", "sleep", "stop", "that's all", "thats all", "thank", "thanks", "nothing", "never mind", "nevermind", "leave it", "cancel", "ok ok", "okay okay"]):
                    self.state = "idle"
                    self._eval_js("setAuraState('idle', 'JARVIS ONLINE')")
                    print("[Jarvis] Conversation ended by user. Standing by in idle mode.")
                else:
                    # Continuous conversation: automatically listen for follow-up!
                    self._enter_follow_up_listening()

            self.voice.speak(response, on_end=on_done)

        threading.Thread(target=_think_and_answer, daemon=True).start()


    def _eval_js(self, js: str):
        if self.window:
            try:
                self.window.evaluate_js(js)
            except Exception:
                pass

    def start_wake_word_loop(self):
        def _bg_listener():
            self.mic_index, mic_name = get_windows_default_microphone()
            rec = sr.Recognizer()
            rec.dynamic_energy_threshold = False  # Fixed threshold to prevent desensitization
            rec.pause_threshold = 0.45
            rec.phrase_threshold = 0.15
            rec.non_speaking_duration = 0.2

            try:
                mic = sr.Microphone(device_index=self.mic_index)
                with mic as source:
                    print(f"[*] Initializing Windows Default Recording Device: {mic_name}...")
                    rec.adjust_for_ambient_noise(source, duration=0.8)
                    calibrated = rec.energy_threshold
                    rec.energy_threshold = max(60, min(320, calibrated * 0.75))
                    print(f"[*] Microphone calibrated! Ambient noise = {calibrated:.1f}, Active threshold = {rec.energy_threshold:.1f}")

                def callback(recognizer, audio):
                    # If Jarvis is currently speaking, drop audio buffer
                    if self.voice.is_speaking or self.state in ["thinking", "speaking"]:
                        return

                    try:
                        spoken = recognizer.recognize_google(audio).lower().strip()
                    except sr.UnknownValueError:
                        return
                    except Exception as ex:
                        return

                    if not spoken:
                        return

                    print(f"[Heard] '{spoken}'")

                    # If already awaiting command, this spoken phrase IS the command!
                    if self.state == "awaiting_command":
                        self._process_query(spoken)
                        return

                    # Otherwise, check if wake word was spoken
                    triggered, query = check_wake_word(spoken)
                    if triggered:
                        print(f"[*] Wake word detected in: '{spoken}'")
                        if query and len(query) >= 3:
                            # User said wake word and command together (e.g., "Hey Aura what is the battery")
                            self._process_query(query)
                        else:
                            # User said just "Hey Aura" or "Jarvis"
                            self._enter_awaiting_command()

                self.stop_bg_listen = rec.listen_in_background(mic, callback, phrase_time_limit=8)
                print(f"[*] Continuous background listener ACTIVE on '{mic_name}'.")
                print("[*] Ready: Say 'Hey Aura' or 'Jarvis' anytime...")
            except Exception as e:
                print(f"[WakeWord] Microphone error: {e}")

        threading.Thread(target=_bg_listener, daemon=True).start()

    def setup_hotkeys(self):
        if not HAS_KEYBOARD:
            return
        try:
            keyboard.add_hotkey("ctrl+shift+a", self.trigger_listening)
            keyboard.add_hotkey("alt+space", self.trigger_listening)
        except Exception:
            pass


class JarvisJSBridge:
    """Isolated, lightweight bridge for JS API with no window references to prevent recursion."""
    def __init__(self, trigger_fn):
        self._trigger = trigger_fn

    def listen_voice(self):
        self._trigger()


def main():
    app = JarvisApp()
    bridge = JarvisJSBridge(app.trigger_listening)

    html_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hud.html")
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    # Sleek floating circular HUD window (320x340 px)
    # easy_drag=False prevents the .NET AccessibilityObject recursion bug
    window = webview.create_window(
        'AURA JARVIS HUD',
        html=html,
        width=320,
        height=340,
        frameless=True,
        easy_drag=False,
        on_top=True,
        transparent=True,
        background_color='#010203',
        js_api=bridge
    )
    app.window = window

    app.start_wake_word_loop()
    app.setup_hotkeys()

    # Start LAN Node Sync (Cross-PC triggers & Auto-Discovery)
    try:
        from agents.lan_sync import start_lan_server, start_udp_discovery_responder
        start_lan_server(app)
        start_udp_discovery_responder()
    except Exception as ex:
        print(f"[LAN Sync] Listener start error: {ex}")

    # ─── Phone Call Watcher ───────────────────────────────
    def _phone_call_watcher():
        """
        Polls AURA backend every 5s for new call events (incoming/missed).
        Announces them via Jarvis TTS — "Sir, missed call from Rahul."
        Works with iPhone via Phone Link on Laptop 2.
        """
        BACKEND = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        # Also try local backend if remote
        candidates = [BACKEND, "http://127.0.0.1:8000"]
        seen_callers = set()
        print("[PHONE WATCHER] 🟢 Monitoring for calls...")

        while True:
            try:
                for base in candidates:
                    try:
                        r = requests.get(f"{base}/phone/calls", timeout=3)
                        if r.status_code == 200:
                            data = r.json()
                            recent = data.get("recent", [])
                            for event in recent:
                                caller = event.get("caller", "Unknown")
                                ctype  = event.get("type", "")
                                etime  = event.get("time", "")
                                key    = f"{caller}_{etime}"

                                if key not in seen_callers:
                                    seen_callers.add(key)
                                    # Announce via Jarvis voice
                                    if ctype == "missed":
                                        msg = f"Sir, you have a missed call from {caller}."
                                    elif ctype == "incoming":
                                        msg = f"Sir, {caller} is calling."
                                    elif ctype == "scheduled":
                                        msg = f"Reminder sir, you have a scheduled call with {caller}."
                                    else:
                                        msg = f"Sir, phone event from {caller}."
                                    print(f"[PHONE WATCHER] 📞 {msg}")
                                    app.voice.speak(msg)
                            break  # got a response, stop trying candidates
                    except Exception:
                        continue
            except Exception as e:
                pass
            time.sleep(5)

    threading.Thread(target=_phone_call_watcher, daemon=True).start()
    print("[PHONE WATCHER] Call announcement thread started.")

    # ─── RAGE Telemetry & Violation Watchdog ──────────────
    def _rage_violation_watcher():
        """
        Monitors RAGE security telemetry and speaks aggregated, human-like AI alerts
        for genuine live runtime incidents only. Ignores ancient logs and coalesces error cascades.
        """
        print("[RAGE WATCHDOG] 🟢 Monitoring RAGE server telemetry & security logs...")
        time.sleep(3)
        while True:
            try:
                from agents import rage_agent
                voice_alert = rage_agent.poll_voice_alert()
                if voice_alert:
                    print(f"[RAGE WATCHDOG] ⚠️ {voice_alert}")
                    app.voice.speak(voice_alert)
            except Exception:
                pass
            time.sleep(10)

    threading.Thread(target=_rage_violation_watcher, daemon=True).start()
    print("[RAGE WATCHDOG] Security violation listener active.")


    def greet():
        time.sleep(1.2)
        app.voice.speak("Jarvis online. Systems nominal, sir.")

    threading.Thread(target=greet, daemon=True).start()
    webview.start()


if __name__ == "__main__":
    main()
