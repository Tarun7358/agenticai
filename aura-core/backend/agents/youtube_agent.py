"""
YouTube Dashboard & Studio Agent for AURA / JARVIS.
Enables instant access to YouTube Studio Creator Analytics, Channel Dashboard, and metrics.
Executes safely with strict zero-leakage privacy.
"""
import os
import re
import urllib.request
import webbrowser
from typing import Dict, Any

def open_youtube_studio() -> str:
    """Launches YouTube Studio Dashboard directly on screen in the user's browser."""
    url = "https://studio.youtube.com/"
    webbrowser.open(url)
    return url

def open_youtube_analytics() -> str:
    """Launches YouTube Studio Analytics tab for deep-dive audience and revenue metrics."""
    url = "https://studio.youtube.com/channel/analytics"
    webbrowser.open(url)
    return url

def get_channel_summary(handle: str = None) -> Dict[str, Any]:
    """
    Fetches public stats for a YouTube channel handle or opens Studio if private.
    """
    if not handle:
        handle = os.environ.get("YOUTUBE_HANDLE", "").strip()
    
    if not handle:
        return {
            "status": "ready",
            "message": "YouTube Studio is ready. Launching your creator dashboard."
        }

    clean_handle = handle if handle.startswith("@") else f"@{handle}"
    url = f"https://www.youtube.com/{clean_handle}"
    
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8", errors="ignore")
        
        subs_match = re.search(r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([^"]+)"', html)
        subscribers = subs_match.group(1) if subs_match else "Available in Studio"
        
        videos_match = re.search(r'([0-9,]+)\s+videos', html)
        videos = videos_match.group(1) if videos_match else "Available in Studio"
        
        return {
            "status": "ok",
            "handle": clean_handle,
            "subscribers": subscribers,
            "videos": videos,
            "url": url
        }
    except Exception as ex:
        return {
            "status": "error",
            "message": str(ex),
            "handle": clean_handle
        }
