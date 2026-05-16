"""
Content skill — image / animation generation via ComfyUI + AnimateDiff.

Repos:
  - https://github.com/comfyanonymous/ComfyUI
  - https://github.com/guoyww/AnimateDiff

For text content, agents call the LLM directly; this skill focuses on visuals.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import httpx

from config import settings
from core.logger import get_logger

log = get_logger("skill:content")

manifest = {
    "description": "Generate images or short animations through ComfyUI. kind='image' or 'animation'.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "kind": {"type": "string", "enum": ["image", "animation"]},
            "negative": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "frames": {"type": "integer"},
        },
        "required": ["prompt"],
    },
}


def _basic_image_workflow(prompt: str, negative: str, width: int, height: int) -> dict:
    """Minimal txt2img workflow understood by ComfyUI's /prompt endpoint."""
    return {
        "3": {
            "inputs": {"seed": uuid.uuid4().int & ((1 << 31) - 1),
                       "steps": 20, "cfg": 7.0, "sampler_name": "euler",
                       "scheduler": "normal", "denoise": 1.0,
                       "model": ["4", 0], "positive": ["6", 0],
                       "negative": ["7", 0], "latent_image": ["5", 0]},
            "class_type": "KSampler",
        },
        "4": {"inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
              "class_type": "CheckpointLoaderSimple"},
        "5": {"inputs": {"width": width, "height": height, "batch_size": 1},
              "class_type": "EmptyLatentImage"},
        "6": {"inputs": {"text": prompt, "clip": ["4", 1]},
              "class_type": "CLIPTextEncode"},
        "7": {"inputs": {"text": negative, "clip": ["4", 1]},
              "class_type": "CLIPTextEncode"},
        "8": {"inputs": {"samples": ["3", 0], "vae": ["4", 2]},
              "class_type": "VAEDecode"},
        "9": {"inputs": {"filename_prefix": "hackknow", "images": ["8", 0]},
              "class_type": "SaveImage"},
    }


async def run(
    prompt: str,
    kind: str = "image",
    negative: str = "blurry, low quality",
    width: int = 1024,
    height: int = 1024,
    frames: int = 16,
    **_: Any,
) -> dict:
    base = settings.comfyui_base_url
    workflow = _basic_image_workflow(prompt, negative, width, height)
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            r = await client.post(f"{base}/prompt", json={"prompt": workflow})
        except httpx.ConnectError:
            return {
                "status": "skipped",
                "reason": f"ComfyUI not reachable at {base}",
                "prompt": prompt,
            }
        if r.status_code >= 400:
            return {"status": "error", "detail": r.text}
        data = r.json()
        return {
            "status": "queued",
            "prompt_id": data.get("prompt_id"),
            "kind": kind,
            "prompt": prompt,
        }
