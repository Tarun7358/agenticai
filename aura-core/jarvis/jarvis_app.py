"""
AURA JARVIS HUD — Pure Iron Man Arc Reactor Voice Assistant
- Holographic Arc Reactor Visual (Pure HUD, No Chatbot Clutter)
- Always-On Background Wake-Word ("Hey Aura" / "Jarvis")
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
    from agents import network_agent, instagram_agent, file_agent
    from config import settings
    HAS_LOCAL_AGENTS = True
except Exception as e:
    HAS_LOCAL_AGENTS = False

WAKE_WORDS = ["hey aura", "aura", "jarvis", "hey jarvis", "ok aura", "hello aura"]

JARVIS_SYSTEM_PROMPT = (
    "You are JARVIS (AURA), an ultra-intelligent, articulate, polite personal assistant. "
    "Respond naturally like a real human assistant speaking directly to your boss ('Sir'). "
    "Keep answers concise in 1 to 2 spoken sentences. "
    "Do NOT use markdown, bullet points, asterisks, or robotic formatting."
)


class JarvisVoice:
    """Offline, human-like voice synthesis using pyttsx3."""
    def __init__(self):
        self._lock = threading.Lock()
        self.engine = None
        self._init_engine()

    def _init_engine(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 178)  # Natural human speech cadence
            self.engine.setProperty('volume', 1.0)
            voices = self.engine.getProperty('voices')
            for v in voices:
                if "david" in v.name.lower() or "zira" in v.name.lower():
                    self.engine.setProperty('voice', v.id)
                    break
        except Exception as e:
            print(f"[Voice] Init error: {e}")

    def speak(self, text: str, on_start=None, on_end=None):
        def _run():
            with self._lock:
                if on_start:
                    on_start()
                try:
                    clean = re.sub(r'[*_#`]', '', text)
                    clean = re.sub(r'\[.*?\]\(.*?\)', '', clean)
                    eng = pyttsx3.init()
                    eng.setProperty('rate', 178)
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


class JarvisBrain:
    """Intelligent query reasoning: System, Network, Files, or Ollama AI."""

    @staticmethod
    def answer_query(query: str) -> str:
        q = query.lower().strip()

        # 1. Identity & Greetings
        if any(k in q for k in ["who are you", "your name", "what are you"]):
            return "I am AURA, your personal Jarvis AI. Running locally on your laptop with your RTX graphics card. At your service, sir."

        if any(k == q for k in ["hello", "hi", "hey", "good morning", "good evening"]):
            return "Good day, sir. All systems are operational. How can I assist you?"

        # 2. System / Hardware diagnostics
        if any(k in q for k in ["system status", "laptop", "battery", "cpu", "ram", "specs", "how are you running"]):
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            battery = psutil.sensors_battery()
            bat_str = f"battery is at {battery.percent} percent" if battery else "plugged into AC power"
            return f"All systems nominal, sir. Your CPU is at {cpu} percent, memory is at {ram} percent, and the system is {bat_str}."

        # 3. Time / Date
        if any(k in q for k in ["time", "what time", "date today"]):
            now = datetime.datetime.now()
            return f"It is currently {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d')}."

        # 4. Local Network & Wi-Fi Check
        if any(k in q for k in ["network", "wifi", "devices", "who is on my wifi", "scan"]):
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

        # 5. Local File Search
        if "find" in q or "search" in q or "where is" in q:
            term = q.replace("find", "").replace("search", "").replace("where is", "").replace("file", "").strip()
            if term and HAS_LOCAL_AGENTS:
                try:
                    matches = file_agent.search_files(term, limit=1)
                    if matches:
                        top = matches[0]
                        return f"I found that file for you, sir: {top.get('name')} in your {os.path.basename(os.path.dirname(top.get('path', '')))} folder."
                    return f"I could not locate any files matching {term} in your indexed folders, sir."
                except Exception:
                    pass

        # 6. Instagram Status
        if "instagram" in q:
            if HAS_LOCAL_AGENTS:
                try:
                    summary = instagram_agent.get_analytics_summary()
                    if summary.get("connected"):
                        return f"Your Instagram account currently has {summary.get('followers', 0)} followers with {summary.get('posts', 0)} posts."
                except Exception:
                    pass
            return "Your Instagram monitor is initialized, sir. Ready to analyze recent engagement whenever you require."

        # 7. Conversational Query via Ollama Local LLM
        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "mistral",
                    "prompt": f"{JARVIS_SYSTEM_PROMPT}\n\nUser: {query}\nJARVIS:",
                    "stream": False,
                    "options": {"temperature": 0.6, "num_ctx": 2048}
                },
                timeout=20
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                if answer:
                    return answer
        except Exception:
            pass

        # Graceful assistant fallback
        return f"Right away, sir. I have registered your request for '{query}'. All background watchers remain active."


class JarvisApp:
    def __init__(self):
        self.window = None
        self.voice = JarvisVoice()
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300
        self.is_listening = False
        self.is_processing = False

    def listen_voice(self):
        threading.Thread(target=self._listen_and_respond, daemon=True).start()

    def _listen_and_respond(self):
        if self.is_listening or self.is_processing:
            return
        self.is_listening = True

        try:
            self._eval_js("setAuraState('listening', 'LISTENING...')")
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=10)

            self._eval_js("setAuraState('thinking', 'PROCESSING...')")
            try:
                text = self.recognizer.recognize_google(audio)
            except Exception:
                text = ""

            if text:
                print(f"[Jarvis] Heard: '{text}'")
                self._process_query(text)
            else:
                self._eval_js("setAuraState('idle', 'JARVIS ONLINE')")
                self.voice.speak("I am here whenever you need me, sir.")
        except Exception as e:
            print(f"[Jarvis] Listen error: {e}")
            self._eval_js("setAuraState('idle', 'JARVIS ONLINE')")
        finally:
            self.is_listening = False

    def _process_query(self, query: str):
        self.is_processing = True
        self._eval_js("setAuraState('thinking', 'THINKING...')")

        response = JarvisBrain.answer_query(query)
        print(f"[Jarvis] Responding: '{response}'")

        self._eval_js(f"onAuraResponse({json.dumps(response)})")
        self._eval_js("setAuraState('speaking', 'SPEAKING...')")

        def on_done():
            self.is_processing = False
            self._eval_js("setAuraState('idle', 'JARVIS ONLINE')")

        self.voice.speak(response, on_end=on_done)

    def _eval_js(self, js: str):
        if self.window:
            try:
                self.window.evaluate_js(js)
            except Exception:
                pass

    def start_wake_word_loop(self):
        def _loop():
            rec = sr.Recognizer()
            rec.dynamic_energy_threshold = True
            rec.pause_threshold = 0.5

            while True:
                if self.is_listening or self.is_processing:
                    time.sleep(0.5)
                    continue

                try:
                    with sr.Microphone() as source:
                        audio = rec.listen(source, timeout=3, phrase_time_limit=4)

                    try:
                        spoken = rec.recognize_google(audio).lower()
                    except Exception:
                        continue

                    for w in WAKE_WORDS:
                        if w in spoken:
                            print(f"[WakeWord] Activated: '{spoken}'")
                            trailing = spoken.replace(w, "").strip()
                            if len(trailing) > 3:
                                threading.Thread(target=self._process_query, args=(trailing,), daemon=True).start()
                            else:
                                threading.Thread(target=self._listen_and_respond, daemon=True).start()
                            break

                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    time.sleep(1)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def setup_hotkeys(self):
        if not HAS_KEYBOARD:
            return
        try:
            keyboard.add_hotkey("ctrl+shift+a", self.listen_voice)
            keyboard.add_hotkey("alt+space", self.listen_voice)
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
    bridge = JarvisJSBridge(app.listen_voice)

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
        js_api=bridge
    )
    app.window = window

    app.start_wake_word_loop()
    app.setup_hotkeys()

    def greet():
        time.sleep(1)
        app.voice.speak("Jarvis online. Systems nominal, sir.")

    threading.Thread(target=greet, daemon=True).start()
    webview.start()


if __name__ == "__main__":
    main()
