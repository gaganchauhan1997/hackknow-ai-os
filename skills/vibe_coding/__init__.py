"""
Vibe coding skill — Boss describes the app, this scaffolds a runnable project
under workspaces/<slug>/ and optionally runs `python` / `node` / `pip install`.

Devin / OpenDevin style. The agent does the talking; this skill provides
the file system + execution surface.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from config.settings import ROOT
from core.logger import get_logger

log = get_logger("skill:vibe_coding")

manifest = {
    "description": "Author multi-file projects in workspaces/<slug>/. action='write' to put files; 'run' to execute a shell command in the workspace; 'list' to inspect.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["write", "run", "list", "delete"]},
            "slug": {"type": "string"},
            "files": {"type": "object"},
            "command": {"type": "string"},
            "timeout": {"type": "integer"},
        },
        "required": ["action", "slug"],
    },
}

WORKSPACES = ROOT / "workspaces"
WORKSPACES.mkdir(parents=True, exist_ok=True)


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", s).strip("_")
    return s.lower()[:48] or "project"


async def run(action: str, slug: str, **kwargs: Any) -> dict:
    slug = _slug(slug)
    base = WORKSPACES / slug
    base.mkdir(parents=True, exist_ok=True)

    if action == "write":
        files: dict = kwargs.get("files") or {}
        written = []
        for rel, content in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            written.append(rel)
        return {"slug": slug, "wrote": written, "root": str(base)}

    if action == "list":
        files = [str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()]
        return {"slug": slug, "files": files}

    if action == "delete":
        target = base / kwargs.get("path", "")
        if target.is_file():
            target.unlink()
            return {"deleted": str(target.relative_to(base))}
        return {"status": "noop"}

    if action == "run":
        cmd = kwargs["command"]
        timeout = int(kwargs.get("timeout", 60))
        proc = await asyncio.create_subprocess_shell(
            cmd, cwd=str(base),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"status": "timeout", "command": cmd}
        return {
            "exit_code": proc.returncode,
            "stdout": out.decode(errors="replace")[:8000],
            "stderr": err.decode(errors="replace")[:4000],
        }
    raise ValueError(f"unknown vibe_coding action: {action}")
