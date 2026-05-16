"""
HackKnowOS — top-level orchestrator.

Routes user goals through:
  * Vault-aware LLM router (50-key rotation + Ollama zero-key fallback)
  * Task Shredder (atomic micro-tasks sized for free-tier calls)
  * Durable Queue (resumes when keys refresh)
  * 17 specialist agents (15 original + Skill Smith + Fine-Tune)
  * Plug-in skill registry (hot-loaded)
"""

from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass

from config import settings
from core.autonomous_loop import AutonomousLoop
from core.budget_meter import BudgetMeter
from core.i18n import address, detect_language, style_prefix
from core.key_vault import KeyVault
from core.llm_router import LLMRouter
from core.logger import get_logger
from core.memory import Memory
from core.planner import Planner, Task
from core.queue import TaskQueue
from core.skill_registry import SkillRegistry
from core.task_shredder import TaskShredder
from core.workflow import WorkflowEngine, WorkflowResult

log = get_logger("orchestrator")


@dataclass
class ExecResult:
    summary: str
    tasks: list[Task]
    language: str
    job_id: str | None = None


class HackKnowOS:
    def __init__(self) -> None:
        self.vault = KeyVault()
        self.llm = LLMRouter(vault=self.vault)
        self.memory = Memory()
        self.skills = SkillRegistry()
        self.meter = BudgetMeter(self.vault)
        self.queue = TaskQueue(self.vault)
        self.shredder = TaskShredder(self.llm)
        self.agents: dict = {}
        self.registry = settings.agent_registry()
        self.planner = Planner(
            llm=self.llm,
            agent_registry=self.registry,
            skill_names=self.skills.names(),
        )
        self.workflow = WorkflowEngine(runner=self._run_agent)
        self.loop = AutonomousLoop(self)
        self._booted = False
        self._runner_task: asyncio.Task | None = None

    # -------------------------------------------------------------- lifecycle
    async def boot(self) -> None:
        if self._booted:
            return
        log.info(f"booting HackKnow AI OS as '{settings.assistant_name}'...")
        for agent_id, cfg in self.registry["agents"].items():
            module_name, class_name = cfg["class"].rsplit(".", 1)
            try:
                mod = importlib.import_module(module_name)
                cls = getattr(mod, class_name)
            except Exception as exc:  # noqa: BLE001
                log.warning(f"agent {agent_id} unavailable: {exc}")
                continue
            self.agents[agent_id] = cls(
                agent_id=agent_id, cfg=cfg,
                llm=self.llm, memory=self.memory, skills=self.skills,
            )
            log.info(f"  · agent ready: {agent_id}")
        self._booted = True
        # spin up durable queue runner
        self._runner_task = asyncio.create_task(
            self.queue.runner(self._execute_micro_step)
        )
        log.success(f"online. At your service, {address()}.")

    async def shutdown(self) -> None:
        if self._runner_task:
            self._runner_task.cancel()
        await self.llm.aclose()

    # -------------------------------------------------------------- modes
    async def execute(self, goal: str, session: str = "default", mode: str = "auto") -> ExecResult:
        """
        mode='auto'   : choose between fast / planner / shredder by size
        mode='fast'   : CEO replies directly (one LLM call)
        mode='plan'   : Planner emits DAG (synchronous)
        mode='shred'  : TaskShredder splits + Queue runs (async, resumable)
        """
        await self.boot()
        lang = detect_language(goal)
        self.memory.push(f"session:{session}", "user", goal)
        if mode == "auto":
            mode = "shred" if len(goal) > 280 else "plan"

        if mode == "fast":
            answer = await self.agents["ceo"].run(goal, context={})
            self.memory.push(f"session:{session}", "assistant", answer)
            return ExecResult(summary=answer, tasks=[], language=lang)

        if mode == "shred":
            micro = await self.shredder.shred(goal)
            job = await self.queue.enqueue(goal=goal, micro_tasks=micro)
            return ExecResult(
                summary=f"Queued {len(micro)} micro-tasks (job {job.id}). The shredder will run them across your key vault — paused work resumes when a key refreshes.",
                tasks=[],
                language=lang,
                job_id=job.id,
            )

        # default: plan + workflow (synchronous)
        tasks = await self.planner.plan(goal, language=lang)
        if not tasks:
            answer = await self.agents["ceo"].run(goal, context={})
            return ExecResult(summary=answer, tasks=[], language=lang)
        result: WorkflowResult = await self.workflow.execute(tasks)
        summary = await self._synthesize(goal, result, lang)
        self.memory.push(f"session:{session}", "assistant", summary)
        return ExecResult(summary=summary, tasks=result.tasks, language=lang)

    async def delegate(self, agent_id: str, payload: dict) -> str:
        await self.boot()
        agent = self.agents.get(agent_id)
        if not agent:
            raise KeyError(f"unknown agent: {agent_id}")
        return await agent.run(payload.get("task") or str(payload), context=payload)

    # -------------------------------------------------------------- queue executor
    async def _execute_micro_step(self, step: dict) -> str:
        agent_id = step.get("agent", "ceo")
        instruction = step.get("instruction", "")
        return await self._run_agent(agent_id, instruction, {})

    async def _run_agent(self, agent_id: str, instruction: str, context: dict) -> str:
        agent = self.agents.get(agent_id)
        if not agent:
            return f"[ERROR] unknown agent: {agent_id}"
        return await agent.run(instruction, context=context)

    async def _synthesize(self, goal: str, result: WorkflowResult, lang: str) -> str:
        prefix = style_prefix(lang)
        sub_results = "\n\n".join(
            f"## {t.id} ({t.agent})\n{t.result or t.error or ''}"
            for t in result.tasks
        )
        sys = (
            f"{prefix}\n\nYou are synthesizing a final answer for {address()}. "
            f"Be concise and mission-focused. "
            f"Reply in {'Hindi (Devanagari is fine)' if lang == 'hi' else 'English'}."
        )
        user = f"Original goal:\n{goal}\n\nSub-results:\n{sub_results}\n\nProduce the final answer."
        return await self.llm.chat(
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            tier="strong",
        )
