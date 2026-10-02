"""
AURA Instagram Agent
Fetches your Instagram profile data, post analytics, follower trends.
Uses Instaloader (no API key needed, uses your own credentials).
"""

import instaloader
import datetime
import json
from typing import Optional
from config import settings
from memory.store import get_db, log_agent_event


_loader: Optional[instaloader.Instaloader] = None
_profile: Optional[instaloader.Profile] = None


def get_loader() -> instaloader.Instaloader:
    global _loader
    if _loader is None:
        _loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            compress_json=False,
            save_metadata=False,
            quiet=True,
            max_connection_attempts=1,
        )
    return _loader


def login(username: str = None, password: str = None) -> dict:
    """Login to Instagram with stored credentials."""
    username = username or settings.instagram_username
    password = password or settings.instagram_password

    if not username or not password:
        return {"status": "error", "message": "Instagram credentials not set in .env"}

    loader = get_loader()
    try:
        loader.login(username, password)
        return {"status": "ok", "username": username}
    except instaloader.exceptions.BadCredentialsException:
        return {"status": "error", "message": "Bad credentials — check your .env"}
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        return {"status": "error", "message": "2FA required — disable 2FA or use session file"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


_last_profile_cache = None
_last_profile_time = None

def get_profile_data(username: str = None) -> dict:
    """Fetch profile stats: followers, following, posts, bio (with cache & DB fallback)."""
    global _last_profile_cache, _last_profile_time
    username = username or settings.instagram_username
    if not username:
        return {"status": "error", "message": "No Instagram username configured"}

    # 1. Check in-memory cache (valid for 30 minutes)
    if _last_profile_cache and _last_profile_time:
        if (datetime.datetime.now() - _last_profile_time).total_seconds() < 1800:
            return _last_profile_cache

    # 2. Try fetching fresh from Instagram
    loader = get_loader()
    try:
        profile = instaloader.Profile.from_username(loader.context, username)

        data = {
            "username": profile.username,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "followers": profile.followers,
            "followees": profile.followees,
            "mediacount": profile.mediacount,
            "is_private": profile.is_private,
            "is_verified": profile.is_verified,
            "profile_pic_url": profile.profile_pic_url,
            "fetched_at": datetime.datetime.now().isoformat(),
        }

        # Save to DB
        conn = get_db()
        conn.execute(
            "INSERT INTO instagram_stats (username, followers, following, posts, fetched_at) VALUES (?,?,?,?,?)",
            (data["username"], data["followers"], data["followees"], data["mediacount"], data["fetched_at"])
        )
        conn.commit()
        conn.close()

        log_agent_event("instagram", "profile_fetch", {
            "followers": data["followers"],
            "following": data["followees"],
            "posts": data["mediacount"]
        })
        res = {"status": "ok", "data": data}
        _last_profile_cache = res
        _last_profile_time = datetime.datetime.now()
        return res
    except Exception as e:
        # Fallback to last recorded DB row
        try:
            conn = get_db()
            row = conn.execute(
                "SELECT followers, following, posts, fetched_at FROM instagram_stats WHERE username = ? ORDER BY id DESC LIMIT 1",
                (username,)
            ).fetchone()
            conn.close()
            if row:
                fallback_data = {
                    "username": username,
                    "followers": row[0],
                    "followees": row[1],
                    "mediacount": row[2],
                    "is_private": False,
                    "fetched_at": row[3],
                }
                return {"status": "ok", "data": fallback_data}
        except Exception:
            pass
        return {"status": "error", "message": str(e)}


def get_recent_posts(username: str = None, limit: int = 10) -> dict:
    """Fetch recent post metadata (no image download)."""
    username = username or settings.instagram_username
    if not username:
        return {"status": "error", "message": "No Instagram username configured"}

    loader = get_loader()
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        posts = []
        for i, post in enumerate(profile.get_posts()):
            if i >= limit:
                break
            posts.append({
                "shortcode": post.shortcode,
                "caption": (post.caption or "")[:200],
                "likes": post.likes,
                "comments": post.comments,
                "date": post.date_local.isoformat(),
                "is_video": post.is_video,
                "views": post.video_view_count if post.is_video else None,
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "hashtags": list(post.caption_hashtags) if post.caption else [],
            })

        # Calculate engagement
        if posts:
            profile_data = get_profile_data(username)
            followers = profile_data.get("data", {}).get("followers", 1)
            for p in posts:
                p["engagement_rate"] = round(
                    ((p["likes"] + p["comments"]) / max(followers, 1)) * 100, 2
                )

        log_agent_event("instagram", "posts_fetch", {"count": len(posts)})
        return {"status": "ok", "posts": posts, "count": len(posts)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_follower_trend() -> dict:
    """Get follower count history from local DB."""
    conn = get_db()
    rows = conn.execute(
        "SELECT followers, following, posts, fetched_at FROM instagram_stats ORDER BY id DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return {
        "history": [dict(r) for r in reversed(rows)],
        "count": len(rows)
    }


def get_best_posting_times(username: str = None) -> dict:
    """Analyse post engagement by hour to find best posting times."""
    result = get_recent_posts(username, limit=30)
    if result.get("status") != "ok":
        return result

    hour_stats: dict = {}
    for post in result["posts"]:
        try:
            hour = datetime.datetime.fromisoformat(post["date"]).hour
            if hour not in hour_stats:
                hour_stats[hour] = {"total_engagement": 0, "count": 0}
            hour_stats[hour]["total_engagement"] += post["likes"] + post["comments"]
            hour_stats[hour]["count"] += 1
        except Exception:
            continue

    ranked = sorted(
        [{"hour": h, "avg_engagement": round(v["total_engagement"] / v["count"], 1)}
         for h, v in hour_stats.items()],
        key=lambda x: x["avg_engagement"],
        reverse=True
    )
    return {
        "status": "ok",
        "best_times": ranked[:5],
        "all_hours": ranked
    }


def get_summary() -> str:
    """Return a text summary for the AI to use as context without blocking network calls."""
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT username, followers, following, posts, fetched_at FROM instagram_stats ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return f"Instagram @{row[0]}: {row[1]:,} followers, {row[2]:,} following, {row[3]} posts."
    except Exception:
        pass
    if _last_profile_cache and _last_profile_cache.get("status") == "ok":
        d = _last_profile_cache["data"]
        return f"Instagram @{d['username']}: {d['followers']:,} followers, {d['followees']:,} following, {d['mediacount']} posts."
    return "Instagram: Connected (stats recorded in background)"
