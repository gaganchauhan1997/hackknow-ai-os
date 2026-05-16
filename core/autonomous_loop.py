"""
Autonomous Loop — Manus / Devin / OpenDevin style.

Given a high-level goal, the loop:
  1. PERCEIVES current state (memory + last observation).
  2. THINKS — calls the LLM to choose the next action.
  3. ACTS — invokes an agent or a skill directly.
  4. OBSERVES the result, appends it to scratchpad.
  5. Repeats until the LLM emits a STOP action or hits the step limit.

The whole loop streams events out so the UI can render a live trace.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator

from core.llm_router import LLMRouter
from core.logger import get_logger
from core.skill_registry import SkillRegistry

log = get_logger("loop")


_SYSTEM = """You are the Autonomous Loop inside HackKnow AI OS.

You operate as a strict ReAct agent: every turn you emit ONE JSON object, then stop.

Schema:
{
  "thought": "<one short reasoning sentence>",
  "action": {
    "kind": "agent" | "skill" | "stop",
    "name": "<agent_id or skill_name, omit if kind=stop>",
    "args": { ... }                   // arguments for the agent/skill
  },
  "speak": "<optional short message to surface to Boss this step>"
}

Available agents:
{agents}

Available skills:
{skills}

Rules:
- Output STRICT JSON, no prose, no code fences.
- Use kind="stop" when the goal is achieved.
- Keep "thought" under 200 chars.
- For agents pass args={"task": "..."}.
- For skills pass the arguments their manifest requires.
"""


@dataclass
class LoopStep:
    n: int
    thought: str = ""
    action: dict = field(default_factory=dict)
    observation: str = ""
    speak: str = ""
    started_at: float = field(default_factory=time.time)
    duration: float = 0.0


@dataclass
class LoopResult:
    goal: str
    steps: list[LoopStep]
    final: str
    status: str = "done"     # done | hit_step_limit | error


class AutonomousLoop:
    def __init__(self, hackknow_os) -> None:
        self.os = hackknow_os
        self.llm: LLMRouter = hackknow_os.llm
        self.skills: SkillRegistry = hackknow_os.skills

    # ------------------------------------------------------------ public sync
    async def run(self, goal: str, max_steps: int = 12) -> LoopResult:
        steps: list[LoopStep] = []
        scratchpad = ""
        for n in range(1, max_steps + 1):
            step = LoopStep(n=n)
            decision = await self._think(goal, scratchpad)
            step.thought = decision.get("thought", "")
            step.action = decision.get("action", {})
            step.speak = decision.get("speak", "")

            kind = step.action.get("kind")
            if kind == "stop":
                step.observation = "loop complete"
                step.duration = time.time() - step.started_at
                steps.append(step)
                return LoopResult(goal=goal, steps=steps,
                                  final=step.speak or scratchpad.strip()[-2000:])

            try:
                step.observation = await self._act(step.action)
            except Exception as exc:  # noqa: BLE001
                step.observation = f"[error] {exc}"
            step.duration = time.time() - step.started_at
            steps.append(step)
            scratchpad += (
                f"\n\n=== step {n} ===\nthought: {step.thought}\n"
                f"action: {json.dumps(step.action)[:600]}\n"
                f"observation: {step.observation[:1500]}\n"
            )

        return LoopResult(goal=goal, steps=steps,
                          final="step limit reached", status="hit_step_limit")

    # ------------------------------------------------------------ public async stream
    async def stream(self, goal: str, max_steps: int = 12) -> AsyncGenerator[dict, None]:
        scratchpad = ""
        yield {"type": "goal", "goal": goal}
        for n in range(1, max_steps + 1):
            decision = await self._think(goal, scratchpad)
            thought = decision.get("thought", "")
            action = decision.get("action", {})
            speak = decision.get("speak", "")
            yield {"type": "think", "n": n, "thought": thought, "action": action, "speak": speak}
            if action.get("kind") == "stop":
                yield {"type": "stop", "final": speak or "done"}
                return
            try:
                obs = await self._act(action)
            except Exception as exc:  # noqa: BLE001
                obs = f"[error] {exc}"
            yield {"type": "observe", "n": n, "observation": obs[:6000]}
            scratchpad += (
                f"\n\n=== step {n} ===\nthought: {thought}\n"
                f"action: {json.dumps(action)[:600]}\nobservation: {obs[:1500]}\n"
            )
        yield {"type": "stop", "final": "step limit reached"}

    # ------------------------------------------------------------ internals
    async def _think(self, goal: str, scratchpad: str) -> dict:
        agents = "\n".join(f"  - {a}: {self.os.agents[a].cfg.get('role', '')[:80]}"
                           for a in self.os.agents)
        skills = "\n".join(f"  - {s}: {self.skills.get(s).manifest.get('description', '')[:80]}"
                           for s in self.skills.names())
        sys = _SYSTEM.replace("{agents}", agents).replace("{skills}", skills)
        user = f"Goal: {goal}\n\nScratchpad so far:\n{scratchpad or '(empty)'}"
        raw = await self.llm.chat(
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            tier="reasoning", json_mode=True, max_tokens=900,
        )
        return _coerce(raw)

    async def _act(self, action: dict) -> str:
        kind = action.get("kind")
        name = action.get("name", "")
        args = action.get("args") or {}
        if kind == "agent":
            return await self.os.delegate(name, args)
        if kind == "skill":
            return str(await self.skills.run(name, **args))[:8000]
        return f"[unknown action kind: {kind}]"


def _coerce(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*", "", raw).rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"thought": "(invalid JSON)", "action": {"kind": "stop"}, "speak": raw[:600]}
