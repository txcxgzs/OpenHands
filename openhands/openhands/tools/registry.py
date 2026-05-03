"""
Tool Registry - References OpenClaw's pi-tools.ts
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
import logging
import json

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


@dataclass
class ToolResult:
    """Result from executing a tool"""
    tool_call_id: str = ""
    content: str = ""
    is_error: bool = False
    success: bool = field(init=False)
    output: str = field(init=False)
    error: str = field(init=False)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.success = not self.is_error
        self.output = self.content
        self.error = self.content if self.is_error else ""


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
        Decorator to register a tool - can be called as decorator or directly
        """
        if handler is not None:
            # Direct call
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

        # Decorator mode
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
        import inspect

        for entry in self._tools.values():
            if not entry.enabled:
                continue

            if enabled_toolsets and entry.toolset not in enabled_toolsets:
                continue
            if disabled_toolsets and entry.toolset in disabled_toolsets:
                continue
            if allowed_tools and entry.name not in allowed_tools:
                continue

            # 分析函数签名来确定必填参数
            required_params = []
            try:
                sig = inspect.signature(entry.handler)
                for name, param in sig.parameters.items():
                    # 没有默认值的参数是必填的
                    if param.default == inspect.Parameter.empty:
                        required_params.append(name)
            except:
                pass

            definition = {
                "name": entry.name,
                "description": entry.description,
                "input_schema": {
                    "type": "object",
                    "properties": entry.parameters or {},
                    "required": required_params,
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
            return ToolResult(content=f"Unknown tool: {tool_name}", is_error=True)

        if not entry.enabled:
            return ToolResult(content=f"Tool disabled: {tool_name}", is_error=True)

        try:
            # 参数验证 - 过滤无效参数
            valid_params = set(entry.parameters.keys())
            provided_params = set(arguments.keys())
            extra_params = provided_params - valid_params
            if extra_params:
                logger.warning(f"Extra parameters for {tool_name}: {extra_params}")
            
            import asyncio
            import inspect
            
            # 检查函数参数
            sig = inspect.signature(entry.handler)
            param_names = list(sig.parameters.keys())
            
            # 只传递函数接受的参数
            filtered_args = {}
            for k, v in arguments.items():
                if k in param_names:
                    filtered_args[k] = v
            
            # 执行工具
            if asyncio.iscoroutinefunction(entry.handler):
                result = await entry.handler(**filtered_args)
            else:
                result = await asyncio.to_thread(entry.handler, **filtered_args)

            if isinstance(result, str):
                content = result
            else:
                content = json.dumps(result, ensure_ascii=False, default=str)

            return ToolResult(content=content, is_error=False)

        except TypeError as e:
            # 参数错误
            logger.error(f"Parameter error for {tool_name}: {e}")
            return ToolResult(
                content=f"Parameter error for {tool_name}: {str(e)}\nExpected parameters: {list(entry.parameters.keys())}",
                is_error=True
            )
        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return ToolResult(content=f"Error executing {tool_name}: {str(e)}", is_error=True)

    async def execute_tool_call(self, tool_call) -> ToolResult:
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
