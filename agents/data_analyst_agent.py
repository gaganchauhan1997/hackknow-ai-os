"""Data Analyst Agent — pandas-ai backed."""

from agents.base import BaseAgent


class DataAnalystAgent(BaseAgent):
    role_blurb = (
        "Data analyst. Reads CSV / Excel / DataFrame inputs, asks questions in "
        "natural language via the data skill, returns insights + charts."
    )

    async def run(self, instruction: str, context=None) -> str:
        context = context or {}
        if context.get("dataset") or "csv" in instruction.lower():
            try:
                result = await self.use_skill(
                    "data",
                    instruction=instruction,
                    dataset=context.get("dataset"),
                )
                return str(result)
            except Exception as exc:
                return f"[data skill error] {exc}\n\n" + await super().run(instruction, context)
        return await super().run(instruction, context)
