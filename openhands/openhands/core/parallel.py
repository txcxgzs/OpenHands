"""
Parallel Tool Execution - 并行工具执行系统
参考 Hermes Agent 的并行执行策略
"""

from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 永远不能并行的工具（交互式/面向用户）
NEVER_PARALLEL_TOOLS: Set[str] = frozenset({
    "clarify",
    "ask_user",
    "confirm",
    "request_input",
})

# 只读工具，无共享可变状态，可无条件并行
PARALLEL_SAFE_TOOLS: Set[str] = frozenset({
    "read_file",
    "search_files",
    "list_dir",
    "get_state",
    "list_entities",
    "list_services",
    "skill_view",
    "skills_list",
    "vision_analyze",
    "web_extract",
    "web_search",
    "session_search",
    "memory_search",
    "get_headers",
    "browse_web",
})

# 文件工具可并行，但需路径独立
PATH_SCOPED_TOOLS: Set[str] = frozenset({
    "read_file",
    "write_file",
    "patch",
    "delete_file",
    "copy_file",
    "move_file",
})

MAX_TOOL_WORKERS = 8


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: Dict[str, Any]
    
    def get_path_argument(self) -> Optional[str]:
        """获取路径参数"""
        for key in ["path", "file_path", "filepath", "target", "source"]:
            if key in self.arguments:
                return str(self.arguments[key])
        return None


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False
    execution_time: float = 0.0


@dataclass
class ParallelExecutionPlan:
    """并行执行计划"""
    parallel_groups: List[List[ToolCall]]
    sequential_calls: List[ToolCall]
    
    @property
    def total_calls(self) -> int:
        return sum(len(g) for g in self.parallel_groups) + len(self.sequential_calls)


