
"""
Tool Registry System - Reference to OpenClaw's pi-tools.ts
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import json
import logging
import asyncio
from ..types import ToolCall, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ToolEntry:
    """Tool registry entry"""
    name: str
    description: str
    handler: Callable
    toolset: str = "default"
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class ToolRegistry:
    """
    Central tool registry - References OpenClaw's tool catalog
    """

    def __init__(self):
        self._tools: Dict[str, ToolEntry] = {}
        self._toolsets: Dict[str, List[str]] = {}
        self._cache: Dict[str, Any] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Optional[Callable] = None,
        toolset: str = "default",
        parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Callable:
        """
        Decorator to register a tool
        """
        def decorator(func: Callable) -> Callable:
            entry = ToolEntry(
                name=name,
                description=description,
                handler=func,
                toolset=toolset,
                parameters=parameters or {},
                metadata=metadata or {},
            )
            self._tools[name] = entry

            if toolset not in self._toolsets:
                self._toolsets[toolset] = []
            self._toolsets[toolset].append(name)

            logger.debug(f"Registered tool: {name} ({toolset})")
            return func

        if handler:
            entry = ToolEntry(
                name=name,
                description=description,
                handler=handler,
                toolset=toolset,
                parameters=parameters or {},
                metadata=metadata or {},
            )
            self._tools[name] = entry

            if toolset not in self._toolsets:
                self._toolsets[toolset] = []
            self._toolsets[toolset].append(name)
            logger.debug(f"Registered tool: {name} ({toolset})")
            return handler
            
        return decorator

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        return self._tools.get(name)

    def list_tools(
        self,
        toolset: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[ToolEntry]:
        tools = list(self._tools.values())
        if toolset:
            tools = [t for t in tools if t.toolset == toolset]
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    def list_toolsets(self) -> List[str]:
        return list(self._toolsets.keys())

    def get_definitions(
        self,
        enabled_toolsets: Optional[set] = None,
        disabled_toolsets: Optional[set] = None,
        allowed_tools: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get tool definitions in OpenAI/Anthropic format
        """
        definitions = []

        for entry in self._tools.values():
            if not entry.enabled:
                continue

            if enabled_toolsets and entry.toolset not in enabled_toolsets:
                continue
            if disabled_toolsets and entry.toolset in disabled_toolsets:
                continue
            if allowed_tools and entry.name not in allowed_tools:
                continue

            definition = {
                "name": entry.name,
                "description": entry.description,
                "input_schema": {
                    "type": "object",
                    "properties": entry.parameters or {},
                    "required": [],
                },
            }
            definitions.append(definition)

        return definitions

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> ToolResult:
        """Execute a tool"""
        entry = self.get_tool(tool_name)
        if not entry:
            return ToolResult(
                tool_call_id="",
                content=f"Unknown tool: {tool_name}",
                is_error=True,
            )

        try:
            if asyncio.iscoroutinefunction(entry.handler):
                result = await entry.handler(**arguments)
            else:
                result = await asyncio.to_thread(entry.handler, **arguments)

            if isinstance(result, str):
                content = result
            else:
                content = json.dumps(result, ensure_ascii=False, default=str)

            return ToolResult(
                tool_call_id="",
                content=content,
                is_error=False,
            )

        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return ToolResult(
                tool_call_id="",
                content=f"Error executing {tool_name}: {str(e)}",
                is_error=True,
            )

    async def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call from model"""
        result = await self.execute_tool(tool_call.name, tool_call.arguments)
        result.tool_call_id = tool_call.id
        return result

    def enable_tool(self, name: str):
        if name in self._tools:
            self._tools[name].enabled = True

    def disable_tool(self, name: str):
        if name in self._tools:
            self._tools[name].enabled = False


_global_registry: Optional[ToolRegistry] = None


def tool_registry() -> ToolRegistry:
    """Get global tool registry singleton"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry
