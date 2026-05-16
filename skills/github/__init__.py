"""
GitHub skill — clone repos as context, list files, commit + push, open PRs.

Uses git CLI (must be installed) and the GitHub REST API when GITHUB_TOKEN is set.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx

from config.settings import ROOT
from core.logger import get_logger

log = get_logger("skill:github")

manifest = {
    "description": "Interact with GitHub: clone, list, read, commit, push, open PR.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["clone", "list", "read", "commit_push", "open_pr"]},
            "repo": {"type": "string"},
            "branch": {"type": "string"},
            "path": {"type": "string"},
            "message": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "base": {"type": "string"},
        },
        "required": ["action"],
    },
}

REPOS = ROOT / "workspaces" / "_repos"
REPOS.mkdir(parents=True, exist_ok=True)


def _path_for(repo: str) -> Path:
    return REPOS / repo.replace("/", "__")


async def _sh(cmd: list[str], cwd: Path | None = None) -> dict:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return {"exit": proc.returncode,
            "stdout": out.decode(errors="replace"),
            "stderr": err.decode(errors="replace")}


async def run(action: str, **kwargs: Any) -> dict:
    if action == "clone":
        repo = kwargs["repo"]
        branch = kwargs.get("branch", "main")
        target = _path_for(repo)
        if target.exists():
            await _sh(["git", "fetch", "--all"], cwd=target)
            await _sh(["git", "checkout", branch], cwd=target)
            await _sh(["git", "pull"], cwd=target)
            return {"path": str(target), "status": "updated"}
        url = repo if repo.startswith("http") else f"https://github.com/{repo}.git"
        token = os.getenv("GITHUB_TOKEN")
        if token and url.startswith("https://github.com"):
            url = url.replace("https://", f"https://{token}@")
        out = await _sh(["git", "clone", "--depth=1", "-b", branch, url, str(target)])
        return {"path": str(target), **out}

    if action == "list":
        target = _path_for(kwargs["repo"])
        files = []
        for p in target.rglob("*"):
            if ".git" in p.parts:
                continue
            if p.is_file():
                files.append(str(p.relative_to(target)))
        return {"repo": kwargs["repo"], "files": files[:2000]}

    if action == "read":
        target = _path_for(kwargs["repo"]) / kwargs["path"]
        if not target.exists():
            return {"status": "missing"}
        return {"path": str(target), "text": target.read_text(errors="ignore")[:20000]}

    if action == "commit_push":
        target = _path_for(kwargs["repo"])
        branch = kwargs.get("branch", "main")
        msg = kwargs.get("message", "HackKnow AI commit")
        await _sh(["git", "add", "-A"], cwd=target)
        await _sh(["git", "commit", "-m", msg], cwd=target)
        return await _sh(["git", "push", "origin", branch], cwd=target)

    if action == "open_pr":
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return {"status": "skipped", "reason": "GITHUB_TOKEN not set"}
        repo = kwargs["repo"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"https://api.github.com/repos/{repo}/pulls",
                json={
                    "title": kwargs["title"],
                    "head": kwargs["branch"],
                    "base": kwargs.get("base", "main"),
                    "body": kwargs.get("body", ""),
                },
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json"},
            )
            return {"status": r.status_code, "body": r.json()}
    raise ValueError(f"unknown github action: {action}")
