"""
AURA Instagram Autonomous Engine
Powered by instagrapi and local Ollama Mistral LLM.
Features:
- Persistent authenticated session (avoids repeated logins and 429 rate limits)
- Live Reel view counters, play counts, like counts, and engagement analytics
- Autonomous Reel video uploading with AI-generated hooks and viral hashtags
- Automatic newest video discovery from Downloads and Videos folders
"""

import os
import sys
import glob
import json
import time
import datetime
import requests
from typing import Optional, Dict, Any, List
from pathlib import Path
from dotenv import dotenv_values

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(BACKEND_DIR, "data")
SESSION_FILE = os.path.join(DATA_DIR, "instagram_session.json")
REELS_DIR = os.path.join(BACKEND_DIR, "reels")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REELS_DIR, exist_ok=True)

_client = None


def get_credentials() -> tuple[str, str]:
    env_path = os.path.join(BACKEND_DIR, ".env")
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    username = env.get("INSTAGRAM_USERNAME", "").strip()
    password = env.get("INSTAGRAM_PASSWORD", "").strip()
    return username, password


def get_client(force_login: bool = False):
    """Initializes and returns an authenticated instagrapi Client."""
    global _client
    if _client is not None and not force_login:
        return _client

    from instagrapi import Client

    username, password = get_credentials()
    if not username:
        raise ValueError("Instagram username not configured in .env")

    cl = Client()
    cl.delay_range = [1, 3]

    # Attempt to load persistent session
    if os.path.exists(SESSION_FILE) and not force_login:
        try:
            print("[InstagramEngine] Loading saved session from disk...")
            cl.load_settings(SESSION_FILE)
            cl.login(username, password)
            _client = cl
            return _client
        except Exception as e:
            print(f"[InstagramEngine] Saved session expired or invalid ({e}), performing clean login...")

    if not password:
        raise ValueError("Instagram password not set in .env")

    print(f"[InstagramEngine] Authenticating with Instagram as @{username}...")
    try:
        cl.login(username, password)
        cl.dump_settings(SESSION_FILE)
        print("[InstagramEngine] Login successful! Session dumped to session.json.")
        _client = cl
        return _client
    except Exception as e:
        print(f"[InstagramEngine] Authentication failed: {e}")
        raise e


def generate_ai_caption(topic: str = "gaming highlights", video_filename: str = "") -> str:
    """Uses local Ollama Mistral LLM to generate a viral Reel caption and hashtags."""
    prompt = (
        f"You are a viral social media manager for an elite gamer and esports creator. "
        f"Write a short, punchy Instagram Reel caption (1 to 2 lines max) with a strong hook, "
        f"followed by 5 to 7 high-engagement viral hashtags. "
        f"The reel topic is: '{topic}' (Filename: {video_filename}). "
        f"Do NOT include explanations or notes. Return ONLY the caption and hashtags."
    )
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_ctx": 1024}
            },
            timeout=15
        )
        if resp.status_code == 200:
            text = resp.json().get("response", "").strip()
            if text:
                return text
    except Exception as ex:
        print(f"[InstagramEngine] LLM generation error: {ex}")

    # Fallback caption
    return f"Leveling up the gameplay! 🔥 Drop a comment below if you want the full breakdown.\n\n#gaming #esports #gamer #highlights #reels #viral #gamingcommunity"


def find_latest_video_file() -> Optional[str]:
    """Finds the most recently modified video file in user's folders."""
    search_dirs = [
        REELS_DIR,
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Videos"),
        os.path.expanduser("~/Desktop"),
    ]
    extensions = ["*.mp4", "*.mov", "*.m4v"]
    candidates = []

    for d in search_dirs:
        if not os.path.exists(d):
            continue
        for ext in extensions:
            for f in glob.glob(os.path.join(d, ext)):
                try:
                    mtime = os.path.getmtime(f)
                    candidates.append((mtime, f))
                except Exception:
                    continue

    if not candidates:
        return None

    # Sort descending by modification time
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def get_live_reel_analytics(username: str = None) -> Dict[str, Any]:
    """Fetches real-time reel view counts, plays, likes, and comments."""
    cfg_user, _ = get_credentials()
    username = username or cfg_user

    try:
        cl = get_client()
        user_id = cl.user_id_from_username(username)
        # Fetch latest clips / reels
        clips = cl.user_clips(user_id, amount=6)

        results = []
        total_plays = 0
        total_likes = 0
        total_comments = 0

        for clip in clips:
            plays = getattr(clip, "play_count", None) or getattr(clip, "view_count", 0) or 0
            likes = getattr(clip, "like_count", 0) or 0
            comments = getattr(clip, "comment_count", 0) or 0
            shortcode = getattr(clip, "code", "") or getattr(clip, "shortcode", "")

            total_plays += plays
            total_likes += likes
            total_comments += comments

            results.append({
                "shortcode": shortcode,
                "url": f"https://www.instagram.com/reel/{shortcode}/",
                "plays": plays,
                "likes": likes,
                "comments": comments,
                "caption": (getattr(clip, "caption_text", "") or "")[:120],
                "taken_at": str(getattr(clip, "taken_at", "")),
            })

        summary = {
            "status": "ok",
            "username": username,
            "count": len(results),
            "reels": results,
            "total_plays": total_plays,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "latest_plays": results[0]["plays"] if results else 0,
            "latest_likes": results[0]["likes"] if results else 0,
        }
        return summary
    except Exception as e:
        return {"status": "error", "message": str(e)}


def upload_reel_post(video_path: str = None, topic: str = "epic gameplay clip", custom_caption: str = None) -> Dict[str, Any]:
    """Autonomous reel uploader: discovers video, writes AI caption, and uploads to Instagram."""
    # Find video if not specified
    if not video_path:
        video_path = find_latest_video_file()

    if not video_path or not os.path.exists(video_path):
        return {
            "status": "error",
            "message": "No video file found in Downloads, Videos, or reels folder."
        }

    caption = custom_caption or generate_ai_caption(topic=topic, video_filename=os.path.basename(video_path))

    try:
        cl = get_client()
        print(f"[InstagramEngine] Uploading Reel from: '{video_path}'...")
        media = cl.clip_upload(path=video_path, caption=caption)

        shortcode = getattr(media, "code", "")
        url = f"https://www.instagram.com/reel/{shortcode}/" if shortcode else "https://www.instagram.com/"

        # Log into local DB
        try:
            from memory.store import get_db, log_agent_event
            conn = get_db()
            conn.execute(
                "CREATE TABLE IF NOT EXISTS instagram_uploads (id INTEGER PRIMARY KEY AUTOINCREMENT, shortcode TEXT, video_path TEXT, caption TEXT, uploaded_at TEXT)"
            )
            conn.execute(
                "INSERT INTO instagram_uploads (shortcode, video_path, caption, uploaded_at) VALUES (?,?,?,?)",
                (shortcode, video_path, caption, datetime.datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            log_agent_event("instagram", "reel_uploaded", {"shortcode": shortcode, "path": video_path})
        except Exception:
            pass

        return {
            "status": "ok",
            "shortcode": shortcode,
            "url": url,
            "caption": caption,
            "file": os.path.basename(video_path),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
