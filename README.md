# HackKnow AI OS

> **Autonomous AI operating system.** JARVIS-style orchestrator, 21 specialist agents, 18 plug-in skills, 50-key per provider rotation, zero-key local fallback, voice cloning with Boss's own samples, full LibreChat-style chat UI, Docker / Tauri / PWA / Android packaging.

Built for **Myth (Hackknow)** on the principle of **"Free intelligence, infinite capability."**

[Architecture overview →](docs/ARCHITECTURE.md) · [Deploy →](docs/DEPLOY.md) · [Multi-key guide →](docs/MULTI_KEY_GUIDE.md) · [Voice →](docs/VOICE.md) · [Migrate YAHAVIS →](docs/MIGRATION_YAHAVIS.md)

---

## What it is

A modular Python-async platform that combines the strongest open-source repos in agents, voice, browser automation, fine-tuning, RAG, and ecommerce into a single product:

| Inspired by  | Borrowed concepts                          |
|--------------|--------------------------------------------|
| HyperAgent   | the orchestrator + skill registry          |
| LibreChat    | the front-of-house chat UI                 |
| Manus AI     | autonomous task execution                  |
| Devin / OpenDevin | vibe coding + dev sandbox             |
| JARVIS       | "Boss" persona, voice loop, agent swarm    |

…rebranded entirely as **HackKnow.com**.

```
   USER  (Hindi / English · voice / text · web / desktop / Android)
                       ▼
              ┌────────────────┐
              │   CEO Agent    │  ← JARVIS persona, addresses Boss
              └────────┬───────┘
                       ▼
              ┌────────────────┐
              │  Task Shredder │  ← splits big goals → atomic micro-tasks
              └────────┬───────┘
                       ▼
              ┌────────────────┐
              │ Durable Queue  │  ← .cache/queue.json, resumes after restart
              └────────┬───────┘
                       ▼
   ┌─────────────────────────────────────────────────────────┐
   │  21 specialist agents     ·  hot-loaded skills           │
   │  CEO · Planner · Developer · Marketing · SEO · Content   │
   │  Reel · Video · Ecommerce · Data · Excel · Automation    │
   │  Voice · Research · Social · Skill Smith · Fine Tune     │
   │  Debug · Browser · Deployment · Image                    │
   └─────────────────────────────────────────────────────────┘
                       ▼
   ┌─────────────────────────────────────────────────────────┐
   │  18 plug-in skills (wrap 15+ reference repos)            │
   │  browser · voice · voice_clone · code_exec · content     │
   │  video · data · excel · ecommerce · workflow · research  │
   │  realtime_search · rag · finetune · vibe_coding · github │
   │  desktop · android                                       │
   └─────────────────────────────────────────────────────────┘
                       ▼
   ┌─────────────────────────────────────────────────────────┐
   │  Vault-aware LLM router  (up to 50 keys × 11 providers)  │
   │  Groq · Gemini · OpenAI · Anthropic · Cohere · Mistral   │
   │  Together · OpenRouter · DeepSeek · Perplexity · HF      │
   │  Ollama (local · zero-key fallback)                      │
   └─────────────────────────────────────────────────────────┘
```

---

## Quick start

### Local Python

```bash
git clone https://github.com/<you>/hackknow-ai-os && cd hackknow-ai-os
bash setup.sh                          # venv + deps + Playwright + voice
cp .env.example .env  &&  nano .env    # paste any free-tier keys you have
bash scripts/start_server.sh           # → http://localhost:8787
```

### Docker compose (full stack)

```bash
docker compose up -d
# api + ollama + qdrant + redis + flowise
```

### Desktop installer (Tauri)

```bash
cd packaging/tauri && cargo tauri build
# → .dmg / .msi / .deb / .AppImage
```

### Android (Capacitor or PWA)

```bash
# PWA: open the deployed URL in Chrome on Android → "Add to home screen"
# Native APK:
cd packaging/capacitor && npx cap add android && cd android && ./gradlew assembleDebug
```

---

## What the system can do

| Domain               | Capability                                                      |
|----------------------|-----------------------------------------------------------------|
| Conversation         | Hindi + English chat, voice loop, JARVIS persona                |
| Code                 | Author, run, debug Python in sandboxed subprocess               |
| Browser              | Headless Playwright + browser-use; autonomous form-fill         |
| Content              | Image gen (ComfyUI), reels (AnimateDiff), video (Remotion)      |
| Data                 | pandas-ai NL analysis, Plotly dashboards, Power-BI-style XLSX   |
| Ecommerce            | WooCommerce REST + Medusa CRUD on shop.hackknow.com             |
| Research             | DuckDuckGo + Tavily + Exa + Serper + Brave + Firecrawl + Jina   |
| RAG                  | Chroma vector store with PDF / DOCX / MD / TXT ingestion        |
| Voice                | faster-whisper STT + XTTS-v2 voice cloning (Boss's own samples) |
| Fine-tune            | LoRA / QLoRA / Ollama Modelfiles via PEFT                       |
| Skills               | Skill Smith authors brand-new skills autonomously               |
| Automations          | Cron-scheduled agent runs                                       |
| Workflows            | Native DAG + Flowise webhook bridge                             |
| Devices              | Desktop (PyAutoGUI) + Android (adb)                             |

---

## Multi-key vault

Paste up to **50 keys × 11 providers** in the UI. Big goals come in, the Task Shredder splits them into atomic micro-tasks, the queue runs them across all keys, pauses when everything cools, resumes when any key refreshes.

```
 user submits goal
       │
 task shredder ──► JSON DAG of micro-tasks
       │
 durable queue ──► .cache/queue.json (survives restarts)
       │
 LLM router ──► picks freshest key from vault (50 per provider)
       │
 key cooling? → next key
 all exhausted? → pause + schedule wake_after(refresh_seconds)
 wake → resume cursor
 still nothing? → fall through to local Ollama (zero-key mode)
```

See [`docs/MULTI_KEY_GUIDE.md`](docs/MULTI_KEY_GUIDE.md) for the full meter spec.

---

## License

MIT.