class ParallelToolExecutor:
    """
    并行工具执行器
    
    特性:
    - 三类工具分类（不可并行/安全并行/路径作用域）
    - 路径重叠检测
    - 线程池并行执行
    - 结果收集和错误处理
    """
    
    def __init__(self, max_workers: int = MAX_TOOL_WORKERS):
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
    
    def _get_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._executor
    
    def should_parallelize(self, tool_calls: List[ToolCall]) -> bool:
        """判断是否应该并行执行"""
        if len(tool_calls) <= 1:
            return False
        
        for call in tool_calls:
            if call.name in NEVER_PARALLEL_TOOLS:
                return False
        
        return True
    
    def analyze_parallel_safety(self, tool_calls: List[ToolCall]) -> ParallelExecutionPlan:
        """分析并行安全性，生成执行计划"""
        if len(tool_calls) <= 1:
            return ParallelExecutionPlan(
                parallel_groups=[],
                sequential_calls=tool_calls,
            )
        
        sequential = []
        parallel_candidates = []
        
        for call in tool_calls:
            if call.name in NEVER_PARALLEL_TOOLS:
                sequential.append(call)
            else:
                parallel_candidates.append(call)
        
        if not parallel_candidates:
            return ParallelExecutionPlan(
                parallel_groups=[],
                sequential_calls=sequential,
            )
        
        safe_group = []
        path_scoped_groups: Dict[str, List[ToolCall]] = {}
        unsafe_group = []
        
        for call in parallel_candidates:
            if call.name in PARALLEL_SAFE_TOOLS:
                safe_group.append(call)
            elif call.name in PATH_SCOPED_TOOLS:
                path = call.get_path_argument()
                if path:
                    path_prefix = self._get_path_prefix(path)
                    if path_prefix not in path_scoped_groups:
                        path_scoped_groups[path_prefix] = []
                    path_scoped_groups[path_prefix].append(call)
                else:
                    unsafe_group.append(call)
            else:
                unsafe_group.append(call)
        
        parallel_groups = []
        if safe_group:
            parallel_groups.append(safe_group)
        
        for group in path_scoped_groups.values():
            if len(group) > 1 and not self._paths_overlap(group):
                parallel_groups.append(group)
            else:
                sequential.extend(group)
        
        sequential.extend(unsafe_group)
        
        return ParallelExecutionPlan(
            parallel_groups=parallel_groups,
            sequential_calls=sequential,
        )
    
    def _get_path_prefix(self, path: str) -> str:
        """获取路径前缀（用于分组）"""
        try:
            p = Path(path).resolve()
            parts = p.parts
            if len(parts) >= 3:
                return str(Path(*parts[:3]))
            return str(p.parent)
        except Exception:
            return path
    
    def _paths_overlap(self, calls: List[ToolCall]) -> bool:
        """检查路径是否重叠"""
        paths = []
        for call in calls:
            path = call.get_path_argument()
            if path:
                try:
                    paths.append(str(Path(path).resolve()))
                except Exception:
                    pass
        
        for i, p1 in enumerate(paths):
            for p2 in paths[i+1:]:
                if p1.startswith(p2) or p2.startswith(p1):
                    return True
        
        return False
    
    async def execute_parallel(
        self,
        tool_calls: List[ToolCall],
        executor: Callable[[ToolCall], Any],
    ) -> List[ToolResult]:
        """并行执行工具调用"""
        plan = self.analyze_parallel_safety(tool_calls)
        results = []
        
        for group in plan.parallel_groups:
            group_results = await self._execute_group(group, executor)
            results.extend(group_results)
        
        for call in plan.sequential_calls:
            try:
                result = await self._execute_single(call, executor)
                results.append(result)
            except Exception as e:
                results.append(ToolResult(
                    tool_call_id=call.id,
                    tool_name=call.name,
                    content=str(e),
                    is_error=True,
                ))
        
        return results
    
    async def _execute_group(
        self,
        calls: List[ToolCall],
        executor: Callable[[ToolCall], Any],
    ) -> List[ToolResult]:
        """并行执行一组工具"""
        if len(calls) == 1:
            return [await self._execute_single(calls[0], executor)]
        
        loop = asyncio.get_event_loop()
        pool = self._get_executor()
        
        futures = []
        for call in calls:
            future = loop.run_in_executor(pool, self._sync_execute, call, executor)
            futures.append(future)
        
        results = await asyncio.gather(*futures, return_exceptions=True)
        
        final_results = []
        for call, result in zip(calls, results):
            if isinstance(result, Exception):
                final_results.append(ToolResult(
                    tool_call_id=call.id,
                    tool_name=call.name,
                    content=str(result),
                    is_error=True,
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def _execute_single(
        self,
        call: ToolCall,
        executor: Callable[[ToolCall], Any],
    ) -> ToolResult:
        """执行单个工具"""
        import time
        start = time.time()
        
        try:
            if asyncio.iscoroutinefunction(executor):
                content = await executor(call)
            else:
                loop = asyncio.get_event_loop()
                content = await loop.run_in_executor(None, executor, call)
            
            return ToolResult(
                tool_call_id=call.id,
                tool_name=call.name,
                content=str(content) if content else "",
                is_error=False,
                execution_time=time.time() - start,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=call.id,
                tool_name=call.name,
                content=str(e),
                is_error=True,
                execution_time=time.time() - start,
            )
    
    def _sync_execute(
        self,
        call: ToolCall,
        executor: Callable[[ToolCall], Any],
    ) -> ToolResult:
        """同步执行（用于线程池）"""
        import asyncio
        import time
        start = time.time()
        
        try:
            result = executor(call)
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)
            
            return ToolResult(
                tool_call_id=call.id,
                tool_name=call.name,
                content=str(result) if result else "",
                is_error=False,
                execution_time=time.time() - start,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=call.id,
                tool_name=call.name,
                content=str(e),
                is_error=True,
                execution_time=time.time() - start,
            )
    
    def shutdown(self):
        """关闭执行器"""
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None


parallel_executor = ParallelToolExecutor()
