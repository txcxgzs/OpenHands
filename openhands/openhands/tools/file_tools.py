
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
            "file_path": {"type": "string", "description": "Path to file"},
        },
    )
    async def read_file(file_path: str) -> str:
        """Read file contents"""
        try:
            path = Path(file_path)
            if not path.exists():
                return f"File not found: {file_path}"

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            preview = content[:4000]
            if len(content) > 4000:
                preview += f"\n\n[... truncated, total {len(content)} characters]"

            return preview
        except Exception as e:
            logger.exception(f"Error reading file: {file_path}")
            return f"Error reading file: {e}"

    @registry.register_tool(
        name="write_file",
        description="Write contents to a file",
        toolset="files",
        parameters={
            "file_path": {"type": "string", "description": "Path to file"},
            "content": {"type": "string", "description": "Content to write"},
        },
    )
    async def write_file(file_path: str, content: str) -> str:
        """Write content to file"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Wrote {len(content)} characters to {file_path}"
        except Exception as e:
            logger.exception(f"Error writing file: {file_path}")
            return f"Error writing file: {e}"

    @registry.register_tool(
        name="list_dir",
        description="List directory contents",
        toolset="files",
        parameters={
            "dir_path": {"type": "string", "description": "Directory path"},
        },
    )
    async def list_dir(dir_path: str = ".") -> str:
        """List directory contents"""
        try:
            path = Path(dir_path)
            if not path.exists():
                return f"Directory not found: {dir_path}"

            entries = list(path.iterdir())
            result = []

            for entry in sorted(entries):
                prefix = "[DIR]  " if entry.is_dir() else "[FILE] "
                result.append(f"{prefix}{entry.name}")

            return "\n".join(result)
        except Exception as e:
            logger.exception(f"Error listing directory: {dir_path}")
            return f"Error listing directory: {e}"

    @registry.register_tool(
        name="edit_file",
        description="Edit file by replacing text",
        toolset="files",
        parameters={
            "file_path": {"type": "string", "description": "Path to file"},
            "old_string": {"type": "string", "description": "Text to find and replace"},
            "new_string": {"type": "string", "description": "Replacement text"},
        },
    )
    async def edit_file(file_path: str, old_string: str, new_string: str) -> str:
        """Edit file by replacing text"""
        try:
            path = Path(file_path)
            if not path.exists():
                return f"File not found: {file_path}"

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if old_string not in content:
                return f"Error: old_string not found in file"

            new_content = content.replace(old_string, new_string)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Edited {file_path}: replaced {len(old_string)} chars with {len(new_string)} chars"
        except Exception as e:
            logger.exception(f"Error editing file: {file_path}")
            return f"Error editing file: {e}"

    logger.debug("File tools registered")
