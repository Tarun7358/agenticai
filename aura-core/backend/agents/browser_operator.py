"""
AURA / JARVIS Autonomous Browser & Web Task Operator.
=====================================================
Autonomous web navigator that pulls live trending GitHub repositories,
Hacker News tech headlines, and scrapes/summarizes target web pages on demand.
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List


def get_trending_github(limit: int = 3, language: str = "") -> str:
    """Extracts top trending developer repositories on GitHub today."""
    try:
        limit = int(limit) if limit and str(limit).isdigit() else 3
    except Exception:
        limit = 3

    try:
        url = f"https://github.com/trending/{language.strip().lower()}" if language else "https://github.com/trending"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            articles = soup.find_all("article", class_="Box-row")
            results = []
            for art in articles[:limit]:
                h2 = art.find("h2")
                repo_name = h2.text.strip().replace("\n", "").replace(" ", "") if h2 else "Unknown"
                desc = art.find("p")
                desc_text = desc.text.strip() if desc else "No description"
                # Remove problematic emoji characters for Windows cp1252 compatibility
                clean_name = repo_name.encode('ascii', 'ignore').decode('ascii')
                clean_desc = desc_text.encode('ascii', 'ignore').decode('ascii')
                results.append(f"- {clean_name}: {clean_desc}")

            if results:
                return "Sir, here are today's top trending GitHub repositories:\n" + "\n".join(results)
    except Exception as e:
        print(f"[BrowserOperator] GitHub trending error: {e}")

    # Fallback to GitHub Search API
    try:
        api_url = "https://api.github.com/search/repositories?q=stars:>1000+pushed:>2026-09-01&sort=stars&order=desc"
        resp = requests.get(api_url, timeout=6)
        if resp.status_code == 200:
            items = resp.json().get("items", [])[:limit]
            names = [f"- {i['full_name']}: {i.get('description', '')[:80].encode('ascii', 'ignore').decode('ascii')}" for i in items]
            return "Sir, top starred active repositories on GitHub:\n" + "\n".join(names)
    except Exception:
        pass

    return "Unable to access GitHub trending telemetry at the moment, Sir."


def get_tech_headlines(limit: int = 3) -> str:
    """Retrieves top breaking tech headlines from Hacker News."""
    try:
        top_ids_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        top_ids = requests.get(top_ids_url, timeout=5).json()[:limit]
        headlines = []
        for sid in top_ids:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
            item = requests.get(item_url, timeout=4).json()
            title = item.get("title", "")
            if title:
                headlines.append(f"- {title}")
        if headlines:
            return "Sir, here are the top technology headlines right now:\n" + "\n".join(headlines)
    except Exception as e:
        print(f"[BrowserOperator] Tech headlines error: {e}")

    return "Unable to fetch live technology headlines right now, Sir."


def browse_and_summarize(url_or_topic: str) -> str:
    """Scrapes a target webpage and uses Gemini Flash to produce an executive synthesis."""
    url = url_or_topic.strip()
    if not url.startswith("http"):
        url = "https://" + url

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Strip scripts, styles
            for s in soup(["script", "style", "nav", "footer", "header"]):
                s.decompose()
            text = soup.get_text(separator=" ", strip=True)
            text_snippet = text[:3000]

            try:
                from agents import gemini_agent
                if gemini_agent.is_gemini_active():
                    summary = gemini_agent.query_gemini(
                        prompt=f"Summarize the key takeaways of this webpage ({url}):\n\n{text_snippet}",
                        system_prompt="You are an executive research intelligence assistant. Provide a direct 2 to 3 sentence spoken debrief.",
                        max_tokens=300
                    )
                    if summary:
                        return f"From {url}, Sir: {summary.strip()}"
            except Exception:
                pass

            return f"Retrieved content from {url}, Sir. Preliminary text begins: {text_snippet[:150]}..."
    except Exception as e:
        return f"Unable to browse {url}: {e}"

    return f"Failed to retrieve web telemetry from {url}, Sir."
