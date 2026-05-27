"""
Skill registry — discovers and hot-loads skill modules from ``skills/``.

Each skill exposes a module-level ``manifest`` dict and an ``async run(...)``
callable, so agents can use them without bespoke wiring.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any, Callable

import skills as skills_pkg
from core.logger import get_logger

log = get_logger("skills")


@dataclass
class Skill:
    name: str
    description: str
    module: Any
    runner: Callable[..., Any]
    manifest: dict


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self.discover()

    # ----------------------------------------------------------- discover
    def discover(self) -> None:
        for info in pkgutil.iter_modules(skills_pkg.__path__):
            if info.name.startswith("_"):
                continue
            try:
                pkg = importlib.import_module(f"skills.{info.name}")
            except Exception as exc:  # noqa: BLE001
                log.warning(f"skill '{info.name}' failed to import: {exc}")
                continue
            manifest = getattr(pkg, "manifest", None)
            run = getattr(pkg, "run", None)
            if not manifest or not run:
                continue
            self._skills[info.name] = Skill(
                name=info.name,
                description=manifest.get("description", ""),
                module=pkg,
                runner=run,
                manifest=manifest,
            )
            log.info(f"loaded skill: {info.name}")

    # ----------------------------------------------------------- access
    def names(self) -> list[str]:
        return sorted(self._skills)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    async def run(self, _skill_name: str, **kwargs):
        skill = self.get(_skill_name)
        if not skill:
            raise KeyError(f"unknown skill: {_skill_name}")
        return await skill.runner(**kwargs)

    def tool_spec(self) -> list[dict]:
        """Generate OpenAI-style tool specs for agents to call."""
        out = []
        for skill in self._skills.values():
            out.append({
                "type": "function",
                "function": {
                    "name": skill.name,
                    "description": skill.description,
                    "parameters": skill.manifest.get("parameters", {}),
                },
            })
        return out
