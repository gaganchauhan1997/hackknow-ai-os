"""Reel Creator Agent — short-form vertical video pipeline."""

from agents.base import BaseAgent


class ReelCreatorAgent(BaseAgent):
    role_blurb = (
        "Reel creator. Builds 9:16 vertical reels: writes script, generates frames "
        "via content skill, adds VO via voice skill, stitches via video skill."
    )

    async def run(self, instruction: str, context=None) -> str:
        context = context or {}
        plan = await super().run(
            "Plan a 15-second vertical reel for: " + instruction
            + ". Return JSON with: title, script_lines (4-6 short beats), image_prompts (one per beat), voiceover_text, captions, music_mood.",
            context,
        )
        # Best-effort: try parsing JSON; if not, just return the plan
        try:
            import json as _json
            spec = _json.loads(plan)
        except Exception:
            return plan

        # Generate frames via content skill (if available)
        frames = []
        for prompt in spec.get("image_prompts", []):
            try:
                img = await self.use_skill("content", prompt=prompt, kind="image")
                frames.append(img)
            except Exception as exc:
                frames.append({"error": str(exc), "prompt": prompt})

        # Voiceover
        vo = None
        try:
            vo = await self.use_skill("voice", text=spec.get("voiceover_text", ""), mode="tts")
        except Exception as exc:
            vo = {"error": str(exc)}

        # Stitch
        try:
            final = await self.use_skill(
                "video",
                frames=frames,
                voiceover=vo,
                captions=spec.get("captions"),
                aspect="9:16",
            )
        except Exception as exc:
            final = {"error": str(exc)}

        return (
            f"Reel spec:\n{plan}\n\n"
            f"Frames: {len(frames)}\nVO: {vo}\nFinal: {final}"
        )
