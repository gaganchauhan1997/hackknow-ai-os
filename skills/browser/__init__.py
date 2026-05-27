"""
Browser skill — Playwright when available, httpx + BeautifulSoup fallback
so basic scrape/navigate work on the lean Render deploy too.
"""

from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup

from core.logger import get_logger
from config import settings

log = get_logger("skill:browser")

manifest = {
    "description": (
        "Browser automation. action='agentic' (parse intent → client-side actions), "
        "'scrape' (httpx fallback), 'navigate', 'screenshot', 'fill_form', 'social_post'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["agentic", "navigate", "scrape", "fill_form", "screenshot", "social_post"]},
            "url": {"type": "string"},
            "instruction": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": ["action"],
    },
}


# ============================================================
# Heuristic agentic action — returns CLIENT-side instructions
# that the UI executes (window.open, speak, etc.). Works on
# every tier without Playwright.
# ============================================================
import re as _re
import urllib.parse as _up

_DOMAIN_MAP = {
    "youtube":   "https://www.youtube.com",
    "yt":        "https://www.youtube.com",
    "google":    "https://www.google.com",
    "gmail":     "https://mail.google.com",
    "mail":      "https://mail.google.com",
    "facebook":  "https://www.facebook.com",
    "fb":        "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "insta":     "https://www.instagram.com",
    "twitter":   "https://twitter.com",
    "x":         "https://x.com",
    "linkedin":  "https://www.linkedin.com",
    "github":    "https://github.com",
    "reddit":    "https://www.reddit.com",
    "whatsapp":  "https://web.whatsapp.com",
    "spotify":   "https://open.spotify.com",
    "netflix":   "https://www.netflix.com",
    "amazon":    "https://www.amazon.in",
    "flipkart":  "https://www.flipkart.com",
    "hackknow":  "https://hackknow.com",
    "shop":      "https://shop.hackknow.com",
    "wikipedia": "https://en.wikipedia.org",
    "chatgpt":   "https://chat.openai.com",
    "claude":    "https://claude.ai",
    "gemini":    "https://gemini.google.com",
    "perplexity":"https://www.perplexity.ai",
    "render":    "https://dashboard.render.com",
    "cloudflare":"https://dash.cloudflare.com",
}


def _heuristic_intent(instruction: str) -> dict | None:
    """Resolve simple intents (open / play / search) without an LLM call."""
    text = (instruction or "").strip().lower()
    if not text:
        return None
    # search engine?
    m = _re.search(r"(?:search|google|find)\s+(.+?)(?:\s+(?:on|in)\s+(\w+))?$", text)
    if m:
        q = m.group(1).strip()
        engine = (m.group(2) or "google").lower()
        base = {
            "youtube":   "https://www.youtube.com/results?search_query=",
            "google":    "https://www.google.com/search?q=",
            "duckduckgo":"https://duckduckgo.com/?q=",
            "bing":      "https://www.bing.com/search?q=",
        }.get(engine, "https://www.google.com/search?q=")
        return {
            "narrate": f"Searching {engine} for {q}, Boss.",
            "actions": [{"type": "open_url", "url": base + _up.quote(q)}],
        }
    # play X (route to youtube)
    m = _re.search(r"(?:play|sun(?:[oa])?|gana)\s+(.+)", text)
    if m:
        q = m.group(1).strip()
        return {
            "narrate": f"Playing {q} on YouTube, Boss.",
            "actions": [{"type": "open_url",
                         "url": "https://www.youtube.com/results?search_query=" + _up.quote(q)}],
        }
    # direct URL
    url_m = _re.search(r"https?://\S+", text)
    if url_m:
        return {"narrate": "Opening the link, Boss.",
                "actions": [{"type": "open_url", "url": url_m.group(0)}]}
    # open X / kholo X
    m = _re.search(r"^(?:open|kholo?|launch|start|chal+o?|go to|visit)\s+(.+)", text)
    if m:
        target = m.group(1).strip(" .?!")
        # exact match in map
        for key, url in _DOMAIN_MAP.items():
            if target == key or target.startswith(key + " "):
                rest = target[len(key):].strip()
                if rest:
                    # eg. "open youtube and search hackknow"
                    return {"narrate": f"Opening {key.title()}, Boss.",
                            "actions": [{"type": "open_url",
                                         "url": url + "/results?search_query=" + _up.quote(rest)
                                                if "youtube" in url else url}]}
                return {"narrate": f"Opening {key.title()}, Boss.",
                        "actions": [{"type": "open_url", "url": url}]}
        # looks like a domain?
        if "." in target and " " not in target:
            return {"narrate": f"Opening {target}, Boss.",
                    "actions": [{"type": "open_url",
                                 "url": "https://" + target if not target.startswith("http") else target}]}
        # fallback: treat as search query
        return {"narrate": f"Searching for {target}, Boss.",
                "actions": [{"type": "open_url",
                             "url": "https://www.google.com/search?q=" + _up.quote(target)}]}
    return None


