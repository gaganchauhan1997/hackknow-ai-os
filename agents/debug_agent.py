"""Debug Agent — reads error logs / tracebacks, proposes fixes, runs verification."""

from agents.base import BaseAgent


class DebugAgent(BaseAgent):
    role_blurb = (
        "Senior debugger. Reads stack traces and failing tests, isolates root cause, "
        "proposes minimal diffs, and runs the verification step in the code_exec sandbox."
    )

    async def run(self, instruction: str, context=None):  # type: ignore[override]
        context = context or {}
        if "stack" in instruction.lower() or "traceback" in instruction.lower() or "error" in instruction.lower():
            instruction = (
                instruction
                + "\n\nProduce: (1) likely root cause, (2) minimal patch in unified-diff format, "
                "(3) a verification command. Be terse."
            )
        return await super().run(instruction, context)
