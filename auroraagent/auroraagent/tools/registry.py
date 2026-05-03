"""
AuroraAgent 工具注册表
参考: OpenClaw Tool Registry, Hermes Agent Tool Registry
"""

import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    raw_data: Optional[Any] = None


@dataclass
class ToolEntry:
    """工具元数据条目"""
    __slots__ = (
        "name", "toolset", "schema", "handler", "check_fn",
        "requires_env", "is_async", "description",
        "max_result_size_chars",
    )
    
    name: str
    toolset: str
    schema: dict
    handler: Callable
    check_fn: Optional[Callable] = None
    requires_env: Optional[List[str]] = None
    is_async: bool = True
    description: str = ""
    max_result_size_chars: int = 10000


class ToolRegistry:
    """
    线程安全的工具注册表 - 单例模式
    深度参考: Hermes Agent ToolRegistry
    """
    
    _instance: Optional["ToolRegistry"] = None
    _lock: threading.RLock = threading.RLock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._tools: Dict[str, ToolEntry] = {}
        self._toolset_checks: Dict[str, Callable] = {}
        self._lock = threading.RLock()
        self._generation: int = 0
        self._initialized = True
    
    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Optional[Callable] = None,
        requires_env: Optional[List[str]] = None,
        is_async: bool = True,
        description: str = "",
        max_result_size_chars: int = 10000,
    ) -> None:
        """
        注册新工具
        
        Args:
            name: 工具名称
            toolset: 工具集名称
            schema: JSON Schema 工具定义
            handler: 执行函数
            check_fn: 可用性检查函数
            requires_env: 所需环境变量
            is_async: 是否异步
            description: 描述
            max_result_size_chars: 结果最大字符数
        """
        entry = ToolEntry(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env,
            is_async=is_async,
            description=description,
            max_result_size_chars=max_result_size_chars,
        )
        
        with self._lock:
            self._tools[name] = entry
            self._generation += 1
            logger.debug(f"Registered tool: {name} (toolset: {toolset})")
    
    def unregister(self, name: str) -> bool:
        """取消注册工具"""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                self._generation += 1
                logger.debug(f"Unregistered tool: {name}")
                return True
            return False
    
    def get(self, name: str) -> Optional[ToolEntry]:
        """获取工具条目"""
        with self._lock:
            return self._tools.get(name)
    
    def get_definitions(
        self,
        enabled_toolsets: Optional[Set[str]] = None,
        disabled_toolsets: Optional[Set[str]] = None,
        include_unavailable: bool = False,
    ) -> List[dict]:
        """
        获取可用工具定义列表
        
        Args:
            enabled_toolsets: 启用的工具集
            disabled_toolsets: 禁用的工具集
            include_unavailable: 是否包含不可用工具
        
        Returns:
            工具定义列表
        """
        with self._lock:
            entries = list(self._tools.values())
        
        definitions = []
        for entry in entries:
            # 工具集过滤
            if enabled_toolsets and entry.toolset not in enabled_toolsets:
                continue
            if disabled_toolsets and entry.toolset in disabled_toolsets:
                continue
            
            # 可用性检查
            if not include_unavailable:
                if entry.check_fn and not _check_fn_cached(entry.check_fn):
                    continue
                if entry.requires_env:
                    missing = [env for env in entry.requires_env if not os.getenv(env)]
                    if missing:
                        logger.debug(f"Tool {entry.name} skipped: missing env {missing}")
                        continue
            
            definitions.append(entry.schema)
        
        return definitions
    
    def list_tools(self) -> List[str]:
        """列出所有已注册工具"""
        with self._lock:
            return list(self._tools.keys())
    
    def list_toolsets(self) -> Set[str]:
        """列出所有工具集"""
        with self._lock:
            return {entry.toolset for entry in self._tools.values()}
    
    async def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> ToolResult:
        """
        执行工具
        
        Args:
            name: 工具名称
            arguments: 参数字典
        
        Returns:
            工具执行结果
        """
        entry = self.get(name)
        
        if entry is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {name}"
            )
        
        # 可用性检查
        if entry.check_fn and not _check_fn_cached(entry.check_fn):
            return ToolResult(
                success=False,
                error=f"Tool {name} is currently unavailable"
            )
        
        try:
            if entry.is_async:
                result = await entry.handler(**arguments)
            else:
                result = entry.handler(**arguments)
            
            if isinstance(result, ToolResult):
                return result
            elif isinstance(result, str):
                return ToolResult(success=True, output=result)
            else:
                return ToolResult(success=True, output=str(result), raw_data=result)
        
        except Exception as e:
            logger.exception(f"Tool execution failed: {name}")
            return ToolResult(
                success=False,
                error=f"Tool {name} failed: {str(e)}"
            )
    
    def clear(self) -> None:
        """清空注册表"""
        with self._lock:
            self._tools.clear()
            self._generation += 1
            logger.info("Tool registry cleared")


import os
import time

# 工具可用性检查缓存
_CHECK_FN_TTL_SECONDS = 30.0
_check_fn_cache: Dict[Callable, tuple[float, bool]] = {}
_check_fn_cache_lock = threading.RLock()


def _check_fn_cached(fn: Callable) -> bool:
    """TTL 缓存的工具可用性检查"""
    now = time.monotonic()
    
    with _check_fn_cache_lock:
        cached = _check_fn_cache.get(fn)
        if cached:
            ts, value = cached
            if now - ts < _CHECK_FN_TTL_SECONDS:
                return value
    
    try:
        value = bool(fn())
    except Exception:
        value = False
    
    with _check_fn_cache_lock:
        _check_fn_cache[fn] = (now, value)
    
    return value


def tool_registry() -> ToolRegistry:
    """获取注册表单例"""
    return ToolRegistry()
