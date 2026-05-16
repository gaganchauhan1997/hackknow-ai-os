"""
Skill Smith Agent — authors brand-new skill modules autonomously.

Workflow:
  1. Research the target API/library via the research skill.
  2. Plan the skill (name, manifest, endpoints, credentials).
  3. Generate ``skills/_proposed/<name>/__init__.py`` with manifest + run().
  4. Optionally promote to ``skills/<name>/`` after review.
"""

from __future__ import annotations

import re
from pathlib import Path

from agents.base import BaseAgent
from config.settings import ROOT

_SCAFFOLD_PROMPT = """Author a fresh HackKnow skill module.

The skill must implement:
    manifest = {{
        "description": "...",
        "parameters": {{ "type": "object", "properties": {{...}}, "required": [...] }}
    }}

    async def run(**kwargs) -> dict:
        # actual implementation; no placeholders.
        ...

Constraints:
- Pure Python 3.10, async, no top-level network calls.
- Import only stdlib + httpx + bs4 + already-installed deps unless absolutely required.
- All keys come from `os.environ` (document the var names in the docstring).
- Return a clean dict that any agent can consume.

Skill target:
{target}

Reference findings:
{findings}

Return ONLY the full file contents — no markdown fences, no commentary."""


class SkillSmithAgent(BaseAgent):
    role_blurb = (
        "Authors new skill modules autonomously. Researches first, then writes a "
        "production-ready skills/<name>/__init__.py."
    )

    async def author(self, target: str) -> dict:
        # 1. research
        findings = ""
        try:
            r = await self.use_skill("research", query=f"API docs for {target}", top_k=6, fetch_top=2)
            findings = self._compress_findings(r)
        except Exception as exc:
            findings = f"(research failed: {exc})"

        # 2. ask LLM for the file
        prompt = _SCAFFOLD_PROMPT.format(target=target, findings=findings)
        code = await self.llm.chat(
            messages=[
                {"role": "system", "content": self._system_prompt("en")},
                {"role": "user", "content": prompt},
            ],
            tier="reasoning",
            max_tokens=3200,
        )
        code = self._strip_fences(code)

        # 3. choose a name
        name = self._slug(target)
        target_dir = ROOT / "skills" / "_proposed" / name
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / "__init__.py"
        path.write_text(code, encoding="utf-8")

        return {
            "skill_name": name,
            "path": str(path),
            "status": "proposed",
            "note": "Review then move skills/_proposed/<name> → skills/<name> to activate.",
        }

    async def promote(self, name: str) -> dict:
        src = ROOT / "skills" / "_proposed" / name
        dst = ROOT / "skills" / name
        if not src.exists():
            return {"status": "missing"}
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            return {"status": "exists", "path": str(dst)}
        src.rename(dst)
        self.skills.discover()
        return {"status": "promoted", "path": str(dst)}

    async def run(self, instruction: str, context=None):  # type: ignore[override]
        context = context or {}
        if instruction.lower().startswith("promote "):
            return await self.promote(instruction.split(" ", 1)[1].strip())
        result = await self.author(instruction)
        return f"Skill drafted at {result['path']}\n\nReview it, then ask me to 'promote {result['skill_name']}'."

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _slug(target: str) -> str:
        s = re.sub(r"[^a-zA-Z0-9]+", "_", target.lower()).strip("_")
        return s[:40] or "new_skill"

    @staticmethod
    def _strip_fences(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            if text.endswith("```"):
                text = text[:-3]
        return text.strip() + "\n"

    @staticmethod
    def _compress_findings(research_result: dict) -> str:
        out = []
        for r in research_result.get("results", [])[:6]:
            out.append(f"- {r.get('title')} — {r.get('url')}\n  {(r.get('snippet') or '')[:300]}")
        for e in research_result.get("extracts", [])[:2]:
            if "text" in e:
                out.append(f"\n# {e['url']}\n{e['text'][:1500]}")
        return "\n".join(out)
