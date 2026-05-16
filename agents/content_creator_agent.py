"""Content Creator Agent — copy, image prompts, structured content packs."""

from agents.base import BaseAgent


class ContentCreatorAgent(BaseAgent):
    role_blurb = (
        "Content creator. Generates posts, captions, image prompts, descriptions. "
        "Brand voice: Hackknow — bold, ambitious, Indian-market aware."
    )

    async def run(self, instruction: str, context=None) -> str:
        context = context or {}
        instruction = (
            f"{instruction}\n\nBrand voice guidance: Bold, ambitious, India-aware. "
            f"Mix English + Hinglish only when culturally appropriate. Avoid clichés."
        )
        return await super().run(instruction, context)
