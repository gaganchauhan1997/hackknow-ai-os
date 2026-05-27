"""
LLM Router — uses the multi-key Vault, supports zero-key Ollama fallback.

Behaviour:
  * For each call, ask the Vault for a fresh key in the preferred provider.
  * If none available, fall through providers; finally fall back to Ollama.
  * On 429 / quota error, mark key cooling and try the next one.
  * Track tokens spent per key so the BudgetMeter is accurate.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import settings
from core.key_vault import KeyVault
from core.logger import get_logger

log = get_logger("llm_router")

ChatMessage = dict[str, str]


class LLMError(RuntimeError):
    pass


class RateLimitError(LLMError):
    pass


class LLMRouter:
    def __init__(self, vault: KeyVault | None = None) -> None:
        self.vault = vault or KeyVault()
        self._pool = {p["name"]: p for p in settings.llm_pool()}
        # Bootstrap: import keys from env into the vault if vault is empty.
        if not self.vault.keys:
            self._import_env_keys()
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(60.0))

    # ------------------------------------------------------------ env bootstrap
    def _import_env_keys(self) -> None:
        added = 0
        for name, cfg in self._pool.items():
            env_key = cfg.get("env_key")
            if not env_key:
                continue
            secret = os.getenv(env_key)
            if secret:
                self.vault.add(name, secret, label=f"{name} (env)")
                added += 1
        if added:
            log.info(f"imported {added} keys from environment into vault")

    # ----------------------------------------------------------------- public
    async def chat(
        self,
        messages: list[ChatMessage],
        tier: str = "strong",
        temperature: float = 0.5,
        max_tokens: int = 1024,
        json_mode: bool = False,
        preferred_provider: str | None = None,
    ) -> str:
        # Try keyed providers first
        tried: set[str] = set()
        last_error: Exception | None = None

        for _ in range(max(1, len(self.vault.keys) + 1)):
            key = await self.vault.pick(provider=preferred_provider)
            if key is None:
                break
            tried.add(key.id)
            provider_cfg = self._pool.get(key.provider, {})
            model = self._model_for(provider_cfg, tier)
            try:
                t0 = time.time()
                text = await self._call_provider(
                    key.provider, key.secret, provider_cfg, model,
                    messages, temperature, max_tokens, json_mode,
                )
                # rough cost estimate
                approx_tokens = sum(len(m.get("content", "")) for m in messages) // 4 + max_tokens
                await self.vault.record_usage(key.id, approx_tokens, ok=True)
                log.debug(f"{key.provider}/{key.masked()} ✓ ({time.time()-t0:.2f}s)")
                return text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                err = str(exc)
                await self.vault.record_usage(key.id, 0, ok=False, error=err)
                log.warning(f"{key.provider}/{key.masked()} ✗ {err[:120]}")
                continue

        # Zero-key / total exhaustion fallback → Ollama local
        try:
            return await self._ollama_call(messages, temperature, max_tokens)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(
                f"All providers failed (last: {last_error}). Ollama fallback also failed: {exc}"
            )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---------------------------------------------------------------- helpers
    def _model_for(self, cfg: dict, tier: str) -> str:
        models = cfg.get("models", {})
        if tier in models:
            return models[tier]
        return cfg.get("default_model", "gpt-3.5-turbo")

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential(min=1, max=8),
        stop=stop_after_attempt(2),
    )
    async def _call_provider(
        self, provider: str, secret: str, cfg: dict, model: str,
        messages: list[ChatMessage], temperature: float, max_tokens: int, json_mode: bool,
    ) -> str:
        if provider in ("groq", "mistral", "together", "openrouter", "deepseek", "perplexity"):
            return await self._openai_compat(
                base_url=cfg["base_url"], api_key=secret, model=model,
                messages=messages, temperature=temperature, max_tokens=max_tokens,
                json_mode=json_mode, provider=provider,
            )
        if provider == "openai":
            return await self._openai_compat(
                base_url=cfg.get("base_url", "https://api.openai.com/v1"),
                api_key=secret, model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens, json_mode=json_mode,
                provider="openai",
            )
        if provider == "anthropic":
            return await self._anthropic(secret, model, messages, temperature, max_tokens)
        if provider == "gemini":
            return await self._gemini(secret, model, messages, temperature, max_tokens)
        if provider == "cohere":
            return await self._cohere(secret, model, messages, temperature, max_tokens)
        if provider == "huggingface":
            return await self._huggingface(secret, model, messages, temperature, max_tokens)
        if provider == "ollama_local":
            return await self._ollama_call(messages, temperature, max_tokens)
        raise LLMError(f"unknown provider: {provider}")

    # ------------- OpenAI compatible (Groq, Mistral, Together, OpenRouter, DeepSeek, Perplexity, OpenAI)
    async def _openai_compat(self, *, base_url, api_key, model, messages, temperature,
                              max_tokens, json_mode, provider):
        headers = {"Authorization": f"Bearer {api_key}"}
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://hackknow.com"
            headers["X-Title"] = "HackKnow AI OS"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        r = await self._http.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        if r.status_code == 429:
            raise RateLimitError(f"{provider} rate limited")
        if r.status_code in (401, 403):
            raise LLMError(f"{provider} auth failed: {r.text[:200]}")
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

    # ------------- Anthropic
    async def _anthropic(self, api_key, model, messages, temperature, max_tokens):
        # Convert to Anthropic format
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        conv = [m for m in messages if m["role"] != "system"]
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m["role"], "content": m["content"]} for m in conv],
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        r = await self._http.post("https://api.anthropic.com/v1/messages",
                                  json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        return "".join(b.get("text", "") for b in data.get("content", []))

    # ------------- Gemini
    async def _gemini(self, api_key, model, messages, temperature, max_tokens):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        contents = []
        for m in messages:
            role = "user" if m["role"] in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        r = await self._http.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"unexpected Gemini response: {data}") from exc

    # ------------- Cohere
    async def _cohere(self, api_key, model, messages, temperature, max_tokens):
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        history = [
            {"role": "USER" if m["role"] == "user" else "CHATBOT", "message": m["content"]}
            for m in messages[:-1] if m["role"] in ("user", "assistant")
        ]
        payload = {"message": user_msg, "model": model, "chat_history": history,
                   "temperature": temperature, "max_tokens": max_tokens}
        r = await self._http.post("https://api.cohere.com/v1/chat", json=payload,
                                  headers={"Authorization": f"Bearer {api_key}"})
        r.raise_for_status()
        return r.json().get("text", "")

    # ------------- HuggingFace
    async def _huggingface(self, api_key, model, messages, temperature, max_tokens):
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages) + "\nassistant:"
        payload = {"inputs": prompt, "parameters": {
            "temperature": temperature, "max_new_tokens": max_tokens, "return_full_text": False
        }}
        r = await self._http.post(
            f"https://api-inference.huggingface.co/models/{model}",
            json=payload, headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return data[0].get("generated_text", "")
        return str(data)

    # ------------- Ollama (always available local fallback — zero-key mode)
    async def _ollama_call(self, messages, temperature, max_tokens):
        base = (settings.ollama_base_url or "").strip()
        model = settings.ollama_model
        if not base or not base.startswith(("http://", "https://")):
            raise LLMError("Ollama disabled (OLLAMA_BASE_URL not set)")
        payload = {"model": model, "messages": messages, "stream": False,
                   "options": {"temperature": temperature, "num_predict": max_tokens}}
        try:
            r = await self._http.post(f"{base}/api/chat", json=payload, timeout=120.0)
            if r.status_code == 404:
                # try to pull the model on demand
                await self._http.post(f"{base}/api/pull", json={"name": model}, timeout=600.0)
                r = await self._http.post(f"{base}/api/chat", json=payload, timeout=120.0)
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "")
        except httpx.ConnectError as exc:
            raise LLMError(
                f"Ollama unreachable at {base}. Install Ollama and `ollama pull {model}` "
                f"for zero-key mode."
            ) from exc
