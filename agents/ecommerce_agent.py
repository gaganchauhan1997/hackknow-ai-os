"""Ecommerce Agent — WooCommerce + Medusa operations."""

from agents.base import BaseAgent


class EcommerceAgent(BaseAgent):
    role_blurb = (
        "Ecommerce operator for shop.hackknow.com (WooCommerce) and optional Medusa "
        "backend. Creates / updates products, manages inventory, prices, orders, refunds."
    )

    async def run(self, instruction: str, context=None) -> str:
        context = context or {}
        instr_low = instruction.lower()
        if "product" in instr_low or "inventory" in instr_low or "order" in instr_low:
            try:
                result = await self.use_skill(
                    "ecommerce",
                    instruction=instruction,
                    context=context,
                )
                context = {**context, "ecommerce_skill_result": result}
            except Exception as exc:
                context = {**context, "ecommerce_skill_error": str(exc)}
        return await super().run(instruction, context)
