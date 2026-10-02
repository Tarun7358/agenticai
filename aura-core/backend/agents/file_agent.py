"""
AURA File Agent
Watches your folders, indexes documents, and enables natural-language file search.
Uses ChromaDB for vector-based semantic search across your files.
"""

import os
import hashlib
import datetime
from pathlib import Path
from typing import Optional
import asyncio

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import settings
from memory.store import get_collection, get_db, log_agent_event
from utils.llm import get_embedding, summarize


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts", ".json", ".csv"}
MAX_FILE_SIZE_MB = 10


def read_file_content(filepath: str) -> Optional[str]:
    """Read file content based on extension."""
    ext = Path(filepath).suffix.lower()
    try:
        if ext in {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv"}:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()[:50000]  # cap at 50k chars

        elif ext == ".pdf":
            from PyPDF2 import PdfReader
            reader = PdfReader(filepath)
            text = ""
            for page in reader.pages[:20]:  # first 20 pages
                text += page.extract_text() or ""
            return text[:50000]

        elif ext == ".docx":
            import docx
            doc = docx.Document(filepath)
            return "\n".join(p.text for p in doc.paragraphs)[:50000]
    except Exception as e:
        print(f"[Files] Could not read {filepath}: {e}")
    return None


def file_hash(filepath: str) -> str:
    """Get MD5 hash of file for change detection."""
    try:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read(65536)).hexdigest()
    except Exception:
        return ""


async def index_file(filepath: str) -> bool:
    """Index a single file into ChromaDB."""
    path = Path(filepath)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False
    if path.stat().st_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        return False

    content = read_file_content(filepath)
    if not content or len(content.strip()) < 20:
        return False

    fhash = file_hash(filepath)
    doc_id = hashlib.md5(filepath.encode()).hexdigest()

    collection = get_collection("files")

    # Check if already indexed with same hash
    try:
        existing = collection.get(ids=[doc_id])
        if existing["ids"] and existing["metadatas"][0].get("hash") == fhash:
            return False  # unchanged
    except Exception:
        pass

    # Get embedding
    embedding = await get_embedding(content[:2000])  # embed first 2k chars
    if not embedding:
        return False

    metadata = {
        "filepath": str(filepath),
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "modified": datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        "hash": fhash,
        "indexed_at": datetime.datetime.now().isoformat(),
    }

    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[content[:5000]],
        metadatas=[metadata],
    )
    print(f"[Files] Indexed: {path.name}")
    return True


async def index_folder(folder: str) -> dict:
    """Recursively index all supported files in a folder."""
    indexed = 0
    skipped = 0
    folder_path = Path(folder)
    if not folder_path.exists():
        return {"status": "error", "message": f"Folder not found: {folder}"}

    for filepath in folder_path.rglob("*"):
        if filepath.is_file():
            try:
                result = await index_file(str(filepath))
                if result:
                    indexed += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"[Files] Error indexing {filepath}: {e}")
                skipped += 1

    log_agent_event("files", "folder_indexed", {"folder": folder, "indexed": indexed, "skipped": skipped})
    return {"status": "ok", "indexed": indexed, "skipped": skipped, "folder": folder}


async def search_files(query: str, n_results: int = 5) -> list[dict]:
    """Semantic search across indexed files."""
    embedding = await get_embedding(query)
    if not embedding:
        return []

    collection = get_collection("files")
    try:
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            output.append({
                "content_snippet": results["documents"][0][i][:400],
                "filepath": results["metadatas"][0][i]["filepath"],
                "filename": results["metadatas"][0][i]["filename"],
                "relevance": round(1 - results["distances"][0][i], 3),
                "modified": results["metadatas"][0][i].get("modified", ""),
            })
        return output
    except Exception as e:
        print(f"[Files] Search error: {e}")
        return []


def get_indexed_stats() -> dict:
    """How many files are indexed."""
    collection = get_collection("files")
    try:
        count = collection.count()
        return {"indexed_files": count}
    except Exception:
        return {"indexed_files": 0}


# ─── Watchdog: auto-index new/changed files ───────────────────────────────────

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self._loop = asyncio.new_event_loop()

    def on_modified(self, event):
        if not event.is_directory:
            asyncio.run(index_file(event.src_path))

    def on_created(self, event):
        if not event.is_directory:
            asyncio.run(index_file(event.src_path))


_observer: Optional[Observer] = None


def start_file_watcher():
    global _observer
    folders = [f.strip() for f in settings.watched_folders.split(",") if f.strip()]
    if not folders:
        print("[Files] No folders configured for watching (set WATCHED_FOLDERS in .env)")
        return

    handler = FileChangeHandler()
    _observer = Observer()
    for folder in folders:
        if Path(folder).exists():
            _observer.schedule(handler, folder, recursive=True)
            print(f"[Files] Watching: {folder}")
    _observer.start()


def stop_file_watcher():
    global _observer
    if _observer:
        _observer.stop()
        _observer.join()
