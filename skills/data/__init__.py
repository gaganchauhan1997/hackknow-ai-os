"""
Data skill — pandas-ai natural-language data analysis + dashboard prep.

Repo:
  - https://github.com/sinaptik-ai/pandas-ai
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.logger import get_logger

log = get_logger("skill:data")

manifest = {
    "description": "Analyse a CSV / Excel / DataFrame with a natural-language instruction. Returns either text insight or a DataFrame summary.",
    "parameters": {
        "type": "object",
        "properties": {
            "instruction": {"type": "string"},
            "dataset": {"type": "string"},
        },
        "required": ["instruction"],
    },
}


def _load(dataset: Any) -> pd.DataFrame:
    if isinstance(dataset, pd.DataFrame):
        return dataset
    if isinstance(dataset, (str, Path)):
        p = Path(dataset)
        if p.suffix.lower() == ".csv":
            return pd.read_csv(p)
        if p.suffix.lower() in (".xlsx", ".xls"):
            return pd.read_excel(p)
    raise ValueError(f"Unsupported dataset type: {type(dataset)}")


async def run(instruction: str, dataset: Any = None, **_: Any) -> dict:
    if dataset is None:
        return {"status": "skipped", "reason": "no dataset provided"}
    df = _load(dataset)
    try:
        from pandasai import SmartDataframe  # type: ignore
        from pandasai.llm import OpenAI  # type: ignore
        # pandas-ai will read OPENAI_API_KEY from env — we route through
        # OpenRouter's free models by aliasing the base URL if available.
        import os
        if os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
            os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
        sdf = SmartDataframe(df, config={"llm": OpenAI()})
        result = sdf.chat(instruction)
        return {"result": str(result)[:5000], "rows": len(df), "columns": list(df.columns)}
    except Exception as exc:  # noqa: BLE001
        log.warning(f"pandasai unavailable ({exc}) — falling back to pandas describe")
        return {
            "fallback": True,
            "rows": len(df),
            "columns": list(df.columns),
            "describe": df.describe(include="all").to_dict(),
        }
