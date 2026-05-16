"""
Voice clone skill — XTTS-v2 voice cloning using the attached samples.

Repos / models:
  - Coqui XTTS-v2 (https://huggingface.co/coqui/XTTS-v2)
  - F5-TTS  (https://github.com/SWivid/F5-TTS) — optional, very fast
  - OpenVoice V2 (https://github.com/myshell-ai/OpenVoice) — optional fallback

Reference voices live under ``voice_samples/``:
  - laksh_male_soft.mp3       (Boss's male reference)
  - priyanka_female_soft.mp3  (Boss's female reference)

The skill is multilingual: Hindi + English work out of the box on XTTS-v2.
First call downloads ~1.8GB of weights (one-time). Quality is studio-grade,
not robotic.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from config.settings import ROOT
from core.logger import get_logger

log = get_logger("skill:voice_clone")

manifest = {
    "description": "Clone Boss's male or female reference voice with XTTS-v2 (Hindi + English). Falls back to F5-TTS / OpenVoice if XTTS unavailable.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "voice": {"type": "string", "enum": ["male", "female", "auto"]},
            "lang": {"type": "string", "enum": ["en", "hi", "auto"]},
            "engine": {"type": "string", "enum": ["xtts", "f5", "openvoice", "auto"]},
            "out_path": {"type": "string"},
        },
        "required": ["text"],
    },
}


VOICE_SAMPLES = ROOT / "voice_samples"
DEFAULT_MALE = VOICE_SAMPLES / "laksh_male_soft.mp3"
DEFAULT_FEMALE = VOICE_SAMPLES / "priyanka_female_soft.mp3"

_xtts = None


def _pick_sample(voice: str) -> Path:
    if voice == "female":
        return DEFAULT_FEMALE
    return DEFAULT_MALE


def _load_xtts():
    global _xtts
    if _xtts is None:
        from TTS.api import TTS  # type: ignore
        _xtts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                    progress_bar=False, gpu=False)
    return _xtts


def _xtts_sync(text: str, voice: str, lang: str, out_path: str) -> dict:
    tts = _load_xtts()
    sample = _pick_sample(voice)
    if not sample.exists():
        return {"status": "error", "reason": f"reference sample missing: {sample}"}
    tts.tts_to_file(text=text, speaker_wav=str(sample),
                    language="hi" if lang == "hi" else "en", file_path=out_path)
    return {"engine": "xtts-v2", "voice": voice, "lang": lang, "path": out_path}


def _f5_sync(text: str, voice: str, lang: str, out_path: str) -> dict:
    try:
        from f5_tts.api import F5TTS  # type: ignore
    except ImportError:
        return {"status": "skipped", "reason": "f5_tts not installed"}
    sample = _pick_sample(voice)
    f5 = F5TTS()
    f5.infer(ref_file=str(sample), ref_text="", gen_text=text, file_wave=out_path)
    return {"engine": "f5-tts", "voice": voice, "path": out_path}


def _openvoice_sync(text: str, voice: str, lang: str, out_path: str) -> dict:
    return {"status": "skipped", "reason": "OpenVoice setup required (see docs/VOICE.md)"}


async def run(text: str, voice: str = "male", lang: str = "auto",
              engine: str = "auto", out_path: str | None = None, **_: Any) -> dict:
    out_path = out_path or str(ROOT / ".cache" / "tts_out.wav")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    if lang == "auto":
        # crude detection: any Devanagari ⇒ Hindi
        lang = "hi" if any("ऀ" <= ch <= "ॿ" for ch in text) else "en"
    if voice == "auto":
        voice = "male"

    if engine in ("auto", "xtts"):
        try:
            return await asyncio.to_thread(_xtts_sync, text, voice, lang, out_path)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"XTTS failed: {exc} — trying F5")
    if engine in ("auto", "f5"):
        try:
            return await asyncio.to_thread(_f5_sync, text, voice, lang, out_path)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"F5 failed: {exc} — trying OpenVoice")
    return await asyncio.to_thread(_openvoice_sync, text, voice, lang, out_path)
