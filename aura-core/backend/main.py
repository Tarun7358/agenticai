"""
AURA FastAPI Backend — Main Application
All REST + WebSocket endpoints for the React frontend.
"""

import asyncio
import datetime
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from memory.store import init_db, get_history, get_recent_events
from utils.llm import chat, check_ollama_status, summarize
from agents import network_agent, instagram_agent, file_agent, iphone_agent


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[AURA] Starting up...")
    init_db()
    file_agent.start_file_watcher()
    # Initial network scan in background
    asyncio.create_task(asyncio.to_thread(network_agent.scan_and_update_db))
    print("[AURA] Online at http://127.0.0.1:8000")
    yield
    file_agent.stop_file_watcher()
    print("[AURA] Shutting down...")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AURA Personal AI",
    description="Your always-on personal intelligence system",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Models ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class FileSearchRequest(BaseModel):
    query: str
    limit: int = 5

class IndexFolderRequest(BaseModel):
    folder: str

class TrustDeviceRequest(BaseModel):
    mac: str
    alias: str = ""


# ─── Core / Status ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"name": "AURA", "status": "online", "time": datetime.datetime.now().isoformat()}


@app.get("/api/status")
async def get_status():
    ollama = await check_ollama_status()
    return {
        "aura": "online",
        "ollama": ollama,
        "model": settings.ollama_model,
        "time": datetime.datetime.now().isoformat(),
        "instagram_configured": bool(settings.instagram_username),
        "email_configured": bool(settings.email_address),
        "watched_folders": settings.watched_folders.split(",") if settings.watched_folders else [],
        "file_index": file_agent.get_indexed_stats(),
    }


# ─── Chat (Streaming) ─────────────────────────────────────────────────────────

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming chat endpoint — returns text/event-stream."""
    session_id = req.session_id or str(uuid.uuid4())

    # Build context from agents
    context_parts = []
    try:
        ig_summary = instagram_agent.get_summary()
        context_parts.append(ig_summary)
    except Exception:
        pass

    try:
        net_devices = network_agent.get_all_devices()
        trusted = sum(1 for d in net_devices if d["is_trusted"])
        context_parts.append(f"Network: {len(net_devices)} devices total, {trusted} trusted, {len(net_devices)-trusted} unknown.")
    except Exception:
        pass

    context = "\n".join(context_parts)

    async def generate():
        yield f"data: {session_id}\n\n"  # send session ID first
        async for token in chat(session_id, req.message, context):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str, limit: int = 30):
    return {"history": get_history(session_id, limit), "session_id": session_id}


# ─── WebSocket Chat ────────────────────────────────────────────────────────────

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            context_parts = []
            try:
                context_parts.append(instagram_agent.get_summary())
            except Exception:
                pass

            async for token in chat(session_id, data, "\n".join(context_parts)):
                await websocket.send_text(token)
            await websocket.send_text("[DONE]")
    except WebSocketDisconnect:
        pass


# ─── Network Agent ────────────────────────────────────────────────────────────

@app.get("/api/network/devices")
async def get_network_devices():
    return {"devices": network_agent.get_all_devices()}


@app.post("/api/network/scan")
async def trigger_network_scan(bg: BackgroundTasks):
    bg.add_task(asyncio.to_thread, network_agent.scan_and_update_db)
    return {"status": "scan_started"}


@app.get("/api/network/scan/now")
async def scan_now():
    result = await asyncio.to_thread(network_agent.scan_and_update_db)
    return result


@app.post("/api/network/trust")
async def trust_device(req: TrustDeviceRequest):
    ok = network_agent.trust_device(req.mac, req.alias)
    return {"success": ok}


@app.get("/api/network/stats")
async def network_stats():
    return network_agent.get_network_stats()


# ─── Instagram Agent ──────────────────────────────────────────────────────────

@app.get("/api/instagram/profile")
async def instagram_profile():
    return await asyncio.to_thread(instagram_agent.get_profile_data)


@app.get("/api/instagram/posts")
async def instagram_posts(limit: int = 12):
    return await asyncio.to_thread(instagram_agent.get_recent_posts, None, limit)


@app.get("/api/instagram/trend")
async def instagram_trend():
    return instagram_agent.get_follower_trend()


@app.get("/api/instagram/best-times")
async def instagram_best_times():
    return await asyncio.to_thread(instagram_agent.get_best_posting_times)


# ─── File Agent ───────────────────────────────────────────────────────────────

@app.post("/api/files/search")
async def search_files(req: FileSearchRequest):
    results = await file_agent.search_files(req.query, req.limit)
    return {"results": results, "query": req.query}


@app.post("/api/files/index")
async def index_folder(req: IndexFolderRequest, bg: BackgroundTasks):
    bg.add_task(asyncio.to_thread, asyncio.run, file_agent.index_folder(req.folder))
    return {"status": "indexing_started", "folder": req.folder}


@app.get("/api/files/stats")
async def file_stats():
    return file_agent.get_indexed_stats()


# ─── Events / Logs ────────────────────────────────────────────────────────────

@app.get("/api/events")
async def get_events(agent: Optional[str] = None, limit: int = 50):
    return {"events": get_recent_events(agent, limit)}


# ─── Summarize ────────────────────────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    text: str
    instruction: str = "Summarize this clearly and concisely:"

@app.post("/api/summarize")
async def summarize_text(req: SummarizeRequest):
    result = await summarize(req.text, req.instruction)
    return {"summary": result}


# ─── Distributed Ollama AI Gateway / Relay ──────────────────────────────────

@app.post("/api/generate")
async def proxy_ollama_generate(payload: dict):
    """Proxies LLM generation to local Ollama for remote LAN nodes (Thin Client -> AI Server)."""
    import httpx
    ollama_url = settings.ollama_base_url.rstrip('/')
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{ollama_url}/api/generate", json=payload)
            return resp.json()
        except Exception as ex:
            raise HTTPException(status_code=502, detail=f"Ollama gateway error: {ex}")


# ─── iPhone / Mobile Integration ─────────────────────────────────────────────

class CallEventRequest(BaseModel):
    caller: str
    event_type: str = "missed"  # "missed", "incoming", "scheduled"
    time: Optional[str] = None

@app.post("/api/iphone/call-event")
async def log_iphone_call(req: CallEventRequest):
    """Endpoint for iOS Shortcuts or Phone Link to notify JARVIS of a call event."""
    event = iphone_agent.record_call_event(req.caller, req.event_type, req.time)
    return {"status": "ok", "event": event}

@app.get("/api/iphone/calls")
async def get_iphone_calls():
    """Returns missed calls and recent phone notifications."""
    missed = iphone_agent.get_missed_calls()
    recent = iphone_agent.get_recent_phone_notifications()
    upcoming = iphone_agent.get_upcoming_calls()
    return {"missed_calls": missed, "recent_events": recent, "upcoming_calls": upcoming}

@app.post("/api/iphone/pair")
async def pair_iphone():
    """Triggers Windows Phone Link for Bluetooth P2P pairing."""
    msg = iphone_agent.launch_phone_link()
    return {"status": "ok", "message": msg}
