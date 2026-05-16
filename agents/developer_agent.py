"""Developer Agent — open-interpreter-style coding assistant."""

from agents.base import BaseAgent


class DeveloperAgent(BaseAgent):
    role_blurb = (
        "Senior developer. Produces production-ready code, tests, and runs it "
        "via the sandboxed code_exec skill when needed."
    )

    async def run(self, instruction: str, context=None) -> str:
        context = context or {}
        if any(word in instruction.lower() for word in ("run ", "execute", "test it")):
            # Generate the code first, then execute
            code = await super().run(
                f"Produce ONLY the Python code needed for: {instruction}",
                context,
            )
            exec_out = await self.use_skill("code_exec", code=code, language="python")
            return f"Code produced:\n```python\n{code}\n```\n\nExecution result:\n{exec_out}"
        return await super().run(instruction, context)
