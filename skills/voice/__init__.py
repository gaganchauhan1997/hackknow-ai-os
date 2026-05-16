"""
Voice skill — faster-whisper for STT, kokoro for TTS, optional livekit transport.

Repos:
  - https://github.com/SYSTRAN/faster-whisper
  - https://github.com/hexgrad/kokoro
  - https://github.com/livekit/agents
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config import settings
from core.logger import get_logger

log = get_logger("skill:voice")

manifest = {
    "description": "Voice I/O. mode='stt' for speech→text via faster-whisper; mode='tts' for text→speech via kokoro.",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["stt", "tts"]},
            "audio_path": {"type": "string"},
            "text": {"type": "string"},
            "lang": {"type": "string", "enum": ["en", "hi", "auto"]},
        },
        "required": ["mode"],
    },
}

_whisper_model = None


def _load_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(
            settings.whisper_model, device="auto", compute_type="int8"
        )
    return _whisper_model


def _stt(audio_path: str, lang: str | None = None) -> dict:
    model = _load_whisper()
    segments, info = model.transcribe(
        audio_path,
        language=None if (not lang or lang == "auto") else lang,
        vad_filter=True,
    )
    text = " ".join(s.text.strip() for s in segments)
    return {
        "text": text,
        "language": info.language,
        "duration": info.duration,
    }


def _tts(text: str, lang: str = "en", out_path: str | None = None) -> dict:
    out_path = out_path or "out.wav"
    try:
        # kokoro v0.x style
        from kokoro import KPipeline  # type: ignore
    except ImportError:
        return {
            "status": "skipped",
            "reason": "kokoro not installed (pip install kokoro)",
            "text": text,
        }
    voice = settings.kokoro_voice_hi if lang == "hi" else settings.kokoro_voice_en
    pipe = KPipeline(lang_code=("h" if lang == "hi" else "a"))
    generator = pipe(text, voice=voice)
    import numpy as np
    import soundfile as sf
    audio_chunks = [audio for _, _, audio in generator]
    if not audio_chunks:
        return {"status": "error", "reason": "no audio produced"}
    audio = np.concatenate(audio_chunks)
    sf.write(out_path, audio, 24000)
    return {"path": str(Path(out_path).resolve()), "voice": voice}


async def run(mode: str, **kwargs: Any) -> dict:
    if mode == "stt":
        audio_path = kwargs["audio_path"]
        return _stt(audio_path, lang=kwargs.get("lang"))
    if mode == "tts":
        return _tts(
            text=kwargs.get("text", ""),
            lang=kwargs.get("lang", "en"),
            out_path=kwargs.get("out_path"),
        )
    raise ValueError(f"Unknown voice mode: {mode}")
