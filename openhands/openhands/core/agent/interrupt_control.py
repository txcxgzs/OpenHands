"""
智能体中断和并发控制系统

Hermes风格的高级控制机制：
- 中断请求机制
- 工具调用并发执行
- 执行线程管理
- 进度回调
"""

import asyncio
import logging
import threading
from typing import Optional, Callable, List, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class InterruptReason(Enum):
    """中断原因"""
    USER_REQUEST = "user_request"
    TIMEOUT = "timeout"
    ERROR = "error"
    BUDGET_EXHAUSTED = "budget_exhausted"
    EXTERNAL_SIGNAL = "external_signal"


@dataclass
class InterruptRequest:
    """中断请求"""
    reason: InterruptReason
    message: Optional[str] = None
    thread_id: Optional[int] = None


class InterruptController:
    """中断控制器 - 支持细粒度中断"""
    
    def __init__(self):
        self._interrupt_requested = False
        self._interrupt_message: Optional[str] = None
        self._execution_thread_id: Optional[int] = None
        self._worker_thread_ids: List[int] = []
        self._lock = threading.Lock()
    
    def request_interrupt(self, reason: InterruptReason, message: str = None, thread_id: int = None):
        """请求中断
        
        Args:
            reason: 中断原因
            message: 中断消息
            thread_id: 请求中断的线程ID（用于验证）
        """
        with self._lock:
            self._interrupt_requested = True
            self._interrupt_message = message
            if thread_id:
                self._execution_thread_id = thread_id
    
    def clear_interrupt(self):
        """清除中断请求"""
        with self._lock:
            self._interrupt_requested = False
            self._interrupt_message = None
    
    def is_interrupted(self) -> bool:
        """检查是否请求了中断"""
        with self._lock:
            # 从主执行线程检查
            if self._interrupt_requested:
                current_id = threading.current_thread().ident
                # 如果是主线程或注册的worker线程，允许中断
                if self._execution_thread_id is None or current_id == self._execution_thread_id:
                    return True
                # 如果是worker线程
                if current_id in self._worker_thread_ids:
                    return True
            return False
    
    def get_interrupt_message(self) -> Optional[str]:
        """获取中断消息"""
        with self._lock:
            return self._interrupt_message
    
    def register_worker(self, thread_id: int):
        """注册worker线程"""
        with self._lock:
            if thread_id not in self._worker_thread_ids:
                self._worker_thread_ids.append(thread_id)
    
    def unregister_worker(self, thread_id: int):
        """注销worker线程"""
        with self._lock:
            if thread_id in self._worker_thread_ids:
                self._worker_thread_ids.remove(thread_id)


class ToolCallResult:
    """工具调用结果"""
    def __init__(self, tool_name: str, success: bool, result: Any = None, error: str = None):
        self.tool_name = tool_name
        self.success = success
        self.result = result
        self.error = error


class ConcurrentToolExecutor:
    """并发工具执行器"""
    
    def __init__(self, max_concurrent: int = 3, interrupt_controller: InterruptController = None):
        self._max_concurrent = max_concurrent
        self._interrupt = interrupt_controller or InterruptController()
        self._executor = None
        self._active_tasks: List[asyncio.Task] = []
    
    async def execute_batch(
        self, 
        tool_calls: List[Any],
        execute_fn: Callable
    ) -> List[ToolCallResult]:
        """并发执行一批工具调用
        
        Args:
            tool_calls: 工具调用列表
            execute_fn: 执行函数，接收tool_call，返回ToolCallResult
        
        Returns:
            结果列表
        """
        if not tool_calls:
            return []
        
        # 检查中断
        if self._interrupt.is_interrupted():
            logger.info("Tool execution interrupted before start")
            return []
        
        # 创建执行任务
        tasks = []
        for tc in tool_calls:
            task = asyncio.create_task(self._execute_single(tool_call=tc, execute_fn=execute_fn))
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ToolCallResult(
                    tool_name=getattr(tool_calls[i], 'name', 'unknown'),
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_single(self, tool_call: Any, execute_fn: Callable) -> ToolCallResult:
        """执行单个工具调用"""
        try:
            # 检查中断
            if self._interrupt.is_interrupted():
                return ToolCallResult(
                    tool_name=getattr(tool_call, 'name', 'unknown'),
                    success=False,
                    error="Interrupted"
                )
            
            tool_name = getattr(tool_call, 'name', 'unknown')
            
            # 在线程池中执行（避免阻塞事件循环）
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: execute_fn(tool_call)
            )
            
            return ToolCallResult(
                tool_name=tool_name,
                success=True,
                result=result
            )
        except Exception as e:
            return ToolCallResult(
                tool_name=getattr(tool_call, 'name', 'unknown'),
                success=False,
                error=str(e)
            )


class ProgressTracker:
    """进度追踪器"""
    
    def __init__(self):
        self._callbacks: List[Callable] = []
        self._current_step: int = 0
        self._total_steps: int = 0
        self._current_tool: Optional[str] = None
        self._last_activity: float = 0
        self._activity_desc: str = "idle"
    
    def register_callback(self, callback: Callable):
        """注册进度回调"""
        self._callbacks.append(callback)
    
    def update_progress(
        self, 
        step: int = None, 
        total: int = None, 
        tool_name: str = None,
        description: str = None
    ):
        """更新进度"""
        if step is not None:
            self._current_step = step
        if total is not None:
            self._total_steps = total
        if tool_name is not None:
            self._current_tool = tool_name
        if description is not None:
            self._activity_desc = description
        
        import time
        self._last_activity = time.time()
        
        # 调用所有回调
        for callback in self._callbacks:
            try:
                callback(self.get_status())
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    def get_status(self) -> dict:
        """获取当前状态"""
        import time
        return {
            'step': self._current_step,
            'total': self._total_steps,
            'current_tool': self._current_tool,
            'description': self._activity_desc,
            'last_activity': self._last_activity,
            'idle_seconds': time.time() - self._last_activity if self._last_activity else 0
        }
    
    def tool_started(self, tool_name: str):
        """工具开始执行"""
        self.update_progress(tool_name=tool_name, description=f"执行工具: {tool_name}")
    
    def tool_completed(self, tool_name: str, success: bool = True):
        """工具执行完成"""
        self._current_step += 1
        desc = f"✓ {tool_name}" if success else f"✗ {tool_name}"
        self.update_progress(description=desc)
    
    def thinking(self):
        """AI正在思考"""
        self.update_progress(description="🧠 AI思考中...")


# 全局实例
_interrupt_controller: Optional[InterruptController] = None


def get_interrupt_controller() -> InterruptController:
    """获取中断控制器"""
    global _interrupt_controller
    if _interrupt_controller is None:
        _interrupt_controller = InterruptController()
    return _interrupt_controller


def request_interrupt(reason: InterruptReason, message: str = None):
    """请求中断"""
    import os
    get_interrupt_controller().request_interrupt(
        reason=reason, 
        message=message,
        thread_id=os.getpid()
    )


def clear_interrupt():
    """清除中断"""
    get_interrupt_controller().clear_interrupt()


def is_interrupted() -> bool:
    """检查是否中断"""
    return get_interrupt_controller().is_interrupted()
