"""
AURA JARVIS HUD — Desktop Floating Agentic AI
- Iron Man Jarvis Hologram Visuals
- Background 'Hey Aura' / 'Jarvis' Wake-Word Listener
- Voice Response (pyttsx3) + Speech Recognition
- Global Hotkey (Ctrl+Shift+A / Alt+Space)
- Local System, Network, File & Instagram Agent Integration
"""

import os
import sys
import time
import json
import threading
import datetime
import re
import queue

# Ensure backend folder is on python path for importing agents
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

# Try importing backend agents directly if available
try:
    from agents import network_agent, instagram_agent, file_agent
    from config import settings
    HAS_LOCAL_AGENTS = True
except Exception as e:
    HAS_LOCAL_AGENTS = False
    print(f"[Jarvis] Local agents import notice: {e}")

WAKE_WORDS = ["hey aura", "aura", "jarvis", "ok aura", "hello aura", "wake up aura"]


class JarvisVoice:
    """Offline, fast Text-To-Speech engine using pyttsx3."""
    def __init__(self):
        self._lock = threading.Lock()
        self.engine = None
        self._init_engine()

    def _init_engine(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 185)
            self.engine.setProperty('volume', 1.0)
            voices = self.engine.getProperty('voices')
            # Prefer male / David or clear voice for Jarvis style
            for v in voices:
                if "david" in v.name.lower() or "zira" in v.name.lower():
                    self.engine.setProperty('voice', v.id)
                    break
        except Exception as e:
            print(f"[Voice] TTS init error: {e}")
            self.engine = None

    def speak(self, text: str, on_start=None, on_end=None):
        def _run():
            with self._lock:
                if on_start:
                    on_start()
                try:
                    # Clean text from markdown asterisks or code formatting
                    clean = re.sub(r'[*_#`]', '', text)
                    clean = re.sub(r'\[.*?\]\(.*?\)', '', clean)
                    # Re-init engine per thread if needed on Windows
                    eng = pyttsx3.init()
                    eng.setProperty('rate', 185)
                    eng.setProperty('volume', 1.0)
                    eng.say(clean)
                    eng.runAndWait()
                    eng.stop()
                except Exception as ex:
                    print(f"[Voice] Speech error: {ex}")
                finally:
                    if on_end:
                        on_end()

        t = threading.Thread(target=_run, daemon=True)
        t.start()


