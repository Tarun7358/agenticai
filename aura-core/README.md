# AURA — Personal AI Assistant

> Always-on, locally-running personal intelligence. 100% private. Runs on your laptop.

## 🚀 Quick Start

### Step 1: Install Ollama (AI Brain)
```
winget install ollama.ollama
```
Then in a terminal:
```
ollama serve
ollama pull mistral
ollama pull nomic-embed-text
```

### Step 2: Configure AURA
```
cd backend
copy .env.example .env
```
Edit `.env` with your Instagram username/password and other settings.

### Step 3: Launch AURA

You have two ways to run AURA:

#### Option A: Iron Man JARVIS Holographic HUD (Recommended)
Double-click **`LAUNCH-JARVIS-HUD.bat`**
- Floating, transparent Iron Man Arc-Reactor HUD right on your desktop!
- Always listening for **"Hey Aura"** or **"Jarvis"** wake word.
- Global Hotkey: `Ctrl+Shift+A` or `Alt+Space` to summon instantly.
- Voice response (TTS) + Holographic sound wave visualizer.
- Can be dragged anywhere, minimized to a sleek floating mini orb.

#### Option B: Full Web Dashboard
Double-click **`LAUNCH-AURA.bat`** — starts backend + browser dashboard at `http://localhost:5173`.

---

## 📦 Project Structure

```
aura-core/
├── LAUNCH-AURA.bat          ← One-click launcher
├── start-backend.bat
├── start-frontend.bat
│
├── backend/
│   ├── main.py              ← FastAPI app (all endpoints)
│   ├── config.py            ← Settings from .env
│   ├── requirements.txt
│   ├── .env.example         ← Copy to .env and fill in
│   │
│   ├── agents/
│   │   ├── network_agent.py    ← WiFi scanner, device tracker
│   │   ├── instagram_agent.py  ← Instagram analytics
│   │   └── file_agent.py       ← File indexer & semantic search
│   │
│   ├── memory/
│   │   └── store.py         ← SQLite + ChromaDB memory
│   │
│   └── utils/
│       └── llm.py           ← Ollama AI core
│
└── frontend/
    └── src/
        ├── App.tsx           ← Main app, navigation
        ├── ChatPage.tsx      ← AI chat with streaming
        ├── DashboardPage.tsx ← Overview + agent status
        ├── NetworkPage.tsx   ← WiFi device monitor
        ├── InstagramPage.tsx ← Instagram analytics
        ├── FilesPage.tsx     ← Semantic file search
        ├── api.ts            ← Backend API client
        └── index.css         ← Design system
```

---

## 🔌 Features

| Feature | Status |
|---------|--------|
| AI Chat (streaming) | ✅ Ready |
| Dashboard | ✅ Ready |
| Network Scanner | ✅ Ready |
| Instagram Analytics | ✅ Ready |
| File Semantic Search | ✅ Ready |
| WhatsApp | 🔜 Phase 2 |
| Email | 🔜 Phase 2 |
| Voice Input | 🔜 Phase 3 |

---

## 💡 Tips

- **8GB RAM**: Don't run too many apps alongside AURA. Mistral 7B uses ~5GB RAM+VRAM combined.
- **First launch**: The AI model download (~4GB) takes a few minutes. Do it once on good WiFi.
- **File indexing**: Set `WATCHED_FOLDERS` in `.env` to your Documents/Downloads folders.
- **Network scanning**: Run as Administrator for best ARP results on Windows.

---

## 🔐 Privacy

Everything runs locally. No data sent to cloud. Your conversations, files, and network data stay on your machine.
