"""Research Agent — autonomous web research with citations."""

from agents.base import BaseAgent


class ResearchAgent(BaseAgent):
    role_blurb = (
        "Research analyst. Conducts deep web research with citations. Reads docs, "
        "discovers API endpoints, builds knowledge briefs."
    )

    async def run(self, instruction: str, context=None) -> str:
        context = context or {}
        try:
            findings = await self.use_skill("research", query=instruction, top_k=8)
            context = {**context, "findings": findings}
        except Exception as exc:
            context = {**context, "research_error": str(exc)}
        return await super().run(
            instruction + "\n\nProduce a structured brief with cited URLs.",
            context,
        )
