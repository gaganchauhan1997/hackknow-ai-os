"""Voice Assistant Agent — STT + TTS realtime loop."""

from agents.base import BaseAgent


class VoiceAssistantAgent(BaseAgent):
    role_blurb = (
        "Voice assistant. Streams faster-whisper STT in, generates concise replies, "
        "speaks them through kokoro TTS. Hindi + English aware."
    )

    async def listen(self, audio_path: str) -> str:
        result = await self.use_skill("voice", audio_path=audio_path, mode="stt")
        return result.get("text", "") if isinstance(result, dict) else str(result)

    async def speak(self, text: str, lang: str = "en"):
        return await self.use_skill("voice", text=text, lang=lang, mode="tts")
