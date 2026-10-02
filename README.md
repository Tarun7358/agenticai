# AURA — Personal Agentic AI & JARVIS HUD

> Always-on, 100% local personal AI assistant running on your laptop. Powered by local LLMs (Ollama), real-time network scanning, Instagram analytics, semantic file indexing, and an Iron Man JARVIS floating holographic HUD.

---

## ⚡ Features
- 🎙️ **Iron Man JARVIS HUD**: Floating, transparent arc-reactor HUD with real-time audio visualizer, wake word ("Hey Aura" / "Jarvis"), and offline voice replies (TTS).
- 🧠 **Local LLM Intelligence**: Runs Mistral / Llama via Ollama directly on your GPU (RTX 2050) & 8GB RAM without cloud dependencies.
- 📡 **Network Security Agent**: Continuous local network device scanner and rogue device alerts.
- 📸 **Instagram Analytics Agent**: Account stats, follower tracker, engagement analysis.
- 📁 **Semantic File Search Agent**: Watched folder indexer for fast semantic and keyword search.
- 🖥️ **Web Dashboard**: Full React + Vite dashboard for multi-device management.

---

## 🚀 Quick Setup on Any Laptop

### 1. Clone the Repository
```bash
git clone https://github.com/Tarun7358/agenticai.git
cd agenticai
```

### 2. Setup Python Virtual Environment
```cmd
cd aura-core\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
*(Edit `.env` with your Instagram credentials and watched folders).*

### 3. Setup Frontend (Optional for Web Dashboard)
```cmd
cd ..\frontend
npm install
npm run build
```

### 4. Install Ollama & AI Models
Download from [ollama.com](https://ollama.com/download) or run:
```cmd
winget install Ollama.Ollama
ollama serve
ollama pull mistral
ollama pull nomic-embed-text
```

---

## 🎮 Launching AURA

- **Iron Man JARVIS HUD**: Double-click `aura-core\LAUNCH-JARVIS-HUD.bat`
  - Wake word: `"Hey Aura"` or `"Jarvis"`
  - Hotkey: `Ctrl+Shift+A` or `Alt+Space`
- **Web Dashboard**: Double-click `aura-core\LAUNCH-AURA.bat` (opens `http://localhost:5173`)
