"""Hindi / English detection + JARVIS-style addressing helpers."""

from __future__ import annotations

import re

from config import settings

# Devanagari range U+0900-U+097F. Any presence flips us to Hindi mode.
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Common Hinglish trigger words (romanised Hindi). Keeps responses friendly when
# the user writes "kya scene hai bro" without using Devanagari script.
_HINGLISH_HINTS = {
    "kya", "kaise", "kaisa", "hai", "ho", "kar", "karo", "karke", "kyu",
    "kyun", "matlab", "abhi", "bhai", "boss", "bro", "yaar", "thoda", "scene",
}


def detect_language(text: str) -> str:
    """Return 'hi' for Hindi/Hinglish, 'en' otherwise."""
    if settings.default_lang in ("hi", "en"):
        return settings.default_lang
    if _DEVANAGARI.search(text):
        return "hi"
    tokens = {tok.lower().strip(",.?!") for tok in text.split()}
    if tokens & _HINGLISH_HINTS:
        return "hi"
    return "en"


def address(name: str | None = None) -> str:
    """JARVIS-style address. Returns 'Boss' when assistant_mode == 'jarvis'."""
    if settings.assistant_mode == "jarvis":
        return "Boss"
    return name or settings.user_name


def style_prefix(lang: str) -> str:
    """Return a small system-prompt suffix for tone."""
    if settings.assistant_mode == "jarvis":
        if lang == "hi":
            return (
                "तुम Yahavi हो — Boss के लिए एक JARVIS-style autonomous assistant. "
                "हमेशा Boss कहकर सम्बोधित करो। बोल्ड, सटीक, mission-focused रहो।"
            )
        return (
            "You are Yahavi — a JARVIS-style autonomous assistant operating for Boss. "
            "Address the user as 'Boss'. Bold, precise, mission-focused."
        )
    return ""
