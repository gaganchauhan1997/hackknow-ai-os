"""Smoke test — boots the OS and reports status."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orchestrator import HackKnowOS  # noqa: E402


async def main():
    os_ = HackKnowOS()
    await os_.boot()
    print("OK")
    print("  agents:", list(os_.agents))
    print("  skills:", os_.skills.names())
    await os_.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
