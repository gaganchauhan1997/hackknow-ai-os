"""
install.py — Python-level installer / healthcheck for HackKnow AI OS.

Run after setup.sh to verify dependencies and write any missing config defaults.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "httpx",
    "pydantic",
    "yaml",
    "loguru",
    "tenacity",
    "chromadb",
    "playwright",
    "pandas",
    "openpyxl",
]


def check_python_version() -> None:
    if sys.version_info < (3, 10):
        sys.exit("HackKnow AI OS requires Python 3.10 or newer.")


def check_packages() -> list[str]:
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    return missing


def ensure_env() -> None:
    root = Path(__file__).resolve().parent
    env = root / ".env"
    example = root / ".env.example"
    if not env.exists() and example.exists():
        env.write_text(example.read_text())
        print("  ↳ Wrote .env from .env.example")


def main() -> None:
    print("HackKnow AI OS — install / healthcheck")
    check_python_version()
    missing = check_packages()
    if missing:
        print(f"  ✗ Missing packages: {', '.join(missing)}")
        print("    Run:  pip install -r requirements.txt")
        sys.exit(1)
    ensure_env()
    print("  ✓ All checks passed.")
    print(f"  ✓ Python:   {sys.version.split()[0]}")
    print(f"  ✓ Cwd:      {os.getcwd()}")


if __name__ == "__main__":
    main()
