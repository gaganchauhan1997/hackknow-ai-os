"""
Workflow skill — Flowise webhook bridge + native chain runner.

Repos:
  - https://github.com/FlowiseAI/Flowise
  - https://github.com/langchain-ai/langchain
"""

from __future__ import annotations

from typing import Any

import httpx

from config import settings
from core.logger import get_logger

log = get_logger("skill:workflow")

manifest = {
    "description": "Invoke a Flowise flow by ID, or run an inline chain (list of LLM prompts).",
    "parameters": {
        "type": "object",
        "properties": {
            "flow_id": {"type": "string"},
            "payload": {"type": "object"},
            "inline_steps": {"type": "array"},
        },
    },
}


async def run(
    flow_id: str | None = None,
    payload: dict | None = None,
    inline_steps: list[str] | None = None,
    **_: Any,
) -> dict:
    payload = payload or {}
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
                return {"status": "skipped", "reason": "Flowise not reachable"}
    if inline_steps:
        return {"source": "inline", "steps": inline_steps,
                "note": "Use Developer/Planner agents to actually run these as a chain."}
    return {"status": "noop"}
