"""
AURA / JARVIS Sovereign Epistemic Long-Term Memory Agent.
=========================================================
Persistent personal memory engine using local ChromaDB and JSON backup.
- Stores facts, preferences, contacts, projects, and custom directives.
- Contextual semantic recall automatically enriches Jarvis reasoning.
- 100% sovereign and local: data stays strictly on local disk.
"""

import os
import re
import json
import time
import uuid
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
DATA_DIR = os.path.join(BACKEND_DIR, "data")
MEMORY_FILE = os.path.join(DATA_DIR, "personal_memory.json")
CHROMA_DIR = os.path.join(DATA_DIR, "chromadb")

_chroma_collection = None


def _init_chroma():
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _chroma_collection = client.get_or_create_collection("jarvis_personal_memory")
        return _chroma_collection
    except Exception as e:
        print(f"[MemoryAgent] ChromaDB init note ({e}), using JSON store.")
        return None


def _load_json_memories() -> List[Dict[str, Any]]:
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_json_memories(memories: List[Dict[str, Any]]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[MemoryAgent] Error saving memory: {e}")


def save_fact(fact: str, category: str = "general") -> str:
    """Saves a permanent fact or preference to long-term memory."""
    clean_fact = fact.strip()
    if not clean_fact:
        return "Sir, I didn't catch the fact you wanted me to remember."

    fact_id = str(uuid.uuid4())[:8]
    entry = {
        "id": fact_id,
        "fact": clean_fact,
        "category": category,
        "timestamp": time.time(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    # 1. Save to JSON
    memories = _load_json_memories()
    # Check if duplicate or update
    for m in memories:
        if m.get("fact", "").lower() == clean_fact.lower():
            return f"I already remember that, Sir: \"{clean_fact}\"."
    memories.append(entry)
    _save_json_memories(memories)

    # 2. Save to ChromaDB
    col = _init_chroma()
    if col:
        try:
            col.add(
                ids=[fact_id],
                documents=[clean_fact],
                metadatas=[{"category": category, "created_at": entry["created_at"]}]
            )
        except Exception:
            pass

    return f"I have committed that to memory, Sir: \"{clean_fact}\"."


def recall_facts(query: str, limit: int = 3) -> List[str]:
    """Retrieves relevant personal memories matching query."""
    q_low = query.lower().strip()
    col = _init_chroma()
    if col:
        try:
            res = col.query(query_texts=[query], n_results=min(limit, 10))
            docs = res.get("documents", [[]])[0]
            if docs:
                return docs[:limit]
        except Exception:
            pass

    # Keyword/substring fallback from JSON
    memories = _load_json_memories()
    results = []
    keywords = [w for w in re.findall(r'\b[a-zA-Z0-9_-]{3,}\b', q_low) if w not in ["what", "who", "when", "where", "how", "tell", "remember", "about", "your", "the"]]
    for m in reversed(memories):
        f = m.get("fact", "")
        if any(k in f.lower() for k in keywords) or not keywords:
            if f not in results:
                results.append(f)
        if len(results) >= limit:
            break

    return results


def get_memory_context_snippet(query: str = "") -> str:
    """Returns formatted block of relevant personal memories for LLM prompt."""
    recalled = recall_facts(query, limit=4) if query else []
    if not recalled:
        # Pull top 3 most recent facts
        all_m = _load_json_memories()
        recalled = [m["fact"] for m in all_m[-3:]] if all_m else []

    if not recalled:
        return ""
    return "[Personal Long-Term Memory & Directives]:\n" + "\n".join(f"- {fact}" for fact in recalled)


def parse_memory_command(query: str) -> Optional[str]:
    """Parses natural voice memory commands like 'remember that I have a flight at 6' or 'what do you remember about Tarun'."""
    q = query.strip()

    # 1. Saving facts
    m = re.search(r'\b(?:remember\s+(?:that\s+)?|commit\s+to\s+memory(?:\s+that)?|keep\s+in\s+mind(?:\s+that)?|note\s+that)\s*(.+)$', q, flags=re.IGNORECASE)
    if m and not any(k in q.lower() for k in ["what do you", "do you remember", "what do i"]):
        fact = m.group(1).strip()
        fact = re.sub(r'^(?:that|saying|about)\s+', '', fact, flags=re.IGNORECASE).strip()
        return save_fact(fact)

    # 2. Recalling facts about a specific topic/entity (e.g. "what do you remember about Tarun" or "recall Tarun")
    m_topic = re.search(r'\b(?:what\s+do\s+you\s+remember\s+about|do\s+you\s+remember\s+about|tell\s+me\s+about|recall(?:\s+facts\s+about)?)\s*(.+)$', q, flags=re.IGNORECASE)
    if m_topic:
        topic = m_topic.group(1).strip(" ?.")
        recalled = recall_facts(topic, limit=3)
        if recalled:
            return f"Regarding {topic}, Sir: " + "; ".join(recalled)
        return f"I don't have any specific notes recorded regarding {topic} yet, Sir."

    # 3. Listing general memories
    if re.search(r'\b(?:what\s+do\s+you\s+remember|list\s+(?:my\s+)?memories|show\s+memories)\b', q, flags=re.IGNORECASE):
        memories = _load_json_memories()
        if not memories:
            return "My personal memory database is currently empty, Sir. Tell me 'remember that...' anytime to store notes."
        facts = [f"• {m['fact']}" for m in memories[-4:]]
        return f"Sir, here are key items from your personal memory database:\n" + "\n".join(facts)

    return None
