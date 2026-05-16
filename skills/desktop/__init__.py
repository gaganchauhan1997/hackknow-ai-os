"""
Desktop automation skill — PyAutoGUI based.

Best-effort: only available on a real desktop session (X / Wayland / macOS / Windows).
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.logger import get_logger

log = get_logger("skill:desktop")

manifest = {
    "description": "Desktop input automation via PyAutoGUI (click, type, hotkey, screenshot).",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["click", "type", "hotkey", "screenshot", "move"]},
            "x": {"type": "integer"}, "y": {"type": "integer"},
            "text": {"type": "string"},
            "keys": {"type": "array", "items": {"type": "string"}},
            "path": {"type": "string"},
        },
        "required": ["action"],
    },
}


def _run_sync(action: str, kwargs: dict) -> dict:
    try:
        import pyautogui  # type: ignore
    except ImportError:
        return {"status": "skipped", "reason": "pyautogui not installed; pip install pyautogui"}
    pyautogui.FAILSAFE = True
    if action == "click":
        pyautogui.click(x=kwargs.get("x"), y=kwargs.get("y"))
        return {"ok": True}
    if action == "type":
        pyautogui.typewrite(kwargs.get("text", ""), interval=0.03)
        return {"ok": True}
    if action == "hotkey":
        pyautogui.hotkey(*kwargs.get("keys", []))
        return {"ok": True}
    if action == "screenshot":
        img = pyautogui.screenshot()
        path = kwargs.get("path", "/tmp/screen.png")
        img.save(path)
        return {"path": path}
    if action == "move":
        pyautogui.moveTo(kwargs.get("x"), kwargs.get("y"), duration=0.2)
        return {"ok": True}
    return {"status": "unknown"}


async def run(action: str, **kwargs: Any) -> dict:
    return await asyncio.to_thread(_run_sync, action, kwargs)
