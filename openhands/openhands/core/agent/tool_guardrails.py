"""
工具调用护栏系统

Hermes风格的工具调用安全监控：
- 检测循环调用模式
- 检测失败模式
- 幂等性识别
- 可选的中断机制
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from collections import Counter
from enum import Enum

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """工具类别"""
    IDEMPOTENT = "idempotent"  # 只读工具
    MUTATING = "mutating"      # 修改性工具
    UNKNOWN = "unknown"


# 幂等性工具集合（只读操作）
IDEMPOTENT_TOOLS = frozenset({
    "read_file",
    "list_dir",
    "search_files",
    "web_search",
    "web_fetch",
    "browser_snapshot",
    "memory_search",
    "memory_list",
    "session_status",
    "get_file_info",
    "check_path",
})

# 修改性工具集合
MUTATING_TOOLS = frozenset({
    "terminal_run",
    "write_file",
    "edit_file",
    "delete_file",
    "terminal",
    "execute_code",
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_press",
    "memory_add",
    "delegate_task",
    "send_message",
})


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    tool_name: str
    success: bool
    error: Optional[str] = None
    timestamp: float = 0


@dataclass
class GuardrailDecision:
    """护栏决策"""
    should_warn: bool = False
    should_halt: bool = False
    warning_message: Optional[str] = None
    halt_message: Optional[str] = None


@dataclass
class ToolGuardrailConfig:
    """护栏配置"""
    warnings_enabled: bool = True
    hard_stop_enabled: bool = False
    
    # 失败检测阈值
    exact_failure_warn_after: int = 2
    exact_failure_block_after: int = 5
    
    # 同一工具失败检测
    same_tool_failure_warn_after: int = 3
    same_tool_failure_halt_after: int = 8
    
    # 无进展检测
    no_progress_warn_after: int = 2
    no_progress_block_after: int = 5
    
    # 循环检测
    loop_warn_after: int = 3
    loop_halt_after: int = 6
    
    # 幂等性工具集合
    idempotent_tools: frozenset = field(default_factory=lambda: IDEMPOTENT_TOOLS)
    mutating_tools: frozenset = field(default_factory=lambda: MUTATING_TOOLS)


class ToolGuardrailController:
    """工具调用护栏控制器"""
    
    def __init__(self, config: ToolGuardrailConfig = None):
        self._config = config or ToolGuardrailConfig()
        self._reset()
    
    def _reset(self):
        """重置状态"""
        self._records: List[ToolCallRecord] = []
        self._tool_failure_counts: Counter = Counter()
        self._exact_failure_count = 0
        self._no_progress_count = 0
        self._recent_tools: List[str] = []
        self._last_meaningful_output = False
    
    def reset_for_turn(self):
        """每轮重置（可选）"""
        pass  # 保持跨轮追踪
    
    def record_tool_call(self, tool_name: str, success: bool, error: str = None):
        """记录工具调用"""
        import time
        record = ToolCallRecord(
            tool_name=tool_name,
            success=success,
            error=error,
            timestamp=time.time()
        )
        self._records.append(record)
        
        # 更新统计
        self._recent_tools.append(tool_name)
        if len(self._recent_tools) > 20:
            self._recent_tools.pop(0)
        
        if not success:
            self._tool_failure_counts[tool_name] += 1
            self._exact_failure_count += 1
        else:
            # 重置无进展计数
            self._no_progress_count = 0
    
    def check(self) -> GuardrailDecision:
        """检查是否触发护栏"""
        decision = GuardrailDecision()
        
        if not self._config.warnings_enabled:
            return decision
        
        # 检查精确重复失败
        decision = self._check_exact_failures(decision)
        
        # 检查同一工具多次失败
        decision = self._check_same_tool_failures(decision)
        
        # 检查循环模式
        decision = self._check_loop_pattern(decision)
        
        # 检查无进展
        decision = self._check_no_progress(decision)
        
        # 检查硬停止
        if self._config.hard_stop_enabled:
            if decision.should_halt:
                logger.warning(f"Tool guardrail halting: {decision.halt_message}")
        
        return decision
    
    def _check_exact_failures(self, decision: GuardrailDecision) -> GuardrailDecision:
        """检查连续精确失败"""
        if self._exact_failure_count >= self._config.exact_failure_block_after:
            decision.should_halt = True
            decision.halt_message = (
                f"连续 {self._exact_failure_count} 次工具调用失败。"
                "建议检查工具配置或尝试其他方法。"
            )
        elif self._exact_failure_count >= self._config.exact_failure_warn_after:
            decision.should_warn = True
            decision.warning_message = (
                f"连续 {self._exact_failure_count} 次工具调用失败。"
                "请检查问题原因。"
            )
        return decision
    
    def _check_same_tool_failures(self, decision: GuardrailDecision) -> GuardrailDecision:
        """检查同一工具多次失败"""
        for tool_name, count in self._tool_failure_counts.items():
            if count >= self._config.same_tool_failure_halt_after:
                decision.should_halt = True
                decision.halt_message = (
                    f"'{tool_name}' 已连续失败 {count} 次。"
                    "建议跳过此工具或使用替代方案。"
                )
                break
            elif count >= self._config.same_tool_failure_warn_after:
                decision.should_warn = True
                decision.warning_message = (
                    f"'{tool_name}' 已失败 {count} 次。"
                    "请确认参数正确。"
                )
        return decision
    
    def _check_loop_pattern(self, decision: GuardrailDecision) -> GuardrailDecision:
        """检查循环调用模式"""
        if len(self._recent_tools) < 4:
            return decision
        
        # 检查最后N个工具是否形成循环
        for window_size in [3, 4, 5]:
            if len(self._recent_tools) < window_size * 2:
                continue
            
            recent = self._recent_tools[-window_size*2:]
            first_half = tuple(recent[:window_size])
            second_half = tuple(recent[window_size:])
            
            if first_half == second_half:
                loop_count = window_size * 2
                if loop_count >= self._config.loop_halt_after:
                    decision.should_halt = True
                    decision.halt_message = (
                        f"检测到循环调用模式: {' -> '.join(first_half)}。"
                        "请改变策略。"
                    )
                elif loop_count >= self._config.loop_warn_after:
                    decision.should_warn = True
                    decision.warning_message = (
                        f"检测到可能的循环: {' -> '.join(first_half)}。"
                    )
                break
        
        return decision
    
    def _check_no_progress(self, decision: GuardrailDecision) -> GuardrailDecision:
        """检查无进展"""
        if self._no_progress_count >= self._config.no_progress_block_after:
            decision.should_halt = True
            decision.halt_message = (
                f"连续 {self._no_progress_count} 次迭代无进展。"
                "建议重新审视任务或寻求用户帮助。"
            )
        elif self._no_progress_count >= self._config.no_progress_warn_after:
            decision.should_warn = True
            decision.warning_message = (
                f"连续 {self._no_progress_count} 次迭代无进展。"
                "请尝试不同方法。"
            )
        return decision
    
    def increment_no_progress(self):
        """增加无进展计数"""
        self._no_progress_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_calls': len(self._records),
            'total_failures': self._exact_failure_count,
            'tool_failure_counts': dict(self._tool_failure_counts),
            'recent_tools': self._recent_tools[-10:],
            'no_progress_count': self._no_progress_count,
        }
    
    def is_idempotent(self, tool_name: str) -> bool:
        """检查工具是否是幂等的"""
        return tool_name in self._config.idempotent_tools
    
    def is_mutating(self, tool_name: str) -> bool:
        """检查工具是否修改状态"""
        return tool_name in self._config.mutating_tools
    
    def get_category(self, tool_name: str) -> ToolCategory:
        """获取工具类别"""
        if self.is_idempotent(tool_name):
            return ToolCategory.IDEMPOTENT
        elif self.is_mutating(tool_name):
            return ToolCategory.MUTATING
        else:
            return ToolCategory.UNKNOWN
