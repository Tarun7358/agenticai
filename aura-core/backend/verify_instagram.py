"""
Instagram 2FA Verification Helper
Run: python verify_instagram.py 123456
"""
import os
import sys
from dotenv import dotenv_values
from instagrapi import Client

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
SESSION_FILE = os.path.join(DATA_DIR, "instagram_session.json")

env = dotenv_values(os.path.join(BACKEND_DIR, ".env"))
username = env.get("INSTAGRAM_USERNAME", "").strip()
password = env.get("INSTAGRAM_PASSWORD", "").strip()

if not username or not password:
    print("[!] Username or password not found in .env")
    sys.exit(1)

code = sys.argv[1] if len(sys.argv) > 1 else input("Enter the Instagram 2FA / SMS verification code: ").strip()

print(f"[*] Submitting 2FA verification code '{code}' for @{username}...")
cl = Client()
cl.delay_range = [1, 2]

try:
    cl.login(username, password, verification_code=code)
    os.makedirs(DATA_DIR, exist_ok=True)
    cl.dump_settings(SESSION_FILE)
    print(f"[SUCCESS] Instagram successfully verified and authenticated for @{username}!")
    print(f"[*] Session saved permanently to {SESSION_FILE}.")
    print("[*] Autonomous Reel uploading and live analytics are now FULLY UNLOCKED for Jarvis!")
except Exception as e:
    print(f"[ERROR] Verification failed: {e}")
