"""
Sandbox System - Docker isolation
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Sandbox configuration"""
    image: str = "python:3.11-slim"
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    timeout: int = 60
    network_enabled: bool = False
    read_only_root: bool = True


class DockerSandbox:
    """
    Docker-based sandbox for tool execution
    References OpenClaw's Docker isolation
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        try:
            import docker
            client = docker.from_env()
            client.ping()
            return True
        except Exception:
            return False

    async def execute(
        self,
        code: str,
        language: str = "python",
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute code in sandbox"""
        if not self._docker_available:
            return await self._execute_fallback(code, language, **kwargs)

        try:
            import docker
            client = docker.from_env()

            command = self._get_command(code, language)

            container = client.containers.run(
                self.config.image,
                command=command,
                mem_limit=self.config.memory_limit,
                cpu_period=100000,
                cpu_quota=int(self.config.cpu_limit * 100000),
                network_disabled=not self.config.network_enabled,
                read_only=self.config.read_only_root,
                detach=True,
                stdout=True,
                stderr=True,
            )

            try:
                result = container.wait(timeout=self.config.timeout)
                logs = container.logs().decode("utf-8")
                container.remove(force=True)

                return {
                    "success": result["StatusCode"] == 0,
                    "output": logs,
                    "exit_code": result["StatusCode"],
                }
            except Exception as e:
                container.remove(force=True)
                return {"success": False, "error": str(e)}

        except Exception as e:
            logger.error(f"Docker execution failed: {e}")
            return await self._execute_fallback(code, language, **kwargs)

    async def _execute_fallback(
        self,
        code: str,
        language: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Fallback execution without Docker"""
        logger.info("Using fallback execution (no Docker)")

        if language == "python":
            try:
                import sys
                from io import StringIO

                old_stdout = sys.stdout
                sys.stdout = StringIO()

                exec_globals = {"__builtins__": __builtins__}
                exec(code, exec_globals)

                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

                return {"success": True, "output": output, "exit_code": 0}
            except Exception as e:
                return {"success": False, "error": str(e), "exit_code": 1}

        elif language == "javascript":
            try:
                import subprocess
                result = subprocess.run(
                    ["node", "-e", code],
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout,
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr,
                    "exit_code": result.returncode,
                }
            except Exception as e:
                return {"success": False, "error": str(e), "exit_code": 1}

        return {"success": False, "error": f"Unsupported language: {language}"}

    def _get_command(self, code: str, language: str) -> str:
        if language == "python":
            import base64
            encoded = base64.b64encode(code.encode()).decode()
            return f"python3 -c \"import base64; exec(base64.b64decode('{encoded}').decode())\""
        elif language == "javascript":
            return f"node -e \"{code.replace('\"', '\\\\\"')}\""
        return f"echo '{code}'"


async def execute_in_sandbox(
    code: str,
    language: str = "python",
    sandbox: Optional[DockerSandbox] = None,
) -> str:
    """Execute code and return output string"""
    if sandbox is None:
        sandbox = DockerSandbox()

    result = await sandbox.execute(code, language)

    if result["success"]:
        return result.get("output", "")
    else:
        return f"Error: {result.get('error', 'Unknown error')}"
