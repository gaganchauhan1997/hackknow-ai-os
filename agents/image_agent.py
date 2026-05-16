"""Image Agent — text-to-image + edit via ComfyUI/AnimateDiff."""

from agents.base import BaseAgent


class ImageAgent(BaseAgent):
    role_blurb = (
        "Image generator. Produces prompts, then renders frames through ComfyUI. "
        "Handles edits, in-paints, style transfers."
    )

    async def run(self, instruction: str, context=None):  # type: ignore[override]
        context = context or {}
        prompt = instruction
        try:
            r = await self.use_skill("content", prompt=prompt, kind="image")
            context = {**context, "image_result": r}
        except Exception as exc:
            context = {**context, "image_error": str(exc)}
        return await super().run(instruction, context)
