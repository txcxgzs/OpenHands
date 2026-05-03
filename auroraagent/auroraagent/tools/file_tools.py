"""
文件工具集
参考: OpenClaw 和 Hermes Agent 的文件操作工具
"""

import asyncio
from pathlib import Path
from typing import Optional
import logging

from .registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


async def read_file_impl(path: str, limit: Optional[int] = None) -> ToolResult:
    """读取文件内容"""
    try:
        file_path = Path(path)
        if not file_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        
        if file_path.is_dir():
            return ToolResult(success=False, error=f"Path is a directory: {path}")
        
        async with asyncio.Lock():
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        
        if limit and len(content) > limit:
            content = content[:limit] + f"\n... (truncated, {len(content)} total bytes)"
        
        return ToolResult(success=True, output=content)
    except Exception as e:
        logger.exception(f"Error reading file: {path}")
        return ToolResult(success=False, error=str(e))


async def write_file_impl(path: str, content: str, append: bool = False) -> ToolResult:
    """写入文件"""
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = "a" if append else "w"
        with open(file_path, mode, encoding="utf-8") as f:
            f.write(content)
        
        action = "Appended to" if append else "Wrote"
        return ToolResult(success=True, output=f"{action} {path} ({len(content)} bytes)")
    except Exception as e:
        logger.exception(f"Error writing file: {path}")
        return ToolResult(success=False, error=str(e))


async def list_dir_impl(path: str, show_hidden: bool = False) -> ToolResult:
    """列出目录内容"""
    try:
        dir_path = Path(path)
        if not dir_path.exists():
            return ToolResult(success=False, error=f"Directory not found: {path}")
        
        if not dir_path.is_dir():
            return ToolResult(success=False, error=f"Path is not a directory: {path}")
        
        entries = []
        for item in sorted(dir_path.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            
            type_prefix = "[DIR] " if item.is_dir() else "[FILE] "
            size_str = "" if item.is_dir() else f" ({item.stat().st_size:,} bytes)"
            entries.append(f"{type_prefix}{item.name}{size_str}")
        
        output = f"Directory: {path}\n" + "\n".join(entries) if entries else "Empty directory"
        return ToolResult(success=True, output=output)
    except Exception as e:
        logger.exception(f"Error listing directory: {path}")
        return ToolResult(success=False, error=str(e))


async def delete_file_impl(path: str) -> ToolResult:
    """删除文件"""
    try:
        file_path = Path(path)
        if not file_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        
        if file_path.is_dir():
            return ToolResult(success=False, error=f"Path is a directory, use delete_dir: {path}")
        
        file_path.unlink()
        return ToolResult(success=True, output=f"Deleted: {path}")
    except Exception as e:
        logger.exception(f"Error deleting file: {path}")
        return ToolResult(success=False, error=str(e))


def check_requirements() -> bool:
    """检查工具要求"""
    return True


def register_tools(registry: ToolRegistry):
    """注册文件工具集"""
    registry.register(
        name="read_file",
        toolset="file",
        schema={
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取文件内容。支持指定最大字节数。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "文件路径",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "可选。最大读取字节数",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        handler=read_file_impl,
        check_fn=check_requirements,
        description="读取文件内容",
    )
    
    registry.register(
        name="write_file",
        toolset="file",
        schema={
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "写入或追加文件内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "文件路径",
                        },
                        "content": {
                            "type": "string",
                            "description": "要写入的内容",
                        },
                        "append": {
                            "type": "boolean",
                            "description": "是否追加模式",
                            "default": False,
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        },
        handler=write_file_impl,
        check_fn=check_requirements,
        description="写入或追加文件内容",
    )
    
    registry.register(
        name="list_dir",
        toolset="file",
        schema={
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "列出目录内容，显示文件大小。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "目录路径",
                        },
                        "show_hidden": {
                            "type": "boolean",
                            "description": "是否显示隐藏文件",
                            "default": False,
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        handler=list_dir_impl,
        check_fn=check_requirements,
        description="列出目录内容",
    )
    
    registry.register(
        name="delete_file",
        toolset="file",
        schema={
            "type": "function",
            "function": {
                "name": "delete_file",
                "description": "删除单个文件（慎用）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "文件路径",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        handler=delete_file_impl,
        check_fn=check_requirements,
        description="删除单个文件",
    )
