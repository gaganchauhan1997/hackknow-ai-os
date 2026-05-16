"""
Code execution skill — sandboxed Python (and shell) execution.

Inspired by:
  - https://github.com/OpenInterpreter/open-interpreter

Uses a subprocess sandbox with a configurable timeout. Returns stdout/stderr.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from core.logger import get_logger

log = get_logger("skill:code_exec")

manifest = {
    "description": "Execute Python or shell code in a subprocess sandbox with a timeout. Returns stdout, stderr, exit_code.",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "language": {"type": "string", "enum": ["python", "bash"]},
            "timeout": {"type": "integer"},
        },
        "required": ["code"],
    },
}


async def run(code: str, language: str = "python", timeout: int = 30) -> dict:
    suffix = ".py" if language == "python" else ".sh"
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as f:
        f.write(code)
        path = Path(f.name)
    cmd = ["python3", str(path)] if language == "python" else ["bash", str(path)]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "stdout": stdout.decode("utf-8", "replace"),
            "stderr": stderr.decode("utf-8", "replace"),
            "exit_code": proc.returncode,
        }
    except asyncio.TimeoutError:
        return {"stdout": "", "stderr": f"timeout after {timeout}s", "exit_code": -1}
    finally:
        path.unlink(missing_ok=True)