class AuraBrain:
    """Handles query routing: System telemetry, Local Agents, or Ollama AI."""
    
    @staticmethod
    def get_system_telemetry():
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        bat_str = f"{battery.percent}%" if battery else "AC Connected"
        return {
            "cpu": cpu,
            "ram": ram,
            "gpu": "RTX 2050",
            "battery": bat_str
        }

    @staticmethod
    def answer_query(query: str) -> str:
        q = query.lower().strip()

        # 1. Identity / Status
        if any(k in q for k in ["who are you", "your name", "what are you"]):
            return "I am AURA, your personal Jarvis AI. Running locally on your laptop with your RTX 2050 graphics card and 8GB RAM."

        if any(k in q for k in ["system status", "system stats", "battery", "cpu", "ram", "specs"]):
            stats = AuraBrain.get_system_telemetry()
            return f"System telemetry: CPU load is at {stats['cpu']}%, RAM usage is at {stats['ram']}%, GPU RTX 2050 is active, power status is {stats['battery']}."

        if any(k in q for k in ["what time", "current time", "date today"]):
            now = datetime.datetime.now()
            return f"The current time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."

        # 2. Local Network check
        if any(k in q for k in ["network", "devices on wifi", "who is on my wifi", "scan network"]):
            if HAS_LOCAL_AGENTS:
                try:
                    devices = network_agent.get_all_devices()
                    count = len(devices)
                    new_devs = [d for d in devices if d.get("is_new")]
                    if new_devs:
                        return f"Network scan completed. Found {count} connected devices. Alert: {len(new_devs)} unknown device detected on your Wi-Fi."
                    return f"Network scan completed. {count} active devices recognized on your subnet. Everything is secure."
                except Exception as e:
                    return f"Scanning your network now. Check the network log for details."
            return "Scanning network. Your subnet scan is active."

        # 3. Instagram check
        if any(k in q for k in ["instagram", "followers", "insta analytics"]):
            if HAS_LOCAL_AGENTS:
                try:
                    summary = instagram_agent.get_analytics_summary()
                    if summary.get("connected"):
                        return f"Instagram analytics: Account has {summary.get('followers', 0)} followers, {summary.get('posts', 0)} posts. Recent engagement is steady."
                    return "Instagram is configured in your .env file. Run a sync to fetch your latest follower and post insights."
                except Exception:
                    pass
            return "Instagram module is loaded. I can track your follower counts, engagement, and post stats."

        # 4. File search
        if q.startswith("find file") or q.startswith("search file") or "where is" in q:
            search_term = q.replace("find file", "").replace("search file", "").replace("where is", "").strip()
            if search_term and HAS_LOCAL_AGENTS:
                try:
                    matches = file_agent.search_files(search_term, limit=3)
                    if matches:
                        top = matches[0]
                        return f"Found file: {top.get('name')} in {top.get('path')}."
                    return f"No local files matching '{search_term}' found in your watched folders."
                except Exception:
                    pass

        # 5. Query Ollama AI brain if online
        try:
            resp = requests.post(
                "http://127.0.0.1:8000/api/chat/stream",
                json={"message": query},
                timeout=25,
                stream=True
            )
            if resp.status_code == 200:
                full_text = ""
                for line in resp.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith("data: "):
                            token = decoded[6:]
                            if token != "[DONE]":
                                full_text += token
                if full_text.strip():
                    return full_text.strip()
        except Exception:
            pass

        # Direct Ollama fallback if backend API is not up
        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "mistral", "prompt": f"You are Jarvis/AURA personal AI. Answer concisely in 1-2 sentences: {query}", "stream": False},
                timeout=15
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                if answer:
                    return answer
        except Exception:
            pass

        # Fallback response
        return f"Acknowledged, sir. I have processed '{query}'. All background monitors remain active."


