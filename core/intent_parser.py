"""
Intent parser — adapted from YahavisAI/core/intent_parser.py.

Converts a raw user utterance into a structured intent object the
orchestrator can route directly to the right specialist agent or skill.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from core.llm_router import LLMRouter
from core.logger import get_logger

log = get_logger("intent_parser")

INTENT_CATEGORIES = [
    "FILE_OP", "APP_CONTROL", "BROWSER", "SYSTEM", "CONTENT_GEN",
    "HACKKNOW", "MEMORY", "CODE", "CHAT",
]

INTENT_TO_AGENT = {
    "FILE_OP":     "automation",
    "APP_CONTROL": "automation",
    "BROWSER":     "browser",
    "SYSTEM":      "automation",
    "CONTENT_GEN": "content_creator",
    "HACKKNOW":    "ecommerce",
    "MEMORY":      "research",
    "CODE":        "developer",
    "CHAT":        "ceo",
}

INTENT_TO_SKILL = {
    "FILE_OP":     "computer_control",
    "APP_CONTROL": "computer_control",
    "SYSTEM":      "computer_control",
}


@dataclass
class Intent:
    intent: str = "CHAT"
    action: str = ""
    target: str = ""
    params: dict = field(default_factory=dict)
    language: str = "en"
    confidence: float = 0.5
    voice_response: str = ""

    @property
    def best_agent(self) -> str:
        return INTENT_TO_AGENT.get(self.intent, "ceo")

    @property
    def best_skill(self) -> str | None:
        return INTENT_TO_SKILL.get(self.intent)


_PROMPT = """You are HackKnow Intent Parser. Output STRICT JSON ONLY:
{
  "intent": "<CATEGORY>",
  "action": "<verb>",
  "target": "<what to act on>",
  "params": {},
  "language": "<en|hi|hinglish>",
  "confidence": 0.0-1.0,
  "voice_response": "<short reply>"
}
CATEGORIES: """ + ", ".join(INTENT_CATEGORIES) + """

EXAMPLES:
"Open VS Code" → {"intent":"APP_CONTROL","action":"open","target":"vs code","params":{"app_name":"code"},"language":"en","confidence":0.98,"voice_response":"Opening VS Code, Boss."}
"shop.hackknow.com pe low stock items dikha" → {"intent":"HACKKNOW","action":"list_low_stock","target":"shop","params":{},"language":"hinglish","confidence":0.95,"voice_response":"Checking low-stock items now, Boss."}
"3-word reply: ping" → {"intent":"CHAT","action":"reply","target":"","params":{"text":"pong, online, ready"},"language":"en","confidence":0.99,"voice_response":""}
"""


class IntentParser:
    def __init__(self, llm: LLMRouter) -> None:
        self.llm = llm

    async def parse(self, utterance: str) -> Intent:
        try:
            raw = await self.llm.chat(
                messages=[
                    {"role": "system", "content": _PROMPT},
                    {"role": "user", "content": utterance},
                ],
                tier="fast", json_mode=True, max_tokens=400,
            )
        except Exception as exc:
            log.warning(f"intent llm failed: {exc}")
            return Intent(voice_response=str(utterance)[:200])

        data = _coerce_json(raw)
        return Intent(
            intent=str(data.get("intent", "CHAT")).upper(),
            action=str(data.get("action", "")),
            target=str(data.get("target", "")),
            params=data.get("params") or {},
            language=str(data.get("language", "en")),
            confidence=float(data.get("confidence", 0.5)),
            voice_response=str(data.get("voice_response", "")),
        )


def _coerce_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*", "", raw).rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}