async def _agentic_via_llm(instruction: str) -> dict:
    """LLM-driven intent parser. Returns the same shape as heuristic."""
    try:
        from core.llm_router import LLMRouter
    except ImportError:
        return {"status": "error", "reason": "LLM router unavailable"}
    sys_prompt = (
        "Parse the user's intent into STRICT JSON the client browser will execute. "
        "Output ONLY valid JSON with this shape:\n"
        '{"narrate": "<short reply>", "actions": [{"type": "open_url"|"speak"|"copy"|"search", "url": "...", "text": "...", "query": "..."}]}\n'
        "Examples:\n"
        '"Open instagram" → {"narrate":"Opening Instagram, Boss.","actions":[{"type":"open_url","url":"https://instagram.com"}]}\n'
        '"Search news today" → {"narrate":"Searching news, Boss.","actions":[{"type":"open_url","url":"https://www.google.com/search?q=news+today"}]}\n'
        '"What time is it" → {"narrate":"It is currently shown on your device.","actions":[{"type":"speak","text":"Check your clock, Boss."}]}\n'
    )
    llm = LLMRouter()
    try:
        raw = await llm.chat(
            messages=[{"role": "system", "content": sys_prompt},
                      {"role": "user", "content": instruction}],
            tier="fast", json_mode=True, max_tokens=400,
        )
    finally:
        await llm.aclose()
    import json as _json
    raw = raw.strip()
    if raw.startswith("```"):
        raw = _re.sub(r"^```[a-zA-Z]*\n", "", raw).rstrip("`").strip()
    try:
        out = _json.loads(raw)
    except _json.JSONDecodeError:
        m = _re.search(r"\{.*\}", raw, _re.DOTALL)
        out = _json.loads(m.group(0)) if m else {"narrate": raw[:200], "actions": []}
    out.setdefault("engine", "agentic-llm")
    return out


def _has_playwright() -> bool:
    try:
        import playwright.async_api  # noqa: F401
        return True
    except ImportError:
        return False


async def _scrape_httpx(url: str) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) HackKnow/0.2 Safari/605.1.15"
        )
    }
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        title = (soup.title.string.strip() if soup.title and soup.title.string else "")
        text = " ".join(soup.get_text(" ").split())[:30000]
        desc = ""
        m = soup.find("meta", attrs={"name": "description"})
        if m and m.get("content"):
            desc = m["content"][:500]
        return {
            "engine": "httpx",
            "url": url,
            "status": r.status_code,
            "title": title,
            "description": desc,
            "text": text,
            "links": [a.get("href") for a in soup.find_all("a", href=True)[:30]],
        }


async def run(action: str, **kwargs: Any) -> dict:
    has_pw = _has_playwright()

    # agentic: parse intent → client-side actions (works on every tier)
    if action == "agentic":
        instr = kwargs.get("instruction") or kwargs.get("task") or ""
        # try heuristic first (instant, no LLM cost)
        h = _heuristic_intent(instr)
        if h:
            h["engine"] = "agentic-heuristic"
            return h
        # fall through to LLM
        try:
            return await _agentic_via_llm(instr)
        except Exception as exc:
            return {"status": "error", "reason": str(exc),
                    "narrate": "Sorry Boss, I could not parse that.",
                    "actions": []}

    # scrape: prefer httpx (works on lean deploy + production)
    if action == "scrape":
        url = kwargs.get("url", "")
        if not url:
            return {"status": "error", "reason": "url required"}
        try:
            return await _scrape_httpx(url)
        except Exception as exc:
            return {"status": "error", "engine": "httpx", "reason": str(exc), "url": url}

    if not has_pw:
        return {
            "status": "skipped",
            "reason": (
                "Playwright not installed on this deploy (lean tier). "
                "Install requirements-extras.txt + run `playwright install chromium` to enable."
            ),
            "action": action,
        }

    from playwright.async_api import async_playwright

    if action == "navigate":
        url = kwargs["url"]
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            title = await page.title()
            await browser.close()
            return {"engine": "playwright", "url": url, "title": title}

    if action == "screenshot":
        url = kwargs["url"]
        path = kwargs.get("path", "/tmp/screenshot.png")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await page.screenshot(path=path, full_page=True)
            await browser.close()
            return {"engine": "playwright", "path": path}

    if action == "fill_form":
        url = kwargs["url"]
        fields = kwargs.get("payload", {})
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            for selector, value in fields.items():
                await page.fill(selector, str(value))
            await browser.close()
            return {"engine": "playwright", "url": url, "filled": list(fields)}

    if action == "social_post":
        try:
            from browser_use import Agent as BrowserUseAgent  # type: ignore
            from langchain_community.chat_models import ChatOllama  # type: ignore
        except ImportError:
            return {
                "status": "skipped",
                "reason": "browser-use not installed (requirements-extras.txt)",
                "instruction": kwargs.get("instruction"),
            }
        instr = kwargs.get("instruction") or "Post to social media"
        agent = BrowserUseAgent(task=instr, llm=ChatOllama(model="llama3.1:8b"))
        result = await agent.run()
        return {"engine": "browser-use", "status": "completed", "trace": str(result)[:2000]}

    return {"status": "error", "reason": f"unknown browser action: {action}"}
