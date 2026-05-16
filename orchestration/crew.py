"""
CrewAI bridge — wraps HackKnow agents as CrewAI agents for collaborative tasks.

Repo: https://github.com/crewAIInc/crewAI

Use this when you want explicit role-play / debate between agents rather than
the deterministic DAG that ``core.workflow`` provides.
"""

from __future__ import annotations

from typing import Any

from core.logger import get_logger

log = get_logger("crew")


def build_crew(hackknow_os: Any, agent_ids: list[str], task: str) -> Any:
    """Return a CrewAI Crew instance composed of the named HackKnow agents."""
    try:
        from crewai import Agent as CrewAgent, Crew, Task as CrewTask  # type: ignore
    except ImportError:
        raise RuntimeError("crewai not installed — pip install crewai")

    agents = []
    for aid in agent_ids:
        ha = hackknow_os.agents[aid]
        agents.append(
            CrewAgent(
                role=aid.replace("_", " ").title(),
                goal=ha.cfg.get("role", ""),
                backstory=f"HackKnow specialist for {aid}.",
                allow_delegation=True,
                verbose=True,
            )
        )
    crew_task = CrewTask(description=task, expected_output="A polished, actionable result.", agent=agents[0])
    return Crew(agents=agents, tasks=[crew_task], verbose=True)
