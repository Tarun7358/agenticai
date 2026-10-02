"""
AURA / JARVIS Webcam Presence & Walk-Away Auto-Lock Sentinel.
==============================================================
Monitors user physical presence in front of workstation using lightweight
OpenCV Haar Cascades. Automatically locks Windows if Sir walks away for >45s,
and announces secure status upon return.
"""

import os
import time
import threading
import ctypes
from typing import Dict, Any, Optional

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class PresenceSentinel:
    def __init__(self, timeout_seconds: int = 45):
        self.timeout_seconds = timeout_seconds
        self.enabled = False
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.last_face_seen = time.time()
        self.face_present = True
        self.was_auto_locked = False
        self._welcome_callback = None

        if HAS_CV2:
            try:
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception:
                self.face_cascade = None
        else:
            self.face_cascade = None

    def register_welcome_callback(self, cb):
        self._welcome_callback = cb

    def set_enabled(self, enabled: bool) -> str:
        self.enabled = enabled
        if enabled and not self.is_running:
            self.start()
            return "Presence Sentinel activated, Sir. I will automatically lock your workstation if you step away."
        elif not enabled:
            return "Presence Sentinel is now deactivated, Sir."
        return f"Presence Sentinel active: enabled={self.enabled}"

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self.is_running,
            "face_present": self.face_present,
            "seconds_since_seen": int(time.time() - self.last_face_seen),
            "timeout_threshold": self.timeout_seconds
        }

    def start(self):
        if not HAS_CV2 or self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        self.enabled = False

    def _monitor_loop(self):
        # Open camera index 0
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print("[Presence] Warning: Could not open default camera for presence monitoring.")
            self.is_running = False
            return

        print("[Presence] Sentinel camera stream online.")

        while self.is_running:
            try:
                if not self.enabled:
                    time.sleep(2)
                    continue

                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(2)
                    continue

                # Downscale for ultra-fast <10ms face detection
                small = cv2.resize(frame, (320, 240))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=4, minSize=(30, 30))

                now = time.time()
                if len(faces) > 0:
                    self.face_present = True
                    self.last_face_seen = now
                    if self.was_auto_locked:
                        self.was_auto_locked = False
                        if self._welcome_callback:
                            try:
                                self._welcome_callback("Welcome back, Sir. All systems remained secure in your absence.")
                            except Exception:
                                pass
                else:
                    self.face_present = False
                    elapsed = now - self.last_face_seen
                    if elapsed > self.timeout_seconds and not self.was_auto_locked:
                        print(f"[Presence] Sir walked away ({int(elapsed)}s absence). Auto-locking workstation.")
                        self.was_auto_locked = True
                        try:
                            ctypes.windll.user32.LockWorkStation()
                        except Exception as e:
                            print(f"[Presence] Error locking workstation: {e}")

                # Poll every 3 seconds to keep CPU at near zero percent
                time.sleep(3)

            except Exception as ex:
                print(f"[Presence] Monitoring loop error: {ex}")
                time.sleep(3)

        cap.release()
        print("[Presence] Sentinel camera released.")


_sentinel_instance = PresenceSentinel()

def enable_presence_lock() -> str:
    return _sentinel_instance.set_enabled(True)

def disable_presence_lock() -> str:
    return _sentinel_instance.set_enabled(False)

def get_presence_status() -> str:
    st = _sentinel_instance.get_status()
    state = "active" if st["enabled"] else "inactive"
    seen = st["seconds_since_seen"]
    pres = "detected at desk" if st["face_present"] else f"absent for {seen}s"
    return f"Presence Sentinel is {state}, Sir. Physical presence: {pres} (auto-lock threshold: {st['timeout_threshold']}s)."
