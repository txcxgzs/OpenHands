"""
System Tools - 系统信息和实用工具
"""

import asyncio
import logging
import platform
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register system tools"""

    @registry.register_tool(
        name="get_system_info",
        description="Get system information",
        toolset="system",
        parameters={},
    )
    async def get_system_info() -> str:
        try:
            info = []
            info.append(f"Platform: {platform.platform()}")
            info.append(f"Python: {platform.python_version()}")
            info.append(f"Architecture: {platform.machine()}")
            info.append(f"Processor: {platform.processor()}")
            
            # CPU
            try:
                import psutil
                info.append(f"CPU Count: {psutil.cpu_count()}")
                info.append(f"CPU Usage: {psutil.cpu_percent()}%")
            except:
                pass
            
            # Memory
            try:
                import psutil
                mem = psutil.virtual_memory()
                info.append(f"Memory: {mem.total / (1024**3):.1f} GB total, {mem.available / (1024**3):.1f} GB available")
            except:
                pass
            
            # Disk
            try:
                import psutil
                disk = psutil.disk_usage('/')
                info.append(f"Disk: {disk.total / (1024**3):.1f} GB total, {disk.free / (1024**3):.1f} GB free")
            except:
                pass
            
            return "\n".join(info)
        except Exception as e:
            return f"Error getting system info: {e}"

    @registry.register_tool(
        name="get_env",
        description="Get environment variable",
        toolset="system",
        parameters={
            "name": {"type": "string", "description": "Environment variable name"}
        },
    )
    async def get_env(name: str) -> str:
        try:
            value = os.environ.get(name, "")
            if value:
                return f"{name}={value}"
            else:
                return f"Environment variable '{name}' not found"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="list_env",
        description="List all environment variables",
        toolset="system",
        parameters={},
    )
    async def list_env() -> str:
        try:
            result = []
            for key, value in sorted(os.environ.items()):
                # 隐藏敏感信息
                if any(s in key.lower() for s in ['key', 'secret', 'password', 'token']):
                    result.append(f"{key}=***")
                else:
                    result.append(f"{key}={value[:100]}")
            return "\n".join(result[:50])  # 限制输出
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="get_current_dir",
        description="Get current working directory",
        toolset="system",
        parameters={},
    )
    async def get_current_dir() -> str:
        try:
            cwd = os.getcwd()
            return f"Current directory: {cwd}"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="check_path",
        description="Check if a path exists",
        toolset="system",
        parameters={
            "path": {"type": "string", "description": "Path to check"}
        },
    )
    async def check_path(path: str) -> str:
        try:
            p = Path(path)
            if p.exists():
                if p.is_dir():
                    return f"✓ Path exists: {path} (directory)"
                elif p.is_file():
                    size = p.stat().st_size
                    return f"✓ Path exists: {path} (file, {size} bytes)"
                else:
                    return f"✓ Path exists: {path}"
            else:
                return f"✗ Path does not exist: {path}"
        except Exception as e:
            return f"Error checking path: {e}"

    @registry.register_tool(
        name="get_file_info",
        description="Get file or directory information",
        toolset="system",
        parameters={
            "path": {"type": "string", "description": "Path to file or directory"}
        },
    )
    async def get_file_info(path: str) -> str:
        try:
            p = Path(path)
            if not p.exists():
                return f"Path does not exist: {path}"
            
            info = []
            info.append(f"Path: {path}")
            info.append(f"Type: {'directory' if p.is_dir() else 'file'}")
            
            stat = p.stat()
            info.append(f"Size: {stat.st_size} bytes")
            info.append(f"Modified: {stat.st_mtime}")
            
            if p.is_file():
                # 尝试读取内容预览
                try:
                    with open(p, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read(200)
                        info.append(f"Preview: {content}...")
                except:
                    pass
            
            return "\n".join(info)
        except Exception as e:
            return f"Error getting file info: {e}"

    logger.debug("System tools registered")
