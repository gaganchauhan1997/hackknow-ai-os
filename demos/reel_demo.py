"""
Reel demo — end-to-end vertical reel generation.

Usage:
    python demos/reel_demo.py "Bold launch reel for Hackknow energy mug"
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orchestrator import HackKnowOS  # noqa: E402


async def main(concept: str):
    os_ = HackKnowOS()
    await os_.boot()
    print(await os_.delegate("reel_creator", {"task": concept}))
    await os_.shutdown()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "Hackknow launch-day reel"))
