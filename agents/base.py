"""
BaseAgent — shared behaviour for all 15 specialist agents.

Each agent receives the same dependencies (LLM, memory, skill registry) and
exposes one async method: ``run(instruction, context)``.
"""

from __future__ import annotations

from typing import Any

from core.i18n import address, detect_language, style_prefix
from core.llm_router import LLMRouter
from core.logger import get_logger
from core.memory import Memory
from core.skill_registry import SkillRegistry


class BaseAgent:
    role_blurb: str = ""

    def __init__(
        self,
        *,
        agent_id: str,
        cfg: dict,
        llm: LLMRouter,
        memory: Memory,
        skills: SkillRegistry,
    ) -> None:
        self.id = agent_id
        self.cfg = cfg
        self.llm = llm
        self.memory = memory
        self.skills = skills
        self.log = get_logger(f"agent:{agent_id}")
        self.allowed_skills: list[str] = self._resolve_skills(cfg.get("skills", []))
        self.tier: str = cfg.get("llm_tier", "strong")

    # ---------------------------------------------------------- resolution
    def _resolve_skills(self, declared) -> list[str]:
        if declared == ["all"] or declared == "all":
            return self.skills.names()
        return [s for s in declared if s in self.skills.names()]

    # ---------------------------------------------------------- behaviour
    async def run(self, instruction: str, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        lang = detect_language(instruction)
        system = self._system_prompt(lang)
        history_scope = f"agent:{self.id}"

        prior = self.memory.history(history_scope)[-6:]
        ctx_block = self._format_context(context)

        messages = [{"role": "system", "content": system}, *prior]
        if ctx_block:
            messages.append({"role": "system", "content": ctx_block})
        messages.append({"role": "user", "content": instruction})

        self.log.debug(f"running ({lang}): {instruction[:80]}")
        reply = await self.llm.chat(messages=messages, tier=self.tier)
        self.memory.push(history_scope, "user", instruction)
        self.memory.push(history_scope, "assistant", reply)
        return reply

    # ---------------------------------------------------------- helpers
    def _system_prompt(self, lang: str) -> str:
        prefix = style_prefix(lang)
        role = self.cfg.get("role", self.role_blurb)
        skills_str = ", ".join(self.allowed_skills) or "(no skills)"
        boss = address()
        return (
            f"{prefix}\n\n"
            f"You are the {self.id.replace('_', ' ').title()} Agent inside HackKnow AI OS. "
            f"Role: {role}\n"
            f"You serve {boss}. Available skills you may reference: {skills_str}.\n"
            f"Be decisive. Plan briefly, then act. Produce concrete, production-ready outputs."
        )

    @staticmethod
    def _format_context(ctx: dict) -> str:
        if not ctx:
            return ""
        rows = [f"- {k}: {str(v)[:600]}" for k, v in ctx.items()]
        return "Upstream context:\n" + "\n".join(rows)

    # ---------------------------------------------------------- skill helpers
    async def use_skill(self, name: str, **kwargs):
        if name not in self.allowed_skills:
            raise PermissionError(f"agent {self.id} cannot use skill '{name}'")
        return await self.skills.run(name, **kwargs)
