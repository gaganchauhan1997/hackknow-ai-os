"""
Realtime search skill — multi-provider live web search.

Routes the query to whichever provider has a key configured. Returns a unified
schema regardless of vendor.

Supported providers (env keys):
  TAVILY_API_KEY    — https://tavily.com
  EXA_API_KEY       — https://exa.ai
  SERPER_API_KEY    — https://serper.dev
  BRAVE_API_KEY     — https://search.brave.com/help/api
  FIRECRAWL_API_KEY — https://firecrawl.dev
  JINA_API_KEY      — https://jina.ai/reader
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from core.logger import get_logger

log = get_logger("skill:realtime_search")

manifest = {
    "description": "Live web search via Tavily / Exa / Serper / Brave / Firecrawl / Jina. Returns ranked results with snippets.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "provider": {"type": "string", "enum": ["auto", "tavily", "exa", "serper", "brave", "firecrawl", "jina"]},
            "top_k": {"type": "integer"},
        },
        "required": ["query"],
    },
}


async def _tavily(client: httpx.AsyncClient, q: str, k: int) -> list[dict]:
    r = await client.post("https://api.tavily.com/search", json={
        "api_key": os.environ["TAVILY_API_KEY"], "query": q, "max_results": k,
    })
    r.raise_for_status()
    data = r.json()
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content")}
            for x in data.get("results", [])]


async def _exa(client: httpx.AsyncClient, q: str, k: int) -> list[dict]:
    r = await client.post("https://api.exa.ai/search",
        json={"query": q, "numResults": k},
        headers={"x-api-key": os.environ["EXA_API_KEY"]})
    r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("text") or ""}
            for x in r.json().get("results", [])]


async def _serper(client: httpx.AsyncClient, q: str, k: int) -> list[dict]:
    r = await client.post("https://google.serper.dev/search",
        json={"q": q, "num": k}, headers={"X-API-KEY": os.environ["SERPER_API_KEY"]})
    r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("link"), "snippet": x.get("snippet")}
            for x in r.json().get("organic", [])]


async def _brave(client: httpx.AsyncClient, q: str, k: int) -> list[dict]:
    r = await client.get("https://api.search.brave.com/res/v1/web/search",
        params={"q": q, "count": k},
        headers={"X-Subscription-Token": os.environ["BRAVE_API_KEY"]})
    r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("description")}
            for x in r.json().get("web", {}).get("results", [])]


async def _firecrawl(client: httpx.AsyncClient, q: str, k: int) -> list[dict]:
    r = await client.post("https://api.firecrawl.dev/v1/search",
        json={"query": q, "limit": k},
        headers={"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"})
    r.raise_for_status()
    data = r.json().get("data", [])
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("description") or ""}
            for x in data]


async def _jina(client: httpx.AsyncClient, q: str, k: int) -> list[dict]:
    # Jina Reader: pass a query, it returns top results in markdown
    r = await client.get(f"https://s.jina.ai/{q}", headers={
        "Authorization": f"Bearer {os.environ['JINA_API_KEY']}", "Accept": "application/json",
    })
    r.raise_for_status()
    data = r.json().get("data", [])
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content")}
            for x in data[:k]]


PROVIDERS = {
    "tavily":    ("TAVILY_API_KEY",    _tavily),
    "exa":       ("EXA_API_KEY",       _exa),
    "serper":    ("SERPER_API_KEY",    _serper),
    "brave":     ("BRAVE_API_KEY",     _brave),
    "firecrawl": ("FIRECRAWL_API_KEY", _firecrawl),
    "jina":      ("JINA_API_KEY",      _jina),
}


async def run(query: str, provider: str = "auto", top_k: int = 6, **_: Any) -> dict:
    candidates: list[str]
    if provider == "auto":
        candidates = [name for name, (env, _) in PROVIDERS.items() if os.getenv(env)]
        if not candidates:
            # graceful free-tier fallback
            from skills import research
            r = await research.run(query=query, top_k=top_k)
            return {"provider": "duckduckgo_fallback", "results": r.get("results", [])}
    else:
        candidates = [provider]
    last = None
    async with httpx.AsyncClient(timeout=20.0) as client:
        for name in candidates:
            env, fn = PROVIDERS[name]
            if not os.getenv(env):
                continue
            try:
                items = await fn(client, query, top_k)
                return {"provider": name, "results": items}
            except Exception as exc:  # noqa: BLE001
                last = exc
                log.warning(f"{name} failed: {exc}")
    return {"status": "error", "error": str(last)}
