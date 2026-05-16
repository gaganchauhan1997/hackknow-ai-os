"""
Budget meter — tells the user, in real time, "with this key set, here's
what you can do today and how long it'll last".
"""

from __future__ import annotations

from dataclasses import dataclass

from core.key_vault import KeyVault


@dataclass
class CapabilityEstimate:
    name: str
    cost_per_unit: int    # tokens per unit
    description: str

    def units_possible(self, available_tokens: int) -> int:
        return max(0, available_tokens // max(1, self.cost_per_unit))


# Average "what one unit of work costs" in LLM tokens. Tuned for free tiers.
CAPABILITIES: list[CapabilityEstimate] = [
    CapabilityEstimate("simple_chat_turns",     2_000, "Short Hindi/English chat reply"),
    CapabilityEstimate("blog_articles_1k_words",12_000, "1000-word article with structure"),
    CapabilityEstimate("seo_audits",            18_000, "Full SEO audit with recommendations"),
    CapabilityEstimate("marketing_campaigns",   45_000, "End-to-end 7-day campaign plan"),
    CapabilityEstimate("reel_scripts",           8_000, "15-second reel script + shotlist"),
    CapabilityEstimate("code_features",         28_000, "Mid-size feature with tests"),
    CapabilityEstimate("research_briefs",       16_000, "Cited research brief"),
    CapabilityEstimate("data_analyses",         14_000, "Pandas-AI analysis pass"),
    CapabilityEstimate("woocommerce_ops",        4_000, "WooCommerce CRUD operation"),
    CapabilityEstimate("agent_creations",       30_000, "Author a new specialist agent"),
    CapabilityEstimate("skill_authorings",      35_000, "Author a new skill module"),
]


class BudgetMeter:
    def __init__(self, vault: KeyVault) -> None:
        self.vault = vault

    # ------------------------------------------------------------------ totals
    def total_remaining_tokens(self) -> int:
        return sum(k.remaining_tokens() for k in self.vault.keys.values() if k.is_available())

    def daily_capacity_tokens(self) -> int:
        return sum(k.daily_budget_tokens() for k in self.vault.keys.values() if k.status != "disabled")

    def active_keys(self) -> int:
        return sum(1 for k in self.vault.keys.values() if k.is_available())

    def cooling_keys(self) -> int:
        return sum(1 for k in self.vault.keys.values() if k.status in ("cooling", "exhausted"))

    # ------------------------------------------------------------------ what can we do?
    def capability_map(self) -> dict:
        remaining = self.total_remaining_tokens()
        return {
            c.name: {
                "possible": c.units_possible(remaining),
                "cost_per_unit": c.cost_per_unit,
                "description": c.description,
            }
            for c in CAPABILITIES
        }

    # ------------------------------------------------------------------ duration estimate
    def estimated_duration_hours(self, daily_workload_tokens: int = 200_000) -> float:
        """If user runs ~daily_workload_tokens per day, how many hours of work can current set support?"""
        per_hour = daily_workload_tokens / 24
        remaining = self.total_remaining_tokens()
        return round(remaining / per_hour, 2) if per_hour else 0.0

    def snapshot(self) -> dict:
        """One-shot dashboard payload — the JSON shown on the meter UI."""
        total = self.total_remaining_tokens()
        daily = self.daily_capacity_tokens()
        active = self.active_keys()
        cooling = self.cooling_keys()
        return {
            "active_keys": active,
            "cooling_keys": cooling,
            "total_keys": len(self.vault.keys),
            "tokens_remaining_today": total,
            "tokens_daily_capacity": daily,
            "percent_remaining": round(100 * total / daily, 1) if daily else 100.0,
            "providers_in_use": sorted(self.vault.providers()),
            "estimated_hours_at_normal_load": self.estimated_duration_hours(),
            "capabilities": self.capability_map(),
            "zero_key_mode": len(self.vault.keys) == 0,
        }
