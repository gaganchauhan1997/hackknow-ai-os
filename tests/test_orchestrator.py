"""Boot test — verifies registry, skills, and agents wire up without network."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_imports():
    from core.orchestrator import HackKnowOS
    from core.planner import Planner
    from core.workflow import WorkflowEngine
    from core.memory import Memory
    from core.skill_registry import SkillRegistry
    assert HackKnowOS and Planner and WorkflowEngine and Memory and SkillRegistry


def test_registry_loads():
    from config import settings
    reg = settings.agent_registry()
    assert "agents" in reg
    assert "ceo" in reg["agents"]
    assert len(reg["agents"]) == 15


def test_skill_registry_discovers():
    from core.skill_registry import SkillRegistry
    sr = SkillRegistry()
    names = sr.names()
    assert "browser" in names
    assert "voice" in names
    assert "ecommerce" in names


def test_i18n_detection():
    from core.i18n import detect_language
    assert detect_language("hello there") == "en"
    assert detect_language("नमस्ते बॉस") == "hi"
    assert detect_language("kya scene hai boss") == "hi"


if __name__ == "__main__":
    test_imports(); print("✓ imports")
    test_registry_loads(); print("✓ registry")
    test_skill_registry_discovers(); print("✓ skills")
    test_i18n_detection(); print("✓ i18n")
    print("All checks passed.")
