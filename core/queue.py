"""
Durable task queue. Survives restarts. Pauses when all keys exhausted,
resumes when the vault wakes a key.

Used by the orchestrator + shredder to run long autonomous workflows
without losing progress.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from config.settings import ROOT
from core.key_vault import KeyVault
from core.logger import get_logger

log = get_logger("queue")

JobStatus = Literal["queued", "running", "done", "failed", "paused"]


@dataclass
class QueueJob:
    id: str
    goal: str
    agent_id: str | None = None
    micro_tasks: list[dict] = field(default_factory=list)
    cursor: int = 0
    status: JobStatus = "queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: str | None = None
    error: str | None = None


class TaskQueue:
    def __init__(self, vault: KeyVault, persist_path: Path | None = None) -> None:
        self.vault = vault
        self.persist_path = persist_path or (ROOT / ".cache" / "queue.json")
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, QueueJob] = {}
        self._lock = asyncio.Lock()
        self._wake_event = asyncio.Event()
        self._wake_event.set()
        self._load()

    def _load(self) -> None:
        if not self.persist_path.exists():
            return
        try:
            data = json.loads(self.persist_path.read_text())
            for jd in data.get("jobs", []):
                j = QueueJob(**jd)
                # mark stale running jobs as paused so they resume next boot
                if j.status == "running":
                    j.status = "paused"
                self.jobs[j.id] = j
        except Exception as exc:  # noqa: BLE001
            log.warning(f"queue load failed: {exc}")

    def _save(self) -> None:
        data = {"jobs": [asdict(j) for j in self.jobs.values()]}
        self.persist_path.write_text(json.dumps(data, indent=2))

    # --------------------------------------------------------- public API
    async def enqueue(self, goal: str, micro_tasks: list[dict], agent_id: str | None = None) -> QueueJob:
        async with self._lock:
            j = QueueJob(id=uuid.uuid4().hex[:12], goal=goal, agent_id=agent_id, micro_tasks=micro_tasks)
            self.jobs[j.id] = j
            self._save()
        self._wake_event.set()
        return j

    async def list_jobs(self) -> list[dict]:
        return [asdict(j) for j in self.jobs.values()]

    async def get(self, job_id: str) -> QueueJob | None:
        return self.jobs.get(job_id)

    async def update(self, job: QueueJob) -> None:
        async with self._lock:
            job.updated_at = time.time()
            self.jobs[job.id] = job
            self._save()

    # ---------------------------------------------------- runner loop
    async def runner(self, executor) -> None:
        """
        Background task. Picks up queued/paused jobs and runs their micro_tasks
        sequentially. Pauses the job if the vault has zero available keys; wakes
        when a key refreshes.
        """
        log.info("queue runner started")
        while True:
            await self._wake_event.wait()
            self._wake_event.clear()
            # snapshot
            pending = [j for j in self.jobs.values() if j.status in ("queued", "paused")]
            if not pending:
                await asyncio.sleep(2.0)
                self._wake_event.set()
                continue
            for job in pending:
                # if no keys + not local-only, pause + schedule wake
                if not self.vault.has_any():
                    job.status = "paused"
                    await self.update(job)
                    wait = await self.vault.next_refresh_in()
                    log.warning(f"all keys exhausted — pausing {job.id}, retry in {wait:.0f}s")
                    asyncio.create_task(self._wake_after(wait))
                    break

                job.status = "running"
                await self.update(job)
                try:
                    while job.cursor < len(job.micro_tasks):
                        woke = await self.vault.wake_refreshed()
                        if woke:
                            log.info(f"woke {woke} keys")
                        step = job.micro_tasks[job.cursor]
                        result = await executor(step)
                        step["result"] = str(result)[:8000]
                        job.cursor += 1
                        await self.update(job)
                    job.result = "\n\n".join(
                        f"## {i+1}. {s.get('agent', '?')}\n{s.get('result','')}"
                        for i, s in enumerate(job.micro_tasks)
                    )
                    job.status = "done"
                    await self.update(job)
                except Exception as exc:  # noqa: BLE001
                    job.error = str(exc)
                    job.status = "failed"
                    await self.update(job)
                    log.error(f"job {job.id} failed: {exc}")

    async def _wake_after(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
        self._wake_event.set()
