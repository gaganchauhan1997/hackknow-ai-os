"""
Research skill — free-tier web research via DuckDuckGo + page fetch.
"""

from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup

from core.logger import get_logger

log = get_logger("skill:research")

manifest = {
    "description": "Search the web (DuckDuckGo) and return ranked snippets with optional page-text extraction.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer"},
            "fetch_top": {"type": "integer"},
        },
        "required": ["query"],
    },
}


async def run(query: str, top_k: int = 5, fetch_top: int = 2, **_: Any) -> dict:
    try:
        from duckduckgo_search import DDGS  # type: ignore
    except ImportError:
        return {"status": "skipped", "reason": "duckduckgo-search not installed"}
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=top_k):
            results.append({"title": r.get("title"), "url": r.get("href"), "snippet": r.get("body")})
    extracts: list[dict] = []
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for r in results[:fetch_top]:
            try:
                resp = await client.get(r["url"])
                soup = BeautifulSoup(resp.text, "html.parser")
                for s in soup(["script", "style", "noscript"]):
                    s.decompose()
                extracts.append({"url": r["url"], "text": " ".join(soup.get_text().split())[:6000]})
            except Exception as exc:  # noqa: BLE001
                extracts.append({"url": r["url"], "error": str(exc)})
    return {"query": query, "results": results, "extracts": extracts}
