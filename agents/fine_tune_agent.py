"""
Fine-Tune Agent — orchestrates dataset prep + LoRA/QLoRA/PEFT training and
custom Ollama Modelfiles.
"""

from agents.base import BaseAgent


class FineTuneAgent(BaseAgent):
    role_blurb = (
        "Fine-tuning specialist. Prepares datasets, kicks off LoRA/QLoRA via "
        "PEFT or Unsloth, and writes Ollama Modelfiles for custom local models."
    )

    async def run(self, instruction: str, context=None):  # type: ignore[override]
        context = context or {}
        try:
            r = await self.use_skill(
                "finetune",
                instruction=instruction,
                payload=context,
            )
            context = {**context, "finetune_skill": r}
        except Exception as exc:
            context = {**context, "finetune_error": str(exc)}
        return await super().run(instruction, context)
