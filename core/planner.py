"""
Planner — decomposes a user goal into a DAG of subtasks tied to agents.

The planner is itself an LLM call, prompted to emit JSON. The orchestrator
parses the JSON into Task objects which the workflow engine then executes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from core.llm_router import LLMRouter
from core.logger import get_logger

log = get_logger("planner")


@dataclass
class Task:
    id: str
    agent: str
    instruction: str
    depends_on: list[str] = field(default_factory=list)
    result: Any | None = None
    status: str = "pending"          # pending | running | done | error
    error: str | None = None


_PLANNER_SYSTEM = """You are the Planner inside HackKnow AI OS.

Available specialist agents (ID → role):
{agent_table}

Available skill domains (an agent can chain them):
{skill_list}

Given the user goal, decompose it into the smallest useful set of subtasks.
Return STRICT JSON of the form:

{{
  "plan": [
    {{
      "id": "t1",
      "agent": "<agent_id>",
      "instruction": "<concrete task description>",
      "depends_on": []
    }}
  ]
}}

Rules:
- Use snake_case agent IDs from the table above.
- Keep instructions concrete and singular (no 'and').
- Tasks that can run in parallel should have non-overlapping depends_on.
- 1-8 tasks total — be efficient.
- Always end with a synthesizer task assigned to "ceo" that depends on prior tasks.
"""


class Planner:
    def __init__(self, llm: LLMRouter, agent_registry: dict, skill_names: list[str]) -> None:
        self.llm = llm
        self.agent_registry = agent_registry
        self.skill_names = skill_names

    def _system_prompt(self) -> str:
        rows = []
        for agent_id, cfg in self.agent_registry["agents"].items():
            rows.append(f"  - {agent_id}: {cfg.get('role', '')}")
        return _PLANNER_SYSTEM.format(
            agent_table="\n".join(rows),
            skill_list=", ".join(self.skill_names) or "(none registered)",
        )

    async def plan(self, goal: str, language: str = "en") -> list[Task]:
        sys_prompt = self._system_prompt()
        if language == "hi":
            sys_prompt += "\n\nNote: user wrote in Hindi/Hinglish — keep instructions clear in English (agents work in English internally), but plan with cultural context."
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": goal},
        ]
        try:
            raw = await self.llm.chat(messages=messages, tier="reasoning", json_mode=True)
        except Exception:
            raw = await self.llm.chat(messages=messages, tier="strong")
        data = _coerce_json(raw)
        return _build_tasks(data)


def _coerce_json(raw: str) -> dict:
    raw = raw.strip()
    # strip code fences
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*", "", raw).rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # try extracting the first {...} blob
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _build_tasks(data: dict) -> list[Task]:
    plan = data.get("plan") or data.get("tasks") or []
    out: list[Task] = []
    for entry in plan:
        out.append(
            Task(
                id=str(entry["id"]),
                agent=str(entry["agent"]),
                instruction=str(entry["instruction"]),
                depends_on=[str(d) for d in entry.get("depends_on", [])],
            )
        )
    return out
