"""
AutoGen bridge — group-chat patterns for multi-agent debate.

Repo: https://github.com/microsoft/autogen
"""

from __future__ import annotations

from typing import Any

from core.logger import get_logger

log = get_logger("autogen")


def build_group_chat(hackknow_os: Any, agent_ids: list[str]) -> Any:
    """Return an AutoGen GroupChatManager seeded with the named HackKnow agents."""
    try:
        from autogen import AssistantAgent, GroupChat, GroupChatManager  # type: ignore
    except ImportError:
        raise RuntimeError("pyautogen not installed — pip install pyautogen")

    members = []
    for aid in agent_ids:
        ha = hackknow_os.agents[aid]
        members.append(
            AssistantAgent(
                name=aid,
                system_message=ha.cfg.get("role", ""),
                llm_config={"model": "gpt-3.5-turbo"},  # autogen requires a stub; HackKnow handles real routing
            )
        )
    gc = GroupChat(agents=members, messages=[], max_round=6)
    return GroupChatManager(groupchat=gc, llm_config={"model": "gpt-3.5-turbo"})
