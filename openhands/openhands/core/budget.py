"""
IterationBudget - 迭代预算系统
参考 Hermes Agent 的迭代预算机制
"""

from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class BudgetStats:
    total_used: int = 0
    refunded: int = 0
    overflows: int = 0
    last_consume_time: Optional[datetime] = None
    last_refund_time: Optional[datetime] = None


class IterationBudget:
    """
    线程安全的迭代计数器
    
    特性:
    - 父 Agent 默认 90 次迭代上限
    - 子 Agent 独立预算（默认 50 次）
    - execute_code 迭代可退款
    - 线程安全保证并行工具调用时的计数准确性
    """
    
    DEFAULT_MAX_ITERATIONS = 90
    CHILD_MAX_ITERATIONS = 50
    
    def __init__(self, max_total: int = DEFAULT_MAX_ITERATIONS, parent: Optional["IterationBudget"] = None):
        self.max_total = max_total
        self.parent = parent
        self._used = 0
        self._lock = threading.Lock()
        self._stats = BudgetStats()
        self._on_exhausted: Optional[Callable] = None
        self._refund_enabled = True
    
    def consume(self) -> bool:
        """消费一次迭代，返回是否成功"""
        with self._lock:
            if self._used >= self.max_total:
                self._stats.overflows += 1
                logger.debug(f"Budget exhausted: {self._used}/{self.max_total}")
                if self._on_exhausted:
                    self._on_exhausted()
                return False
            self._used += 1
            self._stats.total_used += 1
            self._stats.last_consume_time = datetime.now()
            return True
    
    def refund(self) -> bool:
        """退还一次迭代（用于代码执行等无需实际消耗的场景）"""
        if not self._refund_enabled:
            return False
        
        with self._lock:
            if self._used > 0:
                self._used -= 1
                self._stats.refunded += 1
                self._stats.last_refund_time = datetime.now()
                logger.debug(f"Budget refunded: {self._used}/{self.max_total}")
                return True
            return False
    
    @property
    def remaining(self) -> int:
        """剩余迭代次数"""
        with self._lock:
            return self.max_total - self._used
    
    @property
    def used(self) -> int:
        """已使用迭代次数"""
        with self._lock:
            return self._used
    
    @property
    def exhausted(self) -> bool:
        """是否已耗尽"""
        with self._lock:
            return self._used >= self.max_total
    
    @property
    def usage_ratio(self) -> float:
        """使用率"""
        with self._lock:
            return self._used / self.max_total if self.max_total > 0 else 0.0
    
    def reset(self):
        """重置预算"""
        with self._lock:
            self._used = 0
            self._stats = BudgetStats()
    
    def set_on_exhausted(self, callback: Callable):
        """设置耗尽回调"""
        self._on_exhausted = callback
    
    def disable_refund(self):
        """禁用退款"""
        self._refund_enabled = False
    
    def enable_refund(self):
        """启用退款"""
        self._refund_enabled = True
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            return {
                "max_total": self.max_total,
                "used": self._used,
                "remaining": self.remaining,
                "refunded": self._stats.refunded,
                "overflows": self._stats.overflows,
                "usage_ratio": self.usage_ratio,
            }
    
    def create_child(self, max_total: int = CHILD_MAX_ITERATIONS) -> "IterationBudget":
        """创建子预算"""
        child = IterationBudget(max_total=max_total, parent=self)
        return child
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def __repr__(self) -> str:
        return f"IterationBudget(used={self._used}/{self.max_total})"


class BudgetManager:
    """预算管理器 - 管理多个预算实例"""
    
    def __init__(self):
        self._budgets: dict[str, IterationBudget] = {}
        self._lock = threading.Lock()
    
    def create(self, name: str, max_total: int = IterationBudget.DEFAULT_MAX_ITERATIONS) -> IterationBudget:
        """创建命名预算"""
        with self._lock:
            budget = IterationBudget(max_total=max_total)
            self._budgets[name] = budget
            return budget
    
    def get(self, name: str) -> Optional[IterationBudget]:
        """获取预算"""
        with self._lock:
            return self._budgets.get(name)
    
    def remove(self, name: str) -> bool:
        """移除预算"""
        with self._lock:
            if name in self._budgets:
                del self._budgets[name]
                return True
            return False
    
    def get_all_stats(self) -> dict[str, dict]:
        """获取所有预算统计"""
        with self._lock:
            return {name: budget.get_stats() for name, budget in self._budgets.items()}


budget_manager = BudgetManager()
