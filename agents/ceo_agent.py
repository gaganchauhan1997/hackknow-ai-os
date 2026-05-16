"""CEO Agent — top-level JARVIS persona, routes + synthesizes."""

from agents.base import BaseAgent


class CEOAgent(BaseAgent):
    role_blurb = (
        "You are the CEO. You greet the user as Boss, coordinate the team, "
        "and produce the final answer combining all sub-agent outputs."
    )
