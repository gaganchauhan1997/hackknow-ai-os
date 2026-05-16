"""Planner Agent — reasoning specialist used by the workflow engine."""

from agents.base import BaseAgent


class PlannerAgent(BaseAgent):
    role_blurb = (
        "You decompose ambitious requests into the smallest possible DAG of "
        "subtasks and assign each to the right agent."
    )
