"""
AURA / JARVIS Live Meeting & Audio Notetaker.
=============================================
Records and transcribes speech/meeting audio, generates executive summaries
and action items using Gemini Flash, and persists structured Markdown notes.
"""

import os
import time
import threading
import datetime
from typing import Dict, Any, Optional

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False

NOTES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "notes")
os.makedirs(NOTES_DIR, exist_ok=True)


class MeetingNotetaker:
    def __init__(self):
        self.is_recording = False
        self.transcribed_chunks = []
        self._thread: Optional[threading.Thread] = None
        self._stop_listen_fn = None
        self.start_time = None

    def start_recording(self) -> str:
        if self.is_recording:
            return "Meeting notetaker is already actively recording, Sir."

        if not HAS_SR:
            return "Speech recognition module is not available for audio notes, Sir."

        self.is_recording = True
        self.transcribed_chunks = []
        self.start_time = datetime.datetime.now()

        def _record_loop():
            rec = sr.Recognizer()
            rec.dynamic_energy_threshold = True
            rec.pause_threshold = 0.8
            try:
                mic = sr.Microphone()
                with mic as source:
                    rec.adjust_for_ambient_noise(source, duration=0.6)

                def _cb(recognizer, audio):
                    if not self.is_recording:
                        return
                    try:
                        text = recognizer.recognize_google(audio).strip()
                        if text:
                            print(f"[Notetaker] Captured: {text}")
                            self.transcribed_chunks.append(text)
                    except Exception:
                        pass

                self._stop_listen_fn = rec.listen_in_background(mic, _cb, phrase_time_limit=15)
            except Exception as e:
                print(f"[Notetaker] Recording error: {e}")
                self.is_recording = False

        threading.Thread(target=_record_loop, daemon=True).start()
        return "Meeting notetaker activated, Sir. I am actively transcribing audio. Tell me 'stop meeting notes' when finished."

    def stop_and_summarize(self) -> str:
        if not self.is_recording:
            return "No active meeting session is running, Sir."

        self.is_recording = False
        if self._stop_listen_fn:
            try:
                self._stop_listen_fn(wait_for_stop=False)
            except Exception:
                pass

        if not self.transcribed_chunks:
            return "Meeting recording stopped, Sir. However, no audible speech was captured."

        full_transcript = " ".join(self.transcribed_chunks)
        duration_mins = max(1, int((datetime.datetime.now() - self.start_time).total_seconds() / 60))

        # Generate Executive Summary & Action Items via Gemini Flash
        summary = "Meeting transcribed."
        action_items = []
        try:
            from agents import gemini_agent
            if gemini_agent.is_gemini_active():
                prompt = (
                    f"Analyze this meeting transcript ({duration_mins} mins):\n\n"
                    f"\"{full_transcript}\"\n\n"
                    f"Provide:\n"
                    f"1. Executive Summary (2-3 concise sentences)\n"
                    f"2. Action Items & Decisions (bulleted list)"
                )
                summary_res = gemini_agent.query_gemini(
                    prompt=prompt,
                    system_prompt="You are an elite corporate chief of staff.",
                    max_tokens=400
                )
                if summary_res:
                    summary = summary_res.strip()
        except Exception as ex:
            print(f"[Notetaker] Summarization error: {ex}")

        # Save Markdown note
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        note_path = os.path.join(NOTES_DIR, f"meeting_note_{timestamp}.md")
        try:
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(f"# Meeting Debrief - {datetime.datetime.now().strftime('%Y-%m-%d %I:%M %p')}\n\n")
                f.write(f"**Duration:** ~{duration_mins} minutes\n\n")
                f.write(f"## Executive Summary & Action Items\n\n{summary}\n\n")
                f.write(f"## Full Raw Transcript\n\n{full_transcript}\n")
        except Exception:
            pass

        return f"Meeting notes compiled and saved to your workspace notes folder, Sir. Processed {len(self.transcribed_chunks)} speech segments across {duration_mins} minute{'s' if duration_mins>1 else ''}."


_notetaker = MeetingNotetaker()

def start_notes() -> str:
    return _notetaker.start_recording()

def stop_notes() -> str:
    return _notetaker.stop_and_summarize()
