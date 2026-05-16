"""
Marketing demo — full campaign run.

Usage:
    python demos/marketing_demo.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orchestrator import HackKnowOS  # noqa: E402


PROMPT = """
Plan and prepare a 7-day launch campaign for the new 'Hackknow Hustle Mug' on
shop.hackknow.com. Include: positioning, 3 channel angles, 7 social posts,
2 reel scripts, an SEO meta description, and a low-stock alert routine.
"""


async def main():
    os_ = HackKnowOS()
    await os_.boot()
    result = await os_.execute(PROMPT)
    print(result.summary)
    await os_.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
