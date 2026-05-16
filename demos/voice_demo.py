"""
Voice demo — listen to a wav file, get an autonomous reply, write a reply wav.

Usage:
    python demos/voice_demo.py path/to/input.wav
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orchestrator import HackKnowOS  # noqa: E402


async def main(audio_path: str):
    os_ = HackKnowOS()
    await os_.boot()
    stt = await os_.skills.run("voice", mode="stt", audio_path=audio_path)
    user_text = stt.get("text", "") if isinstance(stt, dict) else ""
    print(f"You said: {user_text}")
    result = await os_.execute(user_text)
    print(f"Reply: {result.summary}")
    await os_.skills.run("voice", mode="tts", text=result.summary, lang=result.language)
    await os_.shutdown()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "input.wav"))
