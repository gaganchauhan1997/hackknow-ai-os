"""
Task Shredder — splits a user goal into atomic micro-tasks sized so each one
fits comfortably inside a single free-tier key call.

This is the agent Boss asked for: paste 50 keys, big goal goes in, micro-tasks
come out, queue executes them one at a time, key vault rotates underneath.
"""

from __future__ import annotations

import json
import re

from config import settings
from core.llm_router import LLMRouter
from core.logger import get_logger

log = get_logger("shredder")

_SHREDDER_SYSTEM = """You are the Task Shredder inside HackKnow AI OS.

You receive a user goal and split it into the SMALLEST useful atomic micro-tasks.
Each micro-task must:
  - be solvable by one agent in a single LLM call (≈ 1500-2500 tokens output)
  - have a clear, concrete output description
  - reference a specific specialist agent ID from the list below
  - declare its `cost_estimate_tokens` (rough total tokens for the call)

Available specialist agent IDs:
{agent_table}

Return STRICT JSON:
{{
  "micro_tasks": [
    {{
      "step": 1,
      "agent": "<agent_id>",
      "instruction": "<one concrete action>",
      "depends_on_step": null | <int>,
      "cost_estimate_tokens": <int>
    }}
  ]
}}

Rules:
- 3-20 micro-tasks. Fewer is better when possible.
- The LAST step MUST be assigned to "ceo" to synthesize a final answer.
- If the user wrote Hindi/Hinglish, keep instructions clear in English.
- Total cost_estimate_tokens should fit within {budget} tokens if at all possible.
"""


class TaskShredder:
    def __init__(self, llm: LLMRouter) -> None:
        self.llm = llm
        self.registry = settings.agent_registry()

    def _agent_table(self) -> str:
        rows = []
        for agent_id, cfg in self.registry["agents"].items():
            rows.append(f"  - {agent_id}: {cfg.get('role', '')[:80]}")
        return "\n".join(rows)

    async def shred(self, goal: str, budget_tokens: int = 200_000) -> list[dict]:
        sys = _SHREDDER_SYSTEM.format(
            agent_table=self._agent_table(),
            budget=budget_tokens,
        )
        try:
            raw = await self.llm.chat(
                messages=[{"role": "system", "content": sys}, {"role": "user", "content": goal}],
                tier="reasoning",
                json_mode=True,
            )
        except Exception:
            raw = await self.llm.chat(
                messages=[{"role": "system", "content": sys}, {"role": "user", "content": goal}],
                tier="strong",
            )
        data = _coerce_json(raw)
        tasks = data.get("micro_tasks", [])
        if not tasks:
            # fall back: one-shot
            return [{"step": 1, "agent": "ceo", "instruction": goal,
                     "depends_on_step": None, "cost_estimate_tokens": 4000}]
        # ensure last task is CEO
        if tasks[-1].get("agent") != "ceo":
            tasks.append({
                "step": tasks[-1]["step"] + 1,
                "agent": "ceo",
                "instruction": "Synthesise the final answer combining prior steps.",
                "depends_on_step": tasks[-1]["step"],
                "cost_estimate_tokens": 5000,
            })
        return tasks


def _coerce_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*", "", raw).rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise
