"""
Android automation skill — wraps `adb` (Android Debug Bridge).

Requires the host device connected via USB or Wi-Fi debugging. Used by the
Voice Assistant + Automation agents to drive a phone like Gemini's on-device
assistant.
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.logger import get_logger

log = get_logger("skill:android")

manifest = {
    "description": "Drive a connected Android device via adb. action='tap'|'swipe'|'text'|'key'|'app'|'screenshot'|'shell'|'devices'.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "x": {"type": "integer"}, "y": {"type": "integer"},
            "x2": {"type": "integer"}, "y2": {"type": "integer"},
            "text": {"type": "string"},
            "key": {"type": "string"},
            "package": {"type": "string"},
            "command": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["action"],
    },
}


async def _adb(args: list[str]) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "adb", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return {"exit": proc.returncode,
            "stdout": out.decode(errors="replace")[:6000],
            "stderr": err.decode(errors="replace")[:2000]}


async def run(action: str, **kwargs: Any) -> dict:
    if action == "devices":
        return await _adb(["devices"])
    if action == "tap":
        return await _adb(["shell", "input", "tap", str(kwargs["x"]), str(kwargs["y"])])
    if action == "swipe":
        return await _adb(["shell", "input", "swipe",
                           str(kwargs["x"]), str(kwargs["y"]),
                           str(kwargs["x2"]), str(kwargs["y2"]), "300"])
    if action == "text":
        return await _adb(["shell", "input", "text", kwargs["text"].replace(" ", "%s")])
    if action == "key":
        return await _adb(["shell", "input", "keyevent", kwargs["key"]])
    if action == "app":
        return await _adb(["shell", "monkey", "-p", kwargs["package"], "-c", "android.intent.category.LAUNCHER", "1"])
    if action == "screenshot":
        await _adb(["shell", "screencap", "-p", "/sdcard/_hk.png"])
        path = kwargs.get("path", "/tmp/android_screen.png")
        await _adb(["pull", "/sdcard/_hk.png", path])
        return {"path": path}
    if action == "shell":
        return await _adb(["shell", kwargs["command"]])
    return {"status": "unknown", "action": action}
