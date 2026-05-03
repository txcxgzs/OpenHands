"""
Sandbox Tools
"""

import logging

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register sandbox tools"""

    @registry.register_tool(
        name="sandbox_exec",
        description="Execute code in sandbox",
        toolset="sandbox",
        parameters={
            "code": {"type": "string", "description": "Code to execute"},
            "language": {"type": "string", "description": "Language (python, javascript)"},
        },
    )
    async def sandbox_exec(code: str, language: str = "python") -> str:
        try:
            from auroraagent.sandbox import execute_in_sandbox, DockerSandbox

            sandbox = DockerSandbox()
            result = await execute_in_sandbox(code, language, sandbox)
            return result
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="sandbox_check",
        description="Check sandbox status",
        toolset="sandbox",
        parameters={},
    )
    async def sandbox_check() -> str:
        try:
            from auroraagent.sandbox import DockerSandbox

            sandbox = DockerSandbox()
            if sandbox._docker_available:
                return "Sandbox: Docker available, using container isolation"
            else:
                return "Sandbox: Docker not available, using fallback execution"
        except Exception as e:
            return f"Sandbox check error: {e}"

    logger.debug("Sandbox tools registered")
