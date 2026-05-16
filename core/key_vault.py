"""
Key Vault — up to 50 keys per provider, automatic failover, exhaustion tracking,
resume-on-refresh.

Boss can paste any mix of free and paid keys (Groq, Gemini, OpenRouter, Cohere,
Mistral, Together, HuggingFace, custom). The vault picks the freshest key for
every call, retires exhausted keys, and wakes them up when their refresh window
elapses.

Persistence is local JSON at ``.cache/key_vault.json`` so keys survive restarts.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from config.settings import ROOT
from core.logger import get_logger

log = get_logger("key_vault")

MAX_KEYS_PER_PROVIDER = 50

# Sane defaults per provider for the free tier. Tunable in config.
# refresh_seconds = how long until the quota window resets after exhaustion.
# tokens_per_day  = generous estimate of free-tier daily token budget.
# tokens_per_call = average tokens we charge per LLM call (input+output).
PROVIDER_PROFILES: dict[str, dict] = {
    "groq":        {"refresh_seconds":  60,   "rpm": 30,  "tokens_per_day":   500_000, "avg_call_tokens": 4_000},
    "gemini":      {"refresh_seconds":  60,   "rpm": 15,  "tokens_per_day": 1_000_000, "avg_call_tokens": 6_000},
    "cohere":      {"refresh_seconds": 3600,  "rpm": 20,  "tokens_per_day":   200_000, "avg_call_tokens": 3_000},
    "mistral":     {"refresh_seconds":  60,   "rpm": 60,  "tokens_per_day":   500_000, "avg_call_tokens": 4_000},
    "together":    {"refresh_seconds":  60,   "rpm": 60,  "tokens_per_day":   300_000, "avg_call_tokens": 4_000},
    "openrouter":  {"refresh_seconds":  60,   "rpm": 20,  "tokens_per_day":   200_000, "avg_call_tokens": 4_000},
    "huggingface": {"refresh_seconds":  60,   "rpm": 30,  "tokens_per_day":   100_000, "avg_call_tokens": 3_000},
    "ollama_local":{"refresh_seconds":   0,   "rpm": 1000,"tokens_per_day": 9_999_999, "avg_call_tokens": 4_000},
}

KeyStatus = Literal["active", "cooling", "exhausted", "disabled"]


@dataclass
class ApiKey:
    id: str
    provider: str
    secret: str
    label: str = ""
    tier: str = "free"          # 'free' | 'paid'
    added_at: float = field(default_factory=time.time)
    requests_today: int = 0
    tokens_today: int = 0
    last_used_at: float = 0.0
    last_error: str | None = None
    status: KeyStatus = "active"
    cooldown_until: float = 0.0

    # ------------------------------------------------------------------ helpers
    def masked(self) -> str:
        if len(self.secret) <= 8:
            return "***"
        return self.secret[:4] + "…" + self.secret[-4:]

    def public(self) -> dict:
        d = asdict(self)
        d["secret"] = self.masked()
        return d

    def profile(self) -> dict:
        return PROVIDER_PROFILES.get(self.provider, PROVIDER_PROFILES["groq"])

    def daily_budget_tokens(self) -> int:
        base = self.profile()["tokens_per_day"]
        return base * (10 if self.tier == "paid" else 1)

    def remaining_tokens(self) -> int:
        return max(0, self.daily_budget_tokens() - self.tokens_today)

    def remaining_calls(self) -> int:
        avg = max(1, self.profile()["avg_call_tokens"])
        return self.remaining_tokens() // avg

    def is_available(self) -> bool:
        if self.status == "disabled":
            return False
        if self.status == "exhausted" and self.remaining_tokens() <= 0:
            return False
        if self.status == "cooling" and time.time() < self.cooldown_until:
            return False
        if self.status == "cooling" and time.time() >= self.cooldown_until:
            self.status = "active"
            self.last_error = None
        return True


class KeyVault:
    def __init__(self, persist_path: Path | None = None) -> None:
        self._lock = asyncio.Lock()
        self.persist_path = persist_path or (ROOT / ".cache" / "key_vault.json")
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.keys: dict[str, ApiKey] = {}
        self._cursor_by_provider: dict[str, int] = {}
        self._load()

    # ---------------------------------------------------------------- persist
    def _load(self) -> None:
        if not self.persist_path.exists():
            return
        try:
            data = json.loads(self.persist_path.read_text())
            for k in data.get("keys", []):
                key = ApiKey(**k)
                self.keys[key.id] = key
            log.info(f"loaded {len(self.keys)} keys from vault")
        except Exception as exc:  # noqa: BLE001
            log.warning(f"could not read key vault: {exc}")

    def _save(self) -> None:
        data = {"keys": [asdict(k) for k in self.keys.values()]}
        self.persist_path.write_text(json.dumps(data, indent=2))

    # --------------------------------------------------------------- public
    def add(self, provider: str, secret: str, label: str = "", tier: str = "free") -> ApiKey:
        provider_keys = [k for k in self.keys.values() if k.provider == provider]
        if len(provider_keys) >= MAX_KEYS_PER_PROVIDER:
            raise ValueError(
                f"{provider} already has {MAX_KEYS_PER_PROVIDER} keys (max)."
            )
        existing = next((k for k in provider_keys if k.secret == secret), None)
        if existing:
            return existing
        key = ApiKey(
            id=uuid.uuid4().hex[:12],
            provider=provider,
            secret=secret,
            label=label or f"{provider}-{len(provider_keys) + 1}",
            tier=tier,
        )
        self.keys[key.id] = key
        self._save()
        log.info(f"added key {key.masked()} for {provider}")
        return key

    def remove(self, key_id: str) -> bool:
        if key_id in self.keys:
            del self.keys[key_id]
            self._save()
            return True
        return False

    def disable(self, key_id: str) -> None:
        if key_id in self.keys:
            self.keys[key_id].status = "disabled"
            self._save()

    def enable(self, key_id: str) -> None:
        if key_id in self.keys:
            self.keys[key_id].status = "active"
            self._save()

    def list_public(self) -> list[dict]:
        return [k.public() for k in self.keys.values()]

    def providers(self) -> set[str]:
        return {k.provider for k in self.keys.values()}

    def has_any(self) -> bool:
        return any(k.is_available() for k in self.keys.values())

    # -------------------------------------------------------------- picking
    async def pick(self, provider: str | None = None) -> ApiKey | None:
        """Pick the next available key, optionally pinned to a provider."""
        async with self._lock:
            pool = [
                k for k in self.keys.values()
                if k.is_available() and (provider is None or k.provider == provider)
            ]
            if not pool:
                return None
            # bias toward keys with more remaining budget so workload spreads
            pool.sort(key=lambda k: (-k.remaining_tokens(), k.last_used_at))
            return pool[0]

    async def record_usage(self, key_id: str, tokens: int, ok: bool, error: str | None = None) -> None:
        async with self._lock:
            key = self.keys.get(key_id)
            if not key:
                return
            key.last_used_at = time.time()
            if ok:
                key.tokens_today += tokens
                key.requests_today += 1
                if key.remaining_tokens() <= 0:
                    key.status = "exhausted"
                    key.cooldown_until = time.time() + key.profile()["refresh_seconds"]
            else:
                key.last_error = error
                if error and "rate" in error.lower():
                    key.status = "cooling"
                    key.cooldown_until = time.time() + key.profile()["refresh_seconds"]
                elif error and ("quota" in error.lower() or "exhaust" in error.lower()):
                    key.status = "exhausted"
                    key.cooldown_until = time.time() + key.profile()["refresh_seconds"]
            self._save()

    async def wake_refreshed(self) -> int:
        """Promote cooling/exhausted keys back to active when their window resets."""
        woke = 0
        async with self._lock:
            now = time.time()
            for key in self.keys.values():
                if key.status in ("cooling", "exhausted") and now >= key.cooldown_until:
                    key.status = "active"
                    key.tokens_today = 0
                    key.requests_today = 0
                    key.last_error = None
                    woke += 1
            if woke:
                self._save()
        return woke

    async def next_refresh_in(self) -> float:
        """Seconds until *any* key refreshes (0 if any active now)."""
        async with self._lock:
            if any(k.is_available() for k in self.keys.values()):
                return 0.0
            soonest = min(
                (k.cooldown_until for k in self.keys.values() if k.status != "disabled"),
                default=time.time() + 3600,
            )
            return max(1.0, soonest - time.time())
