"""Global settings, loaded from .env + YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # --- identity ---
    user_name: str = "Myth"
    assistant_name: str = "Yahavi"
    assistant_mode: Literal["jarvis", "neutral", "playful"] = "jarvis"
    default_lang: Literal["auto", "en", "hi"] = "auto"

    # --- LLM providers ---
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    cohere_api_key: str | None = None
    mistral_api_key: str | None = None
    together_api_key: str | None = None
    openrouter_api_key: str | None = None
    huggingface_api_key: str | None = None

    # --- local fallback ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # --- voice ---
    whisper_model: str = "base"
    kokoro_voice_en: str = "af_bella"
    kokoro_voice_hi: str = "hf_alpha"

    # --- browser ---
    playwright_headless: bool = True

    # --- ecommerce ---
    wc_base_url: str = "https://shop.hackknow.com"
    wc_consumer_key: str | None = None
    wc_consumer_secret: str | None = None
    medusa_base_url: str = "http://localhost:9000"
    medusa_api_key: str | None = None

    # --- content + workflow ---
    comfyui_base_url: str = "http://localhost:8188"
    flowise_base_url: str = "http://localhost:3000"
    flowise_api_key: str | None = None

    # --- server ---
    hackknow_host: str = "0.0.0.0"
    hackknow_port: int = 8787
    hackknow_log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- helpers ---
    def llm_pool(self) -> list[dict]:
        path = ROOT / "config" / "llm_pool.yaml"
        with open(path) as f:
            return yaml.safe_load(f)["providers"]

    def agent_registry(self) -> dict:
        path = ROOT / "config" / "agents.yaml"
        with open(path) as f:
            return yaml.safe_load(f)


settings = Settings()
