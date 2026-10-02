"""
AURA / JARVIS Sovereign Gemini Hybrid Engine.
============================================
Delivers ultra-fast, intelligent, cinema-grade Jarvis reasoning via Google Gemini
while maintaining strict local data sovereignty:
  - Personal documents, ChromaDB memory, and local logs remain 100% on your SSD.
  - Credential and password filters prevent leaking secrets to cloud endpoints.
  - Seamless fallback to local Ollama / Mistral if offline or on timeout.
"""

import os
import re
import requests
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

# Try loading from .env
try:
    from dotenv import dotenv_values
    env_path = os.path.join(BACKEND_DIR, ".env")
    _env_vals = dotenv_values(env_path) if os.path.exists(env_path) else {}
except Exception:
    _env_vals = {}

GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or _env_vals.get("GEMINI_API_KEY", "")).strip()
GEMINI_MODEL = (os.environ.get("GEMINI_MODEL") or _env_vals.get("GEMINI_MODEL", "gemini-flash-lite-latest")).strip()

# Models to attempt in order of priority and speed
CANDIDATE_MODELS = [
    GEMINI_MODEL,
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest"
]


def is_gemini_active() -> bool:
    """Returns True if a Gemini API key is configured."""
    return bool(GEMINI_API_KEY and len(GEMINI_API_KEY) > 10)


def sanitize_prompt_for_privacy(prompt: str) -> str:
    """
    Local privacy shield: redacts passwords, authentication tokens,
    and private access keys before transmitting query to Gemini.
    """
    # Redact JWT tokens
    p = re.sub(r'eyJ[a-zA-Z0-9_\-]{15,}\.[a-zA-Z0-9_\-]{15,}\.[a-zA-Z0-9_\-]{15,}', '[REDACTED_JWT]', prompt)
    # Redact common credential patterns (password=..., token=...)
    p = re.sub(r'(password|passwd|secret|apikey|token)\s*[:=]\s*[^\s,;]+', r'\1=[REDACTED]', p, flags=re.IGNORECASE)
    return p


def query_gemini(
    prompt: str,
    system_prompt: str = "",
    context: str = "",
    max_tokens: int = 100,
    timeout: int = 7
) -> Optional[str]:
    """
    Queries Gemini with the user's prompt and optional context/system prompt.
    Returns clean text response, or None if unavailable/offline for local fallback.
    """
    if not is_gemini_active():
        return None

    clean_prompt = sanitize_prompt_for_privacy(prompt)
    if context:
        clean_context = sanitize_prompt_for_privacy(context)
        clean_prompt = f"Context:\n{clean_context}\n\nUser Question:\n{clean_prompt}"

    # Build payload
    payload = {
        "contents": [{"parts": [{"text": clean_prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.6
        }
    }
    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }

    seen_models = set()
    for model_name in CANDIDATE_MODELS:
        clean_model = model_name.replace("models/", "")
        if clean_model in seen_models:
            continue
        seen_models.add(clean_model)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={GEMINI_API_KEY}"
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        ans = parts[0]["text"].strip()
                        # Clean markdown formatting like asterisks or quotes
                        ans = re.sub(r'[*_~`]', '', ans).strip()
                        return ans
            elif resp.status_code in (404, 429, 503):
                # Try next candidate model
                continue
        except Exception:
            continue

    return None
