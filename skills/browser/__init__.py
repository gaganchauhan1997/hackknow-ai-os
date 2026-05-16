"""
Browser skill — wraps browser-use + Playwright.

Repos:
  - https://github.com/browser-use/browser-use
  - https://github.com/microsoft/playwright
"""

from __future__ import annotations

from typing import Any

from core.logger import get_logger
from config import settings

log = get_logger("skill:browser")

manifest = {
    "description": "Headless browser automation (browser-use + Playwright). Supports navigate, scrape, fill_form, click, screenshot, and high-level social_post.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["navigate", "scrape", "fill_form", "screenshot", "social_post"]},
            "url": {"type": "string"},
            "instruction": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": ["action"],
    },
}


async def _ensure_playwright():
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"
        ) from exc


async def run(action: str, **kwargs: Any) -> dict:
    """Dispatch a browser action."""
    await _ensure_playwright()
    from playwright.async_api import async_playwright

    if action == "navigate":
        url = kwargs["url"]
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            title = await page.title()
            await browser.close()
            return {"url": url, "title": title}

    if action == "scrape":
        url = kwargs["url"]
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            text = await page.evaluate("() => document.body.innerText")
            await browser.close()
            return {"url": url, "text": text[:50000]}

    if action == "screenshot":
        url = kwargs["url"]
        path = kwargs.get("path", "screenshot.png")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await page.screenshot(path=path, full_page=True)
            await browser.close()
            return {"path": path}

    if action == "social_post":
        # Delegated to browser-use agent for high-level intent
        try:
            from browser_use import Agent as BrowserUseAgent  # type: ignore
            from langchain_community.chat_models import ChatOllama  # type: ignore
        except ImportError:
            return {
                "status": "skipped",
                "reason": "browser-use not installed (pip install browser-use)",
                "instruction": kwargs.get("instruction"),
            }
        instr = kwargs.get("instruction") or "Post to social media"
        agent = BrowserUseAgent(task=instr, llm=ChatOllama(model="llama3.1:8b"))
        result = await agent.run()
        return {"status": "completed", "trace": str(result)[:2000]}

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
            return {"url": url, "filled": list(fields)}

    raise ValueError(f"Unknown browser action: {action}")