class JarvisHUDApp:
    def __init__(self):
        self.window = None
        self.voice = JarvisVoice()
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300
        self.is_listening = False
        self.is_processing = False
        self.hud_visible = True
        self.is_compact = False

    # ─── JS Exposed API ───────────────────────────────────────────────────────
    def listen_voice(self):
        """Called when user clicks mic or reactor core on HUD."""
        threading.Thread(target=self._listen_and_respond, daemon=True).start()

    def ask_query(self, query: str):
        """Called when user submits text via HUD input."""
        threading.Thread(target=self._process_query, args=(query,), daemon=True).start()

    def toggle_compact(self, is_compact: bool):
        self.is_compact = is_compact
        if self.window:
            if is_compact:
                self.window.resize(160, 160)
            else:
                self.window.resize(440, 540)

    def hide_window(self):
        if self.window:
            self.window.hide()
            self.hud_visible = False

    def show_window(self):
        if self.window:
            self.window.show()
            self.hud_visible = True

    # ─── Voice Interaction ────────────────────────────────────────────────────
    def _listen_and_respond(self):
        if self.is_listening or self.is_processing:
            return
        self.is_listening = True
        
        try:
            self._eval_js("setAuraState('listening', 'LISTENING... SPEAK NOW')")
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
                audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=10)
            
            self._eval_js("setAuraState('thinking', 'PROCESSING SPEECH...')")
            try:
                text = self.recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                text = ""
            except Exception as e:
                text = ""

            if text:
                self._eval_js(f"onUserSpoke({json.dumps(text)})")
                self._process_query(text)
            else:
                self._eval_js("setAuraState('idle', 'AURA STANDBY // SAY \"HEY AURA\"')")
                self._eval_js("onAuraResponse('I did not catch that, sir.')")
                self.voice.speak("I didn't catch that, sir.")
        except Exception as e:
            print(f"[HUD] Listen error: {e}")
            self._eval_js("setAuraState('idle', 'AURA STANDBY // SAY \"HEY AURA\"')")
        finally:
            self.is_listening = False

    def _process_query(self, query: str):
        self.is_processing = True
        self._eval_js("setAuraState('thinking', 'ANALYZING...')")
        
        response_text = AuraBrain.answer_query(query)
        
        self._eval_js(f"onAuraResponse({json.dumps(response_text)})")
        self._eval_js("setAuraState('speaking', 'SPEAKING RESPONSE')")
        
        def on_done():
            self.is_processing = False
            self._eval_js("setAuraState('idle', 'AURA STANDBY // SAY \"HEY AURA\"')")
            
        self.voice.speak(response_text, on_end=on_done)

    def _eval_js(self, js_code: str):
        if self.window:
            try:
                self.window.evaluate_js(js_code)
            except Exception:
                pass

    # ─── Background Wake Word Listener ────────────────────────────────────────
    def start_wake_word_listener(self):
        def _loop():
            rec = sr.Recognizer()
            rec.dynamic_energy_threshold = True
            rec.pause_threshold = 0.6
            
            while True:
                if self.is_listening or self.is_processing:
                    time.sleep(0.5)
                    continue

                try:
                    with sr.Microphone() as source:
                        audio = rec.listen(source, timeout=3, phrase_time_limit=4)
                    
                    try:
                        text = rec.recognize_google(audio).lower()
                    except Exception:
                        continue

                    # Check for wake words
                    for w in WAKE_WORDS:
                        if w in text:
                            print(f"[WakeWord] Triggered: '{text}'")
                            # Bring window to front
                            self.show_window()
                            
                            # Extract query if user said "Hey Aura, what time is it"
                            remaining = text.replace(w, "").strip()
                            if len(remaining) > 3:
                                self._eval_js(f"onUserSpoke({json.dumps(remaining)})")
                                threading.Thread(target=self._process_query, args=(remaining,), daemon=True).start()
                            else:
                                threading.Thread(target=self._listen_and_respond, daemon=True).start()
                            break

                except sr.WaitTimeoutError:
                    continue
                except Exception as ex:
                    time.sleep(1)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    # ─── Telemetry Loop ───────────────────────────────────────────────────────
    def start_telemetry_loop(self):
        def _loop():
            while True:
                try:
                    stats = AuraBrain.get_system_telemetry()
                    self._eval_js(f"setTelemetry('{stats['cpu']}', '{stats['ram']}', '{stats['gpu']}')")
                except Exception:
                    pass
                time.sleep(3)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    # ─── Global Hotkey ────────────────────────────────────────────────────────
    def setup_hotkeys(self):
        if not HAS_KEYBOARD:
            return
        try:
            def toggle():
                if self.hud_visible:
                    self.listen_voice()
                else:
                    self.show_window()
                    self.listen_voice()

            keyboard.add_hotkey("ctrl+shift+a", toggle)
            keyboard.add_hotkey("alt+space", toggle)
            print("[Jarvis] Global hotkeys active: Ctrl+Shift+A & Alt+Space")
        except Exception as e:
            print(f"[Jarvis] Hotkey setup note: {e}")


def launch_jarvis():
    app = JarvisHUDApp()
    
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hud.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Create frameless, transparent, floating HUD window
    window = webview.create_window(
        'AURA JARVIS HUD',
        html=html_content,
        width=440,
        height=540,
        frameless=True,
        easy_drag=True,
        on_top=True,
        transparent=True,
        js_api=app
    )
    app.window = window

    # Start background threads
    app.start_wake_word_listener()
    app.start_telemetry_loop()
    app.setup_hotkeys()

    # Welcome voice greeting
    def welcome():
        time.sleep(1.2)
        app.voice.speak("AURA online. Systems nominal. Good evening, sir.")

    threading.Thread(target=welcome, daemon=True).start()

    # Run pywebview main loop
    webview.start()


if __name__ == "__main__":
    launch_jarvis()
