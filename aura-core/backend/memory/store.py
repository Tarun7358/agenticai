"""
AURA Memory System — ChromaDB + SQLite
Handles persistent memory for the AI: conversations, embeddings, facts
"""

import sqlite3
import json
import datetime
from pathlib import Path
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from config import settings


# ─── SQLite DB for structured data ────────────────────────────────────────────

DB_PATH = Path(settings.aura_data_path) / "aura.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,          -- 'user' or 'assistant'
            content     TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            metadata    TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS memories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT NOT NULL,          -- 'fact', 'preference', 'event'
            content     TEXT NOT NULL,
            source      TEXT DEFAULT 'user',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent       TEXT NOT NULL,          -- 'instagram', 'whatsapp', 'network', etc.
            event_type  TEXT NOT NULL,
            payload     TEXT NOT NULL,
            status      TEXT DEFAULT 'pending', -- 'pending', 'done', 'error'
            timestamp   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS network_devices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_address TEXT UNIQUE,
            ip_address  TEXT,
            hostname    TEXT,
            vendor      TEXT,
            first_seen  TEXT,
            last_seen   TEXT,
            is_trusted  INTEGER DEFAULT 0,
            alias       TEXT
        );

        CREATE TABLE IF NOT EXISTS instagram_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT,
            followers   INTEGER,
            following   INTEGER,
            posts       INTEGER,
            fetched_at  TEXT
        );
    """)
    conn.commit()
    conn.close()
    print("[DB] SQLite database initialized.")


# ─── ChromaDB for vector memory ───────────────────────────────────────────────

_chroma_client = None


def get_chroma():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    return _chroma_client


def get_collection(name: str):
    client = get_chroma()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}
    )


# ─── Conversation History ──────────────────────────────────────────────────────

def save_message(session_id: str, role: str, content: str, metadata: dict = {}):
    conn = get_db()
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, timestamp, metadata) VALUES (?,?,?,?,?)",
        (session_id, role, content, datetime.datetime.now().isoformat(), json.dumps(metadata))
    )
    conn.commit()
    conn.close()


def get_history(session_id: str, limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT role, content, timestamp FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, limit)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]


# ─── Agent Events ──────────────────────────────────────────────────────────────

def log_agent_event(agent: str, event_type: str, payload: dict, status: str = "done"):
    conn = get_db()
    conn.execute(
        "INSERT INTO agent_events (agent, event_type, payload, status, timestamp) VALUES (?,?,?,?,?)",
        (agent, event_type, json.dumps(payload), status, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_recent_events(agent: Optional[str] = None, limit: int = 50) -> list[dict]:
    conn = get_db()
    if agent:
        rows = conn.execute(
            "SELECT * FROM agent_events WHERE agent=? ORDER BY id DESC LIMIT ?",
            (agent, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agent_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
