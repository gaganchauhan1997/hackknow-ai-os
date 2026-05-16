"""
Shop ops demo — list low-stock items on shop.hackknow.com.
Usage:
    python demos/shop_ops_demo.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orchestrator import HackKnowOS  # noqa: E402


async def main():
    os_ = HackKnowOS()
    await os_.boot()
    out = await os_.delegate("ecommerce", {"task": "check low stock items and summarise"})
    print(out)
    await os_.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
