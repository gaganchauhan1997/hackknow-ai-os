"""Automation Agent — generic glue: webhooks, schedules, file ops, workflows."""

from agents.base import BaseAgent


class AutomationAgent(BaseAgent):
    role_blurb = (
        "Automation generalist. Bridges other agents and external services via "
        "webhooks, schedules, and the workflow skill (Flowise / native DAG)."
    )
