"""
AURA LLM Core — Ollama Integration
Handles all AI inference: chat, summarization, embeddings
"""

import httpx
import json
from typing import AsyncGenerator
from config import settings
from memory.store import get_history, save_message, get_collection
import datetime


OLLAMA_URL = settings.ollama_base_url
MODEL = settings.ollama_model

# System prompt that defines AURA's personality
AURA_SYSTEM_PROMPT = """You are AURA, a personal AI assistant running locally on your owner's laptop.
You have access to your owner's data: Instagram analytics, WhatsApp summaries, network status, local files, emails, and calendar.
You are intelligent, concise, and proactive. You speak like a trusted assistant — direct, helpful, never robotic.
You remember past conversations and personal preferences.
When you don't have data yet (agent not connected), say so honestly.
Current time: {current_time}
"""


async def check_ollama_status() -> dict:
    """Check if Ollama or Remote AI node is running and which models are available."""
    # 1. Try standard Ollama endpoint /api/tags
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return {"status": "online", "models": models}
    except Exception:
        pass

    # 2. Try remote AURA node endpoint /api/status (Laptop 2 on port 8000)
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/status")
            if resp.status_code == 200:
                data = resp.json()
                ollama_data = data.get("ollama", {})
                if ollama_data.get("status") == "online":
                    return {"status": "online", "models": ollama_data.get("models", [])}
    except Exception:
        pass

    return {"status": "offline", "models": [], "hint": "Run: ollama serve"}


async def chat(
    session_id: str,
    user_message: str,
    context: str = ""
) -> AsyncGenerator[str, None]:
    """
    Stream a response from Ollama (local or remote node).
    Maintains conversation history automatically.
    """
    # Build history
    history = get_history(session_id, limit=15)
    messages = []

    system = AURA_SYSTEM_PROMPT.format(
        current_time=datetime.datetime.now().strftime("%A, %B %d %Y at %I:%M %p")
    )
    if context:
        system += f"\n\n[CONTEXT FROM AGENTS]\n{context}"

    messages.append({"role": "system", "content": system})

    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    # Save user message
    save_message(session_id, "user", user_message)

    # Stream from Ollama or Remote AURA Gateway
    full_response = ""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            # If OLLAMA_URL points to remote AURA node on port 8000, stream from its /api/chat/stream
            if ":8000" in OLLAMA_URL:
                try:
                    async with client.stream(
                        "POST",
                        f"{OLLAMA_URL}/api/chat/stream",
                        json={"message": user_message, "session_id": session_id}
                    ) as resp:
                        if resp.status_code == 200:
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data: "):
                                    continue
                                chunk = line[6:]
                                if chunk == "[DONE]":
                                    break
                                full_response += chunk
                                yield chunk
                            if full_response:
                                save_message(session_id, "assistant", full_response)
                                return
                except Exception:
                    pass

            # Standard Ollama /api/chat stream
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": MODEL,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_ctx": 4096,
                    }
                }
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            full_response += token
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
    except httpx.ConnectError:
        error_msg = "⚠️ AURA's AI brain (Ollama on Laptop 2) is unreachable. Please verify connection and try again."
        yield error_msg
        full_response = error_msg

    # Save assistant response
    if full_response:
        save_message(session_id, "assistant", full_response)


async def summarize(text: str, instruction: str = "Summarize this concisely:") -> str:
    """One-shot summarization — used by agents."""
    full = ""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": f"{instruction}\n\n{text}",
                "stream": False,
                "options": {"temperature": 0.3, "num_ctx": 2048}
            }
        )
        if resp.status_code == 200:
            full = resp.json().get("response", "")
    return full.strip()


async def get_embedding(text: str) -> list[float]:
    """Get text embedding from Ollama (nomic-embed-text or fallback to model)."""
    embed_model = "nomic-embed-text"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": embed_model, "prompt": text}
            )
            if resp.status_code == 200:
                return resp.json().get("embedding", [])
        except Exception:
            pass
    return []
