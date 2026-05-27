"""
HackKnow AI OS — FastAPI surface.

Endpoints:
  --- core ---
  GET  /healthcheck
  POST /execute          { goal, mode?, session? }
  POST /chat/stream      Server-Sent-Events streaming chat (LibreChat compatible)
  POST /delegate         { agent, task, context? }
  WS   /voice            voice loop (STT → orchestrate → TTS)

  --- key vault & meter ---
  GET    /keys
  POST   /keys           { provider, secret, label?, tier? }
  DELETE /keys/{id}
  POST   /keys/{id}/enable
  POST   /keys/{id}/disable
  GET    /meter

  --- queue (long-running jobs) ---
  GET  /jobs
  GET  /jobs/{id}

  --- agents ---
  GET  /agents
  POST /agents           { id, role, llm_tier, skills }   ← create runtime agent
  POST /agents/{id}/run  { task }                          ← convenience

  --- skills (incl. Skill Smith) ---
  GET  /skills
  POST /skills/author    { target }                        ← Skill Smith authors a draft
  POST /skills/promote   { name }                          ← move _proposed → active

  --- repos / fine-tune / workflows / browser / automations ---
  POST /repos            { repo, branch? }
  POST /finetune         { action, ... }
  GET  /workflows
  POST /workflows/run    { id, payload? }                  ← Flowise bridge
  POST /browser/run      { action, ... }
  POST /automations      { name, schedule, agent, task }
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from config.settings import ROOT
from core.logger import get_logger
from core.orchestrator import HackKnowOS

log = get_logger("server")

os_: HackKnowOS | None = None
# in-memory automations registry (persisted to .cache/automations.json)
AUTO_FILE = ROOT / ".cache" / "automations.json"
AUTO_FILE.parent.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global os_
    os_ = HackKnowOS()
    await os_.boot()
    log.success(f"HackKnow AI OS listening on http://{settings.hackknow_host}:{settings.hackknow_port}")
    yield
    if os_:
        await os_.shutdown()


app = FastAPI(title="HackKnow AI OS", lifespan=lifespan, version="0.2.0")
app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

UI_DIR = ROOT / "ui"
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


# ============================================================ models ====
class ExecuteRequest(BaseModel):
    goal: str
    session: str = "default"
    mode: str = "auto"


class DelegateRequest(BaseModel):
    agent: str
    task: str
    context: dict = {}


class StreamChatRequest(BaseModel):
    messages: list[dict]
    model: str | None = None
    stream: bool = True


class KeyAddRequest(BaseModel):
    provider: str
    secret: str
    label: str = ""
    tier: str = "free"


class AgentCreateRequest(BaseModel):
    id: str
    role: str
    llm_tier: str = "strong"
    skills: list[str] = []


class SkillAuthorRequest(BaseModel):
    target: str


class SkillPromoteRequest(BaseModel):
    name: str


class RepoRequest(BaseModel):
    repo: str
    branch: str = "main"


class AutomationRequest(BaseModel):
    name: str
    schedule: str    # cron-like or RRULE
    agent: str
    task: str


# =========================================================== UI shell ====
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(UI_DIR / "app.html")


@app.get("/voice", response_class=HTMLResponse)
async def voice_console():
    return FileResponse(UI_DIR / "voice_interface.html")


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(UI_DIR / "manifest.webmanifest")


@app.get("/sw.js")
async def sw():
    return FileResponse(UI_DIR / "sw.js", media_type="application/javascript")


# =========================================================== core ====
@app.get("/healthcheck")
async def healthcheck():
    if not os_:
        return {"status": "booting"}
    return {
        "status": "ok",
        "agents": list(os_.agents),
        "skills": os_.skills.names(),
        "vault_keys": len(os_.vault.keys),
        "active_keys": os_.meter.active_keys(),
        "zero_key_mode": len(os_.vault.keys) == 0,
        "model_default": settings.ollama_model,
    }


@app.post("/execute")
async def execute(req: ExecuteRequest):
    if not os_:
        raise HTTPException(503, "boot in progress")
    try:
        result = await os_.execute(req.goal, session=req.session, mode=req.mode)
        return {
            "summary": result.summary,
            "language": result.language,
            "job_id": result.job_id,
            "tasks": [
                {"id": t.id, "agent": t.agent, "status": t.status,
                 "result": t.result, "error": t.error}
                for t in result.tasks
            ],
        }
    except Exception as exc:
        log.error(f"/execute failed: {exc!r}")
        return JSONResponse(
            status_code=200,
            content={
                "summary": f"⚠ All providers failed. Check API keys in the vault. ({exc})",
                "language": "en",
                "job_id": None,
                "tasks": [],
                "error": str(exc),
            },
        )


@app.post("/delegate")
async def delegate(req: DelegateRequest):
    if not os_:
        raise HTTPException(503, "boot in progress")
    out = await os_.delegate(req.agent, {"task": req.task, **req.context})
    return {"result": out}


@app.post("/chat/stream")
async def chat_stream(req: StreamChatRequest):
    """SSE streaming chat, OpenAI compatible. Front-end consumes line-delimited `data: {…}`."""
    if not os_:
        raise HTTPException(503, "boot in progress")
    user_msg = next((m["content"] for m in reversed(req.messages) if m.get("role") == "user"), "")

    async def gen():
        # full result first, then stream-emulate in chunks
        try:
            result = await os_.execute(user_msg, mode="fast")
            full = result.summary
        except Exception as exc:
            full = f"[error] {exc}"
        chunk_size = 64
        for i in range(0, len(full), chunk_size):
            piece = full[i : i + chunk_size]
            yield "data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}) + "\n\n"
            await asyncio.sleep(0.015)
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# =========================================================== key vault ====
@app.get("/keys")
async def list_keys():
    if not os_:
        return []
    return os_.vault.list_public()


@app.post("/keys")
async def add_key(req: KeyAddRequest):
    if not os_:
        raise HTTPException(503, "boot in progress")
    try:
        key = os_.vault.add(req.provider, req.secret, label=req.label, tier=req.tier)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": key.id, "provider": key.provider, "label": key.label, "masked": key.masked()}


@app.delete("/keys/{key_id}")
async def delete_key(key_id: str):
    if not os_:
        raise HTTPException(503, "boot in progress")
    ok = os_.vault.remove(key_id)
    return {"removed": ok}


@app.post("/keys/{key_id}/enable")
async def enable_key(key_id: str):
    os_.vault.enable(key_id)
    return {"status": "ok"}


@app.post("/keys/{key_id}/disable")
async def disable_key(key_id: str):
    os_.vault.disable(key_id)
    return {"status": "ok"}


@app.get("/meter")
async def meter():
    if not os_:
        return {}
    return os_.meter.snapshot()


# =========================================================== queue ====
@app.get("/jobs")
async def list_jobs():
    if not os_:
        return []
    return await os_.queue.list_jobs()


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if not os_:
        raise HTTPException(503)
    j = await os_.queue.get(job_id)
    if not j:
        raise HTTPException(404, "no such job")
    return j.__dict__


# =========================================================== agents ====
@app.get("/agents")
async def list_agents():
    if not os_:
        return []
    return [
        {"id": aid, "role": agent.cfg.get("role", ""),
         "tier": agent.cfg.get("llm_tier", "strong"),
         "skills": agent.allowed_skills}
        for aid, agent in os_.agents.items()
    ]


@app.post("/agents")
async def create_runtime_agent(req: AgentCreateRequest):
    """Runtime agent — alive only for this server process unless persisted to agents.yaml."""
    if not os_:
        raise HTTPException(503)
    from agents.base import BaseAgent
    if req.id in os_.agents:
        raise HTTPException(400, "agent exists")
    cfg = {"role": req.role, "llm_tier": req.llm_tier, "skills": req.skills}
    os_.agents[req.id] = BaseAgent(agent_id=req.id, cfg=cfg, llm=os_.llm,
                                   memory=os_.memory, skills=os_.skills)
    return {"created": req.id}


@app.post("/agents/{agent_id}/run")
async def run_agent(agent_id: str, payload: dict):
    if not os_:
        raise HTTPException(503)
    out = await os_.delegate(agent_id, payload)
    return {"result": out}


# =========================================================== skills ====
@app.get("/skills")
async def list_skills():
    if not os_:
        return []
    return [{"name": n, "description": os_.skills.get(n).manifest.get("description", "")}
            for n in os_.skills.names()]


@app.post("/skills/author")
async def author_skill(req: SkillAuthorRequest):
    if not os_:
        raise HTTPException(503)
    agent = os_.agents.get("skill_smith")
    if not agent:
        raise HTTPException(400, "skill_smith agent not loaded")
    return await agent.author(req.target)


@app.post("/skills/promote")
async def promote_skill(req: SkillPromoteRequest):
    if not os_:
        raise HTTPException(503)
    agent = os_.agents.get("skill_smith")
    if not agent:
        raise HTTPException(400)
    return await agent.promote(req.name)


# =========================================================== repos ====
@app.post("/repos")
async def attach_repo(req: RepoRequest):
    if not os_:
        raise HTTPException(503)
    return await os_.skills.run("github", action="clone", repo=req.repo, branch=req.branch)


# =========================================================== finetune ====
@app.post("/finetune")
async def finetune(payload: dict):
    if not os_:
        raise HTTPException(503)
    return await os_.skills.run("finetune", **payload)


# =========================================================== workflows ====
@app.get("/workflows")
async def workflows():
    return {"engine": "native+flowise", "flowise": settings.flowise_base_url}


@app.post("/workflows/run")
async def workflow_run(payload: dict):
    if not os_:
        raise HTTPException(503)
    return await os_.skills.run("workflow", **payload)


# =========================================================== browser ====
@app.post("/browser/run")
async def browser_run(payload: dict):
    if not os_:
        raise HTTPException(503)
    return await os_.skills.run("browser", **payload)


# =========================================================== automations ====
def _load_automations() -> list[dict]:
    if AUTO_FILE.exists():
        return json.loads(AUTO_FILE.read_text())
    return []


def _save_automations(items: list[dict]) -> None:
    AUTO_FILE.write_text(json.dumps(items, indent=2))


@app.get("/automations")
async def list_automations():
    return _load_automations()


@app.post("/automations")
async def add_automation(req: AutomationRequest):
    items = _load_automations()
    item = {"id": uuid.uuid4().hex[:10], **req.dict(), "enabled": True}
    items.append(item)
    _save_automations(items)
    return item


@app.delete("/automations/{aid}")
async def delete_automation(aid: str):
    items = [a for a in _load_automations() if a["id"] != aid]
    _save_automations(items)
    return {"removed": aid}


# =========================================================== voice ws ====
@app.post("/loop")
async def loop(payload: dict):
    """SSE stream of an autonomous Manus/Devin-style loop run."""
    if not os_:
        raise HTTPException(503)
    goal = payload.get("goal", "")
    max_steps = int(payload.get("max_steps", 12))

    async def gen():
        async for event in os_.loop.stream(goal, max_steps=max_steps):
            yield "data: " + json.dumps(event) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.websocket("/voice")
async def voice_ws(ws: WebSocket):
    await ws.accept()
    if not os_:
        await ws.send_json({"error": "boot in progress"})
        await ws.close()
        return
    try:
        while True:
            msg = await ws.receive()
            if "bytes" in msg and msg["bytes"]:
                tmp = ROOT / ".cache" / "incoming.wav"
                tmp.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(msg["bytes"])
                stt = await os_.skills.run("voice", mode="stt", audio_path=str(tmp))
                user_text = stt.get("text", "") if isinstance(stt, dict) else ""
                if not user_text.strip():
                    await ws.send_json({"warning": "no speech detected"}); continue
                await ws.send_json({"user_text": user_text, "lang": stt.get("language")})
                result = await os_.execute(user_text, mode="fast")
                await ws.send_json({"assistant_text": result.summary})
                # cloned voice if available, else kokoro
                try:
                    tts = await os_.skills.run("voice_clone", text=result.summary,
                                                voice="male", lang=result.language)
                except Exception:
                    tts = await os_.skills.run("voice", mode="tts",
                                                text=result.summary, lang=result.language)
                if isinstance(tts, dict) and tts.get("path"):
                    await ws.send_bytes(Path(tts["path"]).read_bytes())
            elif "text" in msg and msg["text"]:
                payload = json.loads(msg["text"]) if msg["text"].startswith("{") else {"goal": msg["text"]}
                result = await os_.execute(payload.get("goal", ""), mode="fast")
                await ws.send_json({"assistant_text": result.summary, "language": result.language})
    except WebSocketDisconnect:
        log.info("voice client disconnected")


def main():
    import uvicorn
    uvicorn.run("server.api:app", host=settings.hackknow_host,
                port=settings.hackknow_port,
                log_level=settings.hackknow_log_level.lower(), reload=False)


if __name__ == "__main__":
    main()
