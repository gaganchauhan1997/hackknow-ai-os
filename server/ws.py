"""Standalone WebSocket helpers (kept thin; main WS lives in server/api.py)."""

from __future__ import annotations

import json

from fastapi import WebSocket


async def push_json(ws: WebSocket, payload: dict) -> None:
    await ws.send_text(json.dumps(payload, ensure_ascii=False))
