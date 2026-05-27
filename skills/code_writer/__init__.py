"""
Code writer skill — adapted from YahavisAI/skills/code_writer.py.

Generates code via the LLM router, saves it to disk, optionally opens
it in the system default editor.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from config.settings import ROOT
from core.logger import get_logger

log = get_logger("skill:code_writer")

manifest = {
    "description": "Generate code and save to disk. Returns path + content. Optionally opens the file in the system editor.",
    "parameters": {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "language":    {"type": "string"},
            "filename":    {"type": "string"},
            "open_after":  {"type": "boolean"},
        },
        "required": ["description"],
    },
}

EXTENSION_MAP = {
    "python": ".py", "py": ".py",
    "javascript": ".js", "js": ".js", "typescript": ".ts", "ts": ".ts",
    "jsx": ".jsx", "tsx": ".tsx", "react": ".jsx",
    "html": ".html", "css": ".css",
    "java": ".java", "cpp": ".cpp", "c": ".c",
    "go": ".go", "rust": ".rs",
    "bash": ".sh", "shell": ".sh",
    "sql": ".sql", "json": ".json",
    "markdown": ".md", "md": ".md",
    "yaml": ".yml", "toml": ".toml",
}

OUTPUT_DIR = ROOT / "workspaces" / "_code"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CODE_SYSTEM_PROMPT = (
    "You are an expert programmer. Write clean, well-commented, production-ready "
    "code. Include imports, error handling, docstrings. No explanations — output "
    "ONLY the code. No markdown fences."
)


def _ext(lang: str) -> str:
    return EXTENSION_MAP.get(lang.lower(), ".txt")


def _open_in_editor(path: Path) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


async def run(
    description: str,
    language: str = "python",
    filename: str | None = None,
    open_after: bool = False,
    **_: Any,
) -> dict:
    # Late import to avoid circular deps
    from core.llm_router import LLMRouter
    llm = LLMRouter()
    messages = [
        {"role": "system", "content": CODE_SYSTEM_PROMPT},
        {"role": "user",   "content": f"Language: {language}\n\nTask:\n{description}"},
    ]
    try:
        code = await llm.chat(messages=messages, tier="strong", max_tokens=3000)
    finally:
        await llm.aclose()
    # strip fences if model added them
    code = code.strip()
    if code.startswith("```"):
        import re
        code = re.sub(r"^```[a-zA-Z]*\n", "", code)
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()
    name = filename or f"hackknow_{int(time.time())}{_ext(language)}"
    path = OUTPUT_DIR / name
    path.write_text(code, encoding="utf-8")
    if open_after:
        _open_in_editor(path)
    return {
        "path": str(path),
        "filename": name,
        "language": language,
        "bytes": len(code),
        "preview": code[:1200],
    }
