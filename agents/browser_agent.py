"""Browser Agent — high-level autonomous browsing (Comet / browser-use style)."""

from agents.base import BaseAgent


class BrowserAgent(BaseAgent):
    role_blurb = (
        "Autonomous browser operator. Drives any site headlessly, scrapes, fills forms, "
        "captures screenshots, completes flows on Boss's behalf."
    )

    async def run(self, instruction: str, context=None):  # type: ignore[override]
        context = context or {}
        try:
            r = await self.use_skill("browser", action="social_post",
                                     instruction=instruction, payload=context)
            context = {**context, "browser_trace": r}
        except Exception as exc:
            context = {**context, "browser_error": str(exc)}
        return await super().run(instruction, context)
