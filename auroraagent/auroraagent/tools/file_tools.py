
"""
File Tools - References OpenClaw's file toolset
"""

from typing import Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register file tools to registry"""

    @registry.register_tool(
        name="read_file",
        description="Read contents of a file",
        toolset="files",
        parameters={
            "path": {"type": "string", "description": "Path to file"},
        },
    )
    async def read_file(path: str) -> str:
        """Read file contents"""
        try:
            file_path = Path(path)
            if not file_path.exists():
                return f"File not found: {path}"

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            preview = content[:4000]
            if len(content) > 4000:
                preview += f"\n\n[... truncated, total {len(content)} characters]"

            return preview
        except Exception as e:
            logger.exception(f"Error reading file: {path}")
            return f"Error reading file: {e}"

    @registry.register_tool(
        name="write_file",
        description="Write contents to a file",
        toolset="files",
        parameters={
            "path": {"type": "string", "description": "Path to file"},
            "content": {"type": "string", "description": "Content to write"},
        },
    )
    async def write_file(path: str, content: str) -> str:
        """Write content to file"""
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Wrote {len(content)} characters to {path}"
        except Exception as e:
            logger.exception(f"Error writing file: {path}")
            return f"Error writing file: {e}"

    @registry.register_tool(
        name="list_dir",
        description="List directory contents",
        toolset="files",
        parameters={
            "path": {"type": "string", "description": "Directory path"},
        },
    )
    async def list_dir(path: str = ".") -> str:
        """List directory contents"""
        try:
            dir_path = Path(path)
            if not dir_path.exists():
                return f"Directory not found: {path}"

            entries = list(dir_path.iterdir())
            result = []

            for entry in sorted(entries):
                prefix = "[DIR]  " if entry.is_dir() else "[FILE] "
                result.append(f"{prefix}{entry.name}")

            return "\n".join(result)
        except Exception as e:
            logger.exception(f"Error listing directory: {path}")
            return f"Error listing directory: {e}"

    logger.debug("File tools registered")
