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
        "Browser automation. action='scrape' (text + title via httpx fallback when "
        "Playwright is missing), 'navigate', 'screenshot', 'fill_form', 'social_post'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["navigate", "scrape", "fill_form", "screenshot", "social_post"]},
            "url": {"type": "string"},
            "instruction": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": ["action"],
    },
}


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
