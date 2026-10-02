"""
AURA JARVIS Satellite Node (Laptop 2 / Remote Microphone Client)
Run this script on your second laptop.
- Listens for wake-word ("Hey Aura" / "Jarvis") on Laptop 2's microphone.
- Auto-discovers Laptop 1 (Master PC) on the home Wi-Fi using UDP broadcast.
- Instantly pops up the holographic Arc Reactor HUD on Laptop 1 and executes commands there!
"""

import os
import sys
import time
import socket
import json
import re
import urllib.request
import speech_recognition as sr
import pyttsx3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from agents import lan_sync

WAKE_PATTERNS = [
    r"\b(hey|hi|ok|hello|yo)?\s*(aura|ora|ara|laura|aora|aurora)\b",
    r"\b(hey|hi|ok|hello|yo)?\s*(jarvis|travis|service|jarves|kavya|kavi)\b",
]

def check_wake(text: str):
    text = text.lower().strip()
    for pat in WAKE_PATTERNS:
        m = re.search(pat, text)
        if m:
            return True, text[m.end():].strip(" ,.?")
    return False, ""

def speak(text: str):
    try:
        eng = pyttsx3.init()
        eng.setProperty('rate', 190)
        eng.say(text)
        eng.runAndWait()
        eng.stop()
    except Exception:
        pass

def main():
    print("=" * 60)
    print("     AURA JARVIS — SATELLITE NODE (LAPTOP 2 REMOTE)")
    print("=" * 60)
    print("[*] Searching for Primary PC on local Wi-Fi...")

    master_url = os.environ.get("JARVIS_MASTER_URL") or lan_sync.discover_master_pc(timeout=2.5)
    if master_url:
        print(f"[+] Connected to Primary PC at: {master_url}")
        speak("Satellite connected to master PC, sir.")
    else:
        print("[!] Note: Primary PC not auto-detected yet. Will auto-retry on every command.")

    rec = sr.Recognizer()
    rec.dynamic_energy_threshold = False
    rec.pause_threshold = 0.5

    try:
        mic = sr.Microphone()
        with mic as src:
            rec.adjust_for_ambient_noise(src, duration=0.8)
            rec.energy_threshold = max(60, min(300, rec.energy_threshold * 0.75))
            print(f"[*] Microphone active. Say 'Jarvis' or 'Hey Aura' anytime...")
    except Exception as e:
        print(f"[!] Microphone error: {e}")
        return

    def on_audio(recognizer, audio):
        try:
            spoken = recognizer.recognize_google(audio).lower().strip()
        except Exception:
            return

        if not spoken:
            return

        print(f"[Satellite Heard] '{spoken}'")
        triggered, query = check_wake(spoken)
        if triggered:
            print(f"[*] Wake word detected! Query: '{query}'")
            print("[*] Triggering HUD on Primary PC...")
            res = lan_sync.trigger_remote_pc_hud(master_url=master_url, query=query)
            if res.get("status") == "ok":
                print(f"[+] Command transmitted to Primary PC: {res}")
            else:
                print(f"[!] Could not reach Primary PC: {res.get('message')}")
                speak("Primary PC not responding on Wi-Fi, sir.")

    stop_listen = rec.listen_in_background(mic, on_audio, phrase_time_limit=8)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_listen(wait_for_stop=False)
        print("\n[*] Satellite node stopped.")

if __name__ == "__main__":
    main()
