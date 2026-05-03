"""
终端工具集
参考: OpenClaw 和 Hermes Agent 的终端执行工具
"""

import asyncio
import os
import sys
import subprocess
from typing import Optional
import logging

from .registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


async def terminal_impl(
    command: str,
    timeout: int = 30,
    background: bool = False,
    cwd: Optional[str] = None,
) -> ToolResult:
    """执行终端命令"""
    try:
        working_dir = cwd or os.getcwd()
        
        if sys.platform == "win32":
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                shell=True,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                os.environ.get("SHELL", "/bin/bash"),
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout} seconds"
            )
        
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
        
        output = []
        if stdout_str:
            output.append(f"STDOUT:\n{stdout_str}")
        if stderr_str:
            output.append(f"STDERR:\n{stderr_str}")
        
        result_output = "\n\n".join(output) if output else "(No output)"
        
        success = process.returncode == 0
        return ToolResult(
            success=success,
            output=result_output,
            error=None if success else f"Exit code {process.returncode}",
        )
    except Exception as e:
        logger.exception(f"Error executing terminal command: {command}")
        return ToolResult(success=False, error=str(e))


def check_requirements() -> bool:
    """检查工具要求"""
    return True


def register_tools(registry: ToolRegistry):
    """注册终端工具集"""
    registry.register(
        name="terminal",
        toolset="terminal",
        schema={
            "type": "function",
            "function": {
                "name": "terminal",
                "description": "执行终端命令。在 Windows 上使用 cmd，在 Linux/macOS 上使用 shell。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的命令",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "超时秒数",
                            "default": 30,
                        },
                        "background": {
                            "type": "boolean",
                            "description": "后台执行（返回后继续运行）",
                            "default": False,
                        },
                        "cwd": {
                            "type": "string",
                            "description": "工作目录",
                        },
                    },
                    "required": ["command"],
                },
            },
        },
        handler=terminal_impl,
        check_fn=check_requirements,
        description="执行终端命令",
    )
