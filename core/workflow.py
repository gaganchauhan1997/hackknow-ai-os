"""
Workflow engine — async DAG executor for Planner output.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.logger import get_logger
from core.planner import Task

log = get_logger("workflow")

AgentRunner = Callable[[str, str, dict], Awaitable[str]]
# (agent_id, instruction, context) -> result_text


@dataclass
class WorkflowResult:
    tasks: list[Task]
    final: str

    @property
    def succeeded(self) -> bool:
        return all(t.status == "done" for t in self.tasks)


class WorkflowEngine:
    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    async def execute(self, tasks: list[Task]) -> WorkflowResult:
        by_id = {t.id: t for t in tasks}
        pending = set(by_id)
        results: dict[str, str] = {}
        running: dict[str, asyncio.Task] = {}

        while pending or running:
            # launch all newly-ready tasks
            for tid in list(pending):
                task = by_id[tid]
                if all(dep in results for dep in task.depends_on):
                    context = {dep: results[dep] for dep in task.depends_on}
                    task.status = "running"
                    log.info(f"▶ {task.id} ({task.agent}): {task.instruction[:80]}")
                    running[tid] = asyncio.create_task(
                        self.runner(task.agent, task.instruction, context)
                    )
                    pending.discard(tid)

            if not running:
                # no task ready — cycle?
                if pending:
                    raise RuntimeError("Workflow stuck — unresolved dependencies.")
                break

            done, _ = await asyncio.wait(
                running.values(), return_when=asyncio.FIRST_COMPLETED
            )
            for d in done:
                tid = next(k for k, v in running.items() if v is d)
                task = by_id[tid]
                try:
                    res = d.result()
                    task.result = res
                    task.status = "done"
                    results[tid] = res
                    log.success(f"✓ {tid} done")
                except Exception as exc:  # noqa: BLE001
                    task.status = "error"
                    task.error = str(exc)
                    results[tid] = f"[ERROR] {exc}"
                    log.error(f"✗ {tid} failed: {exc}")
                running.pop(tid)

        # final = last task with no descendants, fallback to last in order
        terminal = [t for t in tasks if not any(t.id in o.depends_on for o in tasks)]
        final = terminal[-1].result if terminal and terminal[-1].result else (
            tasks[-1].result if tasks else ""
        )
        return WorkflowResult(tasks=tasks, final=final or "")
