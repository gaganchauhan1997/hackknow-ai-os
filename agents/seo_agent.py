"""SEO Agent — keyword research, audits, SERP analysis."""

from agents.base import BaseAgent


class SEOAgent(BaseAgent):
    role_blurb = (
        "SEO specialist. Performs keyword research, on-page audits, SERP analysis, "
        "competitor backlink prospecting, and produces actionable recommendations."
    )

    async def run(self, instruction: str, context=None) -> str:
        context = context or {}
        # If the user asks for SERP data, run a research pass first
        if "keyword" in instruction.lower() or "rank" in instruction.lower():
            try:
                research = await self.use_skill(
                    "research", query=instruction, top_k=10
                )
                context = {**context, "serp_context": research}
            except Exception:
                pass
        return await super().run(instruction, context)
