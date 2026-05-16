"""
Video skill — Remotion (Node) bridge + ffmpeg fallback.

Repo:
  - https://github.com/remotion-dev/remotion

If a Remotion project is present at ``video_project/``, we shell out to
``npx remotion render``. Otherwise we fall back to ffmpeg slideshow from
provided frame paths.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any

from config.settings import ROOT
from core.logger import get_logger

log = get_logger("skill:video")

manifest = {
    "description": "Render videos. Pass frames (list of image paths or URLs), optional voiceover path, captions. Returns the output mp4 path.",
    "parameters": {
        "type": "object",
        "properties": {
            "frames": {"type": "array"},
            "voiceover": {"type": "string"},
            "captions": {"type": "array"},
            "aspect": {"type": "string", "enum": ["9:16", "16:9", "1:1"]},
            "output": {"type": "string"},
        },
    },
}


async def _ffmpeg_slideshow(frames: list[str], voiceover: str | None, output: str, aspect: str) -> str:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not installed.")
    with tempfile.TemporaryDirectory() as tmp:
        # Build a concat-friendly directory of normalised frames
        tmpdir = Path(tmp)
        for i, src in enumerate(frames):
            target = tmpdir / f"f{i:04d}.png"
            if isinstance(src, dict):
                src = src.get("path") or src.get("url") or ""
            if not src:
                continue
            target.write_bytes(Path(src).read_bytes() if Path(src).exists() else b"")
        # build ffmpeg command
        scale = {"9:16": "1080:1920", "16:9": "1920:1080", "1:1": "1080:1080"}[aspect]
        cmd = [
            "ffmpeg", "-y",
            "-framerate", "2",
            "-i", str(tmpdir / "f%04d.png"),
            "-vf", f"scale={scale}:force_original_aspect_ratio=increase,crop={scale}",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-r", "30",
        ]
        if voiceover and Path(voiceover).exists():
            cmd += ["-i", voiceover, "-c:a", "aac", "-shortest"]
        cmd.append(output)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {err.decode(errors='replace')}")
    return output


async def run(
    frames: list | None = None,
    voiceover: Any = None,
    captions: list | None = None,
    aspect: str = "9:16",
    output: str | None = None,
    **_: Any,
) -> dict:
    output = output or str(ROOT / ".cache" / "reel.mp4")
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    frames = frames or []
    if isinstance(voiceover, dict):
        voiceover = voiceover.get("path")
    # Try Remotion first
    remotion_dir = ROOT / "video_project"
    if remotion_dir.exists():
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx", "remotion", "render", "MainComp", output,
                cwd=str(remotion_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate()
            if proc.returncode == 0:
                return {"renderer": "remotion", "output": output}
            log.warning(f"remotion fallback to ffmpeg: {err.decode(errors='replace')}")
        except FileNotFoundError:
            pass
    if frames:
        try:
            await _ffmpeg_slideshow(frames, voiceover, output, aspect)
            return {"renderer": "ffmpeg", "output": output}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "detail": str(exc)}
    return {"status": "skipped", "reason": "no frames provided"}
