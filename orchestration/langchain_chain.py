"""
LangChain bridge — expose a HackKnow skill or agent as a LangChain Tool.

Repo: https://github.com/langchain-ai/langchain
"""

from __future__ import annotations

from typing import Any

from core.logger import get_logger

log = get_logger("lc")


def as_langchain_tool(hackknow_os: Any, agent_id: str):
    """Return a LangChain BaseTool wrapping a HackKnow agent."""
    try:
        from langchain.tools import StructuredTool  # type: ignore
    except ImportError:
        raise RuntimeError("langchain not installed — pip install langchain")

    async def _call(task: str) -> str:
        return await hackknow_os.delegate(agent_id, {"task": task})

    return StructuredTool.from_function(
        coroutine=_call,
        name=f"hackknow_{agent_id}",
        description=hackknow_os.agents[agent_id].cfg.get("role", ""),
    )
