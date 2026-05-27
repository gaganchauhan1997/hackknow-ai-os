"""
Workflow skill — Flowise webhook bridge OR native inline chain runner.

When Flowise isn't reachable (lean Render deploy), the inline runner kicks in:
each step is sent to the LLM router sequentially and outputs feed the next step.
"""

from __future__ import annotations

from typing import Any

import httpx

from config import settings
from core.logger import get_logger

log = get_logger("skill:workflow")

manifest = {
    "description": "Run a Flowise flow by ID, or run an inline chain locally via the LLM router.",
    "parameters": {
        "type": "object",
        "properties": {
            "flow_id": {"type": "string"},
            "payload": {"type": "object"},
            "inline_steps": {"type": "array", "items": {"type": "string"}},
            "goal":         {"type": "string"},
        },
    },
}


async def _inline_chain(steps: list[str]) -> dict:
    """Run a list of prompts in sequence; each step receives the previous output."""
    from core.llm_router import LLMRouter
    llm = LLMRouter()
    transcript: list[dict] = []
    prev = ""
    try:
        for i, step in enumerate(steps, 1):
            prompt = step if not prev else f"{step}\n\nContext from previous step:\n{prev[:4000]}"
            out = await llm.chat(
                messages=[
                    {"role": "system", "content": "You are a step worker in a HackKnow chain. Be concise and concrete."},
                    {"role": "user", "content": prompt},
                ],
                tier="fast", max_tokens=800,
            )
            transcript.append({"step": i, "prompt": step[:200], "output": out})
            prev = out
    finally:
        await llm.aclose()
    return {"engine": "inline-chain", "steps_run": len(transcript),
            "transcript": transcript, "final": prev}


async def run(
    flow_id: str | None = None,
    payload: dict | None = None,
    inline_steps: list[str] | None = None,
    goal: str | None = None,
    **_: Any,
) -> dict:
    payload = payload or {}

    # 1) Flowise path
    if flow_id:
        url = f"{settings.flowise_base_url}/api/v1/prediction/{flow_id}"
        headers = {}
        if settings.flowise_api_key:
            headers["Authorization"] = f"Bearer {settings.flowise_api_key}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                r = await client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                return {"source": "flowise", "result": r.json()}
            except httpx.ConnectError:
                log.warning("Flowise unreachable — falling back to inline chain")
                # if user also provided inline steps, run them
                if inline_steps:
                    return await _inline_chain(inline_steps)
                if goal:
                    return await _inline_chain([goal])
                return {"status": "skipped", "reason": "Flowise not reachable and no inline_steps/goal provided"}

    # 2) Inline chain
    if inline_steps:
        return await _inline_chain(inline_steps)
    if goal:
        return await _inline_chain([goal])

    return {"status": "noop", "hint": "Provide flow_id (Flowise) or inline_steps / goal (native chain)."}
