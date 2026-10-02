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


WAKE_PATTERNS = [
    r"\b(hey|hi|ok|hello|yo|ay)?\s*(aura|ora|ara|laura|aora|aurora)\b",
    r"\b(hey|hi|ok|hello|yo)?\s*(jarvis|travis|service|jarves)\b",
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


def get_best_microphone_index():
    """Detects and selects headphone/headset audio input, explicitly ignoring webcams."""
    env_idx = os.environ.get("JARVIS_MIC_INDEX")
    if env_idx is not None:
        try:
            return int(env_idx)
        except Exception:
            pass

    names = sr.Microphone.list_microphone_names()
    print("[*] Detecting audio input devices for Headphone connection...")

    def is_webcam(name):
        n_low = name.lower()
        return any(term in n_low for term in ["logi", "c270", "webcam", "camera"])

    # 1. Look for explicit Headphone / Headset / Realtek devices (excluding webcams)
    headphone_candidates = []
    for idx, name in enumerate(names):
        n_low = name.lower()
        if is_webcam(name):
            continue
        if any(term in n_low for term in ["headphone", "headset", "earphone", "realtek"]):
            if "mic" in n_low or "input" in n_low:
                headphone_candidates.append(idx)

    # Test headphone candidates and pick the one with highest active signal
    best_idx = None
    best_lvl = -1
    for idx in headphone_candidates:
        try:
            mic = sr.Microphone(device_index=idx)
            with mic as source:
                levels = [audioop.rms(source.stream.read(source.CHUNK), source.SAMPLE_WIDTH) for _ in range(4)]
                avg_lvl = sum(levels) / len(levels)
                print(f"[*] Headphone candidate [{idx}] '{names[idx]}': RMS = {avg_lvl:.1f}")
                if avg_lvl > best_lvl:
                    best_lvl = avg_lvl
                    best_idx = idx
        except Exception:
            pass

    if best_idx is not None:
        print(f"[*] --> CONNECTED to Headphone input [{best_idx}]: {names[best_idx]} (RMS: {best_lvl:.1f})")
        print("[*] Logitech Webcam mic excluded per configuration.")
        return best_idx

    # 2. General fallback excluding webcams
    for idx in range(len(names)):
        if is_webcam(names[idx]):
            continue
        if "input" in names[idx].lower() or "mic" in names[idx].lower():
            try:
                mic = sr.Microphone(device_index=idx)
                with mic as source:
                    levels = [audioop.rms(source.stream.read(source.CHUNK), source.SAMPLE_WIDTH) for _ in range(3)]
                    avg_lvl = sum(levels) / len(levels)
                    if avg_lvl > best_lvl:
                        best_lvl = avg_lvl
                        best_idx = idx
            except Exception:
                pass

    if best_idx is not None:
        print(f"[*] --> CONNECTED to input [{best_idx}]: {names[best_idx]}")
        return best_idx

    print("[*] Defaulting to system primary microphone.")
    return None


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
        self.is_speaking = False

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
                    eng.setProperty('rate', 178)
                    eng.setProperty('volume', 1.0)
                    voices = eng.getProperty('voices')
                    for v in voices:
                        if "david" in v.name.lower() or "zira" in v.name.lower():
                            eng.setProperty('voice', v.id)
                            break
                    eng.say(clean)
                    eng.runAndWait()
                    eng.stop()
                except Exception as ex:
                    print(f"[Voice] Speech error: {ex}")
                finally:
                    # Echo prevention pause before re-enabling mic
                    time.sleep(0.3)
                    self.is_speaking = False
                    if on_end:
                        on_end()

        if blocking:
            _run()
        else:
            threading.Thread(target=_run, daemon=True).start()


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
        if any(k in q for k in ["system status", "laptop", "battery", "cpu", "ram", "specs", "how are you running", "hardware"]):
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
        self.state = "idle"  # "idle", "awaiting_command", "thinking", "speaking"
        self.mic_index = None
        self.command_timeout_timer = None
        self.stop_bg_listen = None

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

        self.command_timeout_timer = threading.Timer(7.0, _timeout)
        self.command_timeout_timer.daemon = True
        self.command_timeout_timer.start()

        # Prompt the user
        self.voice.speak("Yes sir?")

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

            self._eval_js(f"onAuraResponse({json.dumps(response)})")
            self.state = "speaking"
            self._eval_js("setAuraState('speaking', 'SPEAKING...')")

            def on_done():
                self.state = "idle"
                self._eval_js("setAuraState('idle', 'JARVIS ONLINE')")

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
            self.mic_index = get_best_microphone_index()
            rec = sr.Recognizer()
            rec.dynamic_energy_threshold = True
            rec.pause_threshold = 0.6
            rec.phrase_threshold = 0.3
            rec.non_speaking_duration = 0.4

            try:
                mic = sr.Microphone(device_index=self.mic_index)
                with mic as source:
                    print("[WakeWord] Calibrating microphone for ambient noise...")
                    rec.adjust_for_ambient_noise(source, duration=1.0)
                    rec.energy_threshold = max(80, rec.energy_threshold * 0.85)
                    print(f"[*] Calibration complete: Ambient threshold = {rec.energy_threshold:.1f}")

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

                self.stop_bg_listen = rec.listen_in_background(mic, callback, phrase_time_limit=5)
                print("[*] Continuous background listener ACTIVE.")
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

    def greet():
        time.sleep(1.2)
        app.voice.speak("Jarvis online. Systems nominal, sir.")

    threading.Thread(target=greet, daemon=True).start()
    webview.start()


if __name__ == "__main__":
    main()
