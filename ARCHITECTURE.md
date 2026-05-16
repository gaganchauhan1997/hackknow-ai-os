# HackKnow AI OS — Architecture

> A modular autonomous multi-agent OS. JARVIS-style coordination over a free-tier LLM pool and 15 best-in-class open-source repos exposed as plug-in skills.

---

## 1. Layering

```
┌──────────────────────────────────────────────────────────────────┐
│ Interface  : Voice console UI  · REST  · WebSocket  · Demos      │
├──────────────────────────────────────────────────────────────────┤
│ Orchestration  : CEO Agent → Planner → Workflow DAG              │
│                 (CrewAI / AutoGen / LangChain adapters optional)  │
├──────────────────────────────────────────────────────────────────┤
│ Agents (15 specialists)                                          │
│   ceo · planner · developer · marketing · seo · content_creator   │
│   reel_creator · video_editor · ecommerce · data_analyst         │
│   excel_dashboard · automation · voice_assistant · research      │
│   social_media                                                   │
├──────────────────────────────────────────────────────────────────┤
│ Skills (plug-in modules wrapping reference repos)                │
│   browser · voice · code_exec · content · video · data           │
│   ecommerce · workflow · research                                │
├──────────────────────────────────────────────────────────────────┤
│ Core   : LLM router · Memory · Planner · Workflow · i18n         │
│          Skill registry · Logger                                  │
├──────────────────────────────────────────────────────────────────┤
│ Providers (free tier)                                            │
│   Groq · Gemini · Cohere · Mistral · Together · OpenRouter       │
│   HuggingFace · Ollama (local)                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Request Lifecycle

```
User input (voice / text, Hindi or English)
        │
        ▼
i18n.detect_language → CEO Agent receives goal
        │
        ▼
Planner emits JSON DAG of subtasks
        │
        ▼
WorkflowEngine schedules tasks in parallel respecting depends_on
        │                ┌── agent.run() pulls memory + tools as needed
        ├─► agent A      │
        ├─► agent B  ────┤   each agent may call skills (browser, voice, …)
        ├─► agent C      │   which talk to external repos / APIs
        ▼                └── LLM Router rotates across free providers
CEO synthesises final answer (lang-aware) → TTS (optional) → user
```

---

## 3. Free-Tier LLM Router (`core/llm_router.py`)

* Loads provider definitions from `config/llm_pool.yaml`.
* Skips providers without configured keys.
* Round-robins; tracks per-provider RPM and consecutive errors.
* Falls back to the next provider on 429 / 5xx / transport errors.
* Tiers: `fast`, `strong`, `reasoning`, `long_context` — each agent declares a preferred tier.

| Provider     | Free quota (rough) | Use for                         |
|--------------|--------------------|---------------------------------|
| Groq         | very generous      | low-latency reasoning           |
| Gemini Flash | 15 RPM             | multimodal / long context       |
| Cohere       | trial credits      | embeddings + RAG                |
| Mistral      | free dev tier      | reasoning                       |
| Together     | free credits       | open-weights diversity          |
| OpenRouter   | `:free` models     | marketplace                     |
| HuggingFace  | inference API      | quick experimentation           |
| Ollama       | local              | offline fallback                |

---

## 4. Memory (`core/memory.py`)

* **TurnBuffer** — sliding window of recent turns, per scope (`session:*`, `agent:*`).
* **VectorMemory** — Chroma persistent client at `.cache/chroma`. Embeddings via sentence-transformers locally (no API cost).
* Public surface:
  * `push(scope, role, content)`
  * `history(scope)`
  * `remember(namespace, text, metadata)`
  * `recall(namespace, query, k)`

---

## 5. Planner (`core/planner.py`)

LLM call returning strict JSON. We forbid prose, ask for a small DAG (1–8 tasks), and always end with a `ceo` synthesizer task. Failed JSON triggers a regex fallback then a retry on a stronger tier.

Example output:
```json
{
  "plan": [
    {"id": "t1", "agent": "research",  "instruction": "Trend snapshot for Hackknow mug niche", "depends_on": []},
    {"id": "t2", "agent": "content_creator", "instruction": "7 social posts in Hinglish", "depends_on": ["t1"]},
    {"id": "t3", "agent": "reel_creator", "instruction": "2 reel scripts 15s each", "depends_on": ["t1"]},
    {"id": "t4", "agent": "ceo", "instruction": "Synthesize the campaign", "depends_on": ["t2","t3"]}
  ]
}
```

---

## 6. Workflow Engine (`core/workflow.py`)

* Pure-async DAG scheduler.
* Tasks become "running" as soon as their dependencies finish.
* `WorkflowResult` carries the per-task status, error, and result.
* Detects cycles / unreachable tasks and raises.

---

## 7. Skills

Each skill is a self-contained Python package exposing:

```python
manifest = {"description": "...", "parameters": {...}}

async def run(**kwargs): ...
```

The `SkillRegistry` discovers them at boot, generates OpenAI-style tool specs, and gates access per-agent through `cfg["skills"]`.

| Skill        | Wraps                                  |
|--------------|----------------------------------------|
| browser      | browser-use + Playwright               |
| voice        | faster-whisper + kokoro                |
| code_exec    | Open-Interpreter style sandboxed exec  |
| content      | ComfyUI + AnimateDiff                  |
| video        | Remotion + ffmpeg                      |
| data         | pandas-ai                              |
| ecommerce    | Medusa + WooCommerce                   |
| workflow     | Flowise + LangChain                    |
| research     | DuckDuckGo + page extraction           |

---

## 8. Agents

All 15 agents share `BaseAgent.run(instruction, context)`. They differ only in:
* `cfg["role"]` (the system prompt fragment)
* `cfg["llm_tier"]` (preferred tier in the router)
* `cfg["skills"]` (which skills they can call)
* Optional overrides (`Developer`, `Reel Creator`, `Social Media`, etc.)

Override style example — `ReelCreatorAgent.run` first plans the reel as JSON, then calls `content` → `voice` → `video` skills in sequence to produce the final MP4.

---

## 9. Hindi + English

* `core/i18n.detect_language` — Devanagari regex + Hinglish hint vocabulary.
* All system prompts get a localised `style_prefix`; the final synthesis is asked to reply in the user's language.
* TTS routes to `kokoro_voice_hi` vs `kokoro_voice_en` automatically.

---

## 10. Self-Improving Skill System

* `SkillRegistry.discover()` re-scans `skills/` on demand (and on server restart).
* When an agent declares a skill failure, it can drop a proposal file under `skills/_proposed/<name>.md` describing the gap; you review and promote.
* Skill manifests double as JSON-schema tool specs so a future "skill-builder agent" can author them autonomously.

---

## 11. Server

* **FastAPI** at `server/api.py`:
  * `GET  /`            → voice console UI
  * `GET  /dashboard`   → agent dashboard
  * `GET  /healthcheck` → registry status
  * `POST /execute`     → autonomous run (planner + workflow)
  * `POST /delegate`    → direct agent call
  * `WS   /voice`       → streaming voice loop (STT → orchestrator → TTS)

---

## 12. Extending

```python
# 1) Add a new agent — edit config/agents.yaml + drop agents/<name>_agent.py
# 2) Add a new skill — create skills/<name>/__init__.py with manifest + run()
# 3) Add a new LLM provider — add to config/llm_pool.yaml + a branch in core/llm_router._call
```

That's it. Boot the OS and the new pieces are live.
