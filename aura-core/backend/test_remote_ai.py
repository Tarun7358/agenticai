import requests
import sys

try:
    print("[TEST] Connecting to Laptop 2 AI at http://192.168.0.4:8000 ...")
    r = requests.post(
        "http://192.168.0.4:8000/api/generate",
        json={
            "model": "mistral",
            "prompt": "Hello! Introduce yourself briefly as Jarvis or AURA in one short sentence.",
            "stream": False
        },
        timeout=30
    )
    if r.status_code == 200:
        data = r.json()
        print("[SUCCESS] Status:", r.status_code)
        print("[RESPONSE]:", data.get("response", data))
    else:
        print("[FAILED] Status:", r.status_code, r.text)
except Exception as e:
    print("[ERROR]:", e)
