
"""
Terminal Tools - References OpenClaw's terminal toolset
"""

import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register terminal tools to registry"""

    @registry.register_tool(
        name="terminal_run",
        description="Run a terminal command",
        toolset="terminal",
        parameters={
            "command": {"type": "string", "description": "Command to run"},
            "timeout": {"type": "number", "description": "Timeout in seconds"},
        },
    )
    async def terminal_run(
        command: str,
        timeout: float = 60.0,
    ) -> str:
        """Run a terminal command"""
        try:
            logger.info(f"Running command: {command}")

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return f"Command timed out after {timeout}s"

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            output = []
            if stdout_str:
                output.append(f"STDOUT:\n{stdout_str}")
            if stderr_str:
                output.append(f"STDERR:\n{stderr_str}")
            output.append(f"EXIT CODE: {proc.returncode}")

            return "\n\n".join(output)
        except Exception as e:
            logger.exception(f"Error running command: {command}")
            return f"Error running command: {e}"

    logger.debug("Terminal tools registered")
