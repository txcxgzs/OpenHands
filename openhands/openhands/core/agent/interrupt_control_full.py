"""
中断控制和多线程安全机制 - 100%对齐Hermes

功能：
- 中断请求机制
- 线程ID验证
- Worker线程追踪
- 进度回调
- 执行状态管理
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Any, Set, Dict
from enum import Enum

logger = logging.getLogger(__name__)


class InterruptReason(Enum):
    """中断原因"""
    USER_REQUEST = "user_request"
    TIMEOUT = "timeout"
    ERROR = "error"
    EXTERNAL_SIGNAL = "external_signal"
    TASK_COMPLETED = "task_completed"


@dataclass
class ExecutionProgress:
    """执行进度"""
    current_step: int = 0
    total_steps: int = 0
    current_tool: Optional[str] = None
    activity: str = "idle"
    last_activity_at: float = field(default_factory=time.time)
    messages_since_last_tool: int = 0


class ProgressCallback:
    """进度回调"""
    
    def __init__(self):
        self._callbacks: List[Callable[[ExecutionProgress], None]] = []
    
    def register(self, callback: Callable[[ExecutionProgress], None]):
        self._callbacks.append(callback)
    
    def unregister(self, callback: Callable[[ExecutionProgress], None]):
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def fire(self, progress: ExecutionProgress):
        for cb in self._callbacks:
            try:
                cb(progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")


class InterruptController:
    """中断控制器"""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._interrupt_requested: bool = False
        self._interrupt_reason: Optional[InterruptReason] = None
        self._interrupt_message: Optional[str] = None
        self._execution_thread_id: Optional[int] = None
        self._worker_thread_ids: Set[int] = set()
    
    def request_interrupt(
        self,
        reason: InterruptReason,
        message: Optional[str] = None,
        thread_id: Optional[int] = None
    ):
        """请求中断"""
        with self._lock:
            self._interrupt_requested = True
            self._interrupt_reason = reason
            self._interrupt_message = message
            if thread_id is not None:
                self._execution_thread_id = thread_id
            logger.info(f"Interrupt requested: {reason.value} - {message}")
    
    def clear_interrupt(self):
        """清除"""
        with self._lock:
            self._interrupt_requested = False
            self._interrupt_reason = None
            self._interrupt_message = None
            logger.info("Interrupt cleared")
    
    def is_interrupted(self) -> bool:
        """检查是否中断"""
        with self._lock:
            if not self._interrupt_requested:
                return False
            
            current_id = threading.current_thread().ident
            if current_id == self._execution_thread_id:
                return True
            if current_id in self._worker_thread_ids:
                return True
            
            return False
    
    def get_interrupt_reason(self) -> Optional[InterruptReason]:
        """获取中断原因"""
        with self._lock:
            return self._interrupt_reason
    
    def get_interrupt_message(self) -> Optional[str]:
        """获取消息"""
        with self._lock:
            return self._interrupt_message
    
    def register_worker_thread(self, thread_id: Optional[int] = None):
        """注册worker线程"""
        if thread_id is None:
            thread_id = threading.current_thread().ident
        with self._lock:
            self._worker_thread_ids.add(thread_id)
    
    def unregister_worker_thread(self, thread_id: Optional[int] = None):
        """注销"""
        if thread_id is None:
            thread_id = threading.current_thread().ident
        with self._lock:
            self._worker_thread_ids.discard(thread_id)
    
    def set_execution_thread(self, thread_id: Optional[int] = None):
        """设置执行线程"""
        if thread_id is None:
            thread_id = threading.current_thread().ident
        with self._lock:
            self._execution_thread_id = thread_id
    
    def reset(self):
        """完全重置"""
        with self._lock:
            self._interrupt_requested = False
            self._interrupt_reason = None
            self._interrupt_message = None
            self._execution_thread_id = None
            self._worker_thread_ids.clear()


class ExecutionManager:
    """执行管理器"""
    
    def __init__(self):
        self._interrupt_controller = InterruptController()
        self._progress = ExecutionProgress()
        self._progress_callbacks = ProgressCallback()
    
    @property
    def interrupt(self) -> InterruptController:
        return self._interrupt_controller
    
    @property
    def progress(self) -> ExecutionProgress:
        return self._progress
    
    def register_progress_callback(self, callback: Callable[[ExecutionProgress], None]):
        """注册"""
        self._progress_callbacks.register(callback)
    
    def unregister_progress_callback(self, callback: Callable[[ExecutionProgress], None]):
        self._progress_callbacks.unregister(callback)
    
    def notify_progress(self):
        """通知"""
        self._progress_callbacks.fire(self._progress)
    
    def update_activity(self, activity: str, tool: Optional[str] = None):
        """更新活动"""
        self._progress.activity = activity
        if tool is not None:
            self._progress.current_tool = tool
        self._progress.last_activity_at = time.time()
        self.notify_progress()
    
    def step_started(self):
        """步骤开始"""
        self._progress.current_step += 1
        self._progress.last_activity_at = time.time()
        self.notify_progress()
    
    def check_interrupt(self) -> bool:
        """检查中断"""
        return self._interrupt_controller.is_interrupted()
    
    def request_interrupt(self, reason: InterruptReason, message: str = None):
        """请求"""
        self._interrupt_controller.request_interrupt(reason, message)
    
    def clear_interrupt(self):
        """清除"""
        self._interrupt_controller.clear_interrupt()


# 全局实例
_execution_manager: Optional[ExecutionManager] = None


def get_execution_manager() -> ExecutionManager:
    """获取管理器"""
    global _execution_manager
    if _execution_manager is None:
        _execution_manager = ExecutionManager()
    return _execution_manager


def request_interrupt(reason: InterruptReason, message: Optional[str] = None):
    """请求"""
    get_execution_manager().request_interrupt(reason, message)


def is_interrupted() -> bool:
    """检查"""
    return get_execution_manager().check_interrupt()


def clear_interrupt():
    """清除"""
    get_execution_manager().clear_interrupt()
