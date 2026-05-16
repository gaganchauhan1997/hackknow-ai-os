"""Social Media Manager Agent — multi-platform posting + scheduling."""

from agents.base import BaseAgent


class SocialMediaAgent(BaseAgent):
    role_blurb = (
        "Social media manager. Schedules and publishes to Instagram, X, LinkedIn, "
        "YouTube Shorts via browser automation + workflow webhooks."
    )

    async def run(self, instruction: str, context=None) -> str:
        context = context or {}
        if "post" in instruction.lower() or "publish" in instruction.lower():
            try:
                result = await self.use_skill(
                    "browser",
                    action="social_post",
                    instruction=instruction,
                    payload=context,
                )
                context = {**context, "post_result": result}
            except Exception as exc:
                context = {**context, "post_error": str(exc)}
        return await super().run(instruction, context)
