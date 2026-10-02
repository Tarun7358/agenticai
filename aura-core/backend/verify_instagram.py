"""
Instagram Verification Helper
Supports:
1. Instant Browser Session ID: python verify_instagram.py --sessionid <your_sessionid>
2. SMS / WhatsApp 2FA Code:   python verify_instagram.py 123456
"""
import os
import sys
import json
from dotenv import dotenv_values
from instagrapi import Client

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
SESSION_FILE = os.path.join(DATA_DIR, "instagram_session.json")

env = dotenv_values(os.path.join(BACKEND_DIR, ".env"))
username = env.get("INSTAGRAM_USERNAME", "").strip()
password = env.get("INSTAGRAM_PASSWORD", "").strip()

if not username:
    print("[!] INSTAGRAM_USERNAME not found in .env")
    sys.exit(1)

args = sys.argv[1:]

# Method A: Login via browser sessionid cookie
if len(args) >= 2 and args[0] == "--sessionid":
    sessionid = args[1].strip()
    print(f"[*] Authenticating @{username} via Browser Session ID...")
    cl = Client()
    cl.private.cookies.set("sessionid", sessionid, domain=".instagram.com")
    cl.public.cookies.set("sessionid", sessionid, domain=".instagram.com")
    try:
        user_info = cl.account_info()
        os.makedirs(DATA_DIR, exist_ok=True)
        cl.dump_settings(SESSION_FILE)
        print(f"[SUCCESS] Connected successfully as @{user_info.username} (ID: {user_info.pk})!")
        print(f"[*] Session saved permanently to {SESSION_FILE}.")
        print("[*] Autonomous Reel uploading and live analytics are now FULLY UNLOCKED for Jarvis!")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Session ID authentication failed: {e}")
        sys.exit(1)

# Method B: 2FA Verification Code
if len(args) >= 1 and args[0] != "YOUR_6_DIGIT_CODE" and not args[0].startswith("--"):
    code = args[0].strip()
else:
    print("\n--- Instagram Authentication for @", username, "---")
    print("Choose your method:")
    print("  1. Enter 6-digit 2FA / SMS / WhatsApp code")
    print("  2. Paste browser 'sessionid' cookie (from Chrome/Edge F12 > Application > Cookies)")
    choice = input("Enter 1 or 2: ").strip()
    if choice == "2":
        sessionid = input("Paste your 'sessionid' cookie value: ").strip()
        cl = Client()
        cl.private.cookies.set("sessionid", sessionid, domain=".instagram.com")
        cl.public.cookies.set("sessionid", sessionid, domain=".instagram.com")
        try:
            user_info = cl.account_info()
            os.makedirs(DATA_DIR, exist_ok=True)
            cl.dump_settings(SESSION_FILE)
            print(f"[SUCCESS] Connected successfully as @{user_info.username} (ID: {user_info.pk})!")
            print(f"[*] Session saved permanently to {SESSION_FILE}.")
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Failed: {e}")
            sys.exit(1)
    else:
        code = input("Enter your 6-digit code: ").strip()

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
    print("\n[TIP] If Instagram only showed an 'Approve' button with no code, use Method 2 (sessionid from Chrome/Edge) to connect instantly!")
