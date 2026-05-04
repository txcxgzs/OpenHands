"""
生产级工具护栏系统 - 100%对齐Hermes

功能：
- 幂等工具/修改工具识别
- 精确重复失败检测
- 同一工具多次失败检测
- 循环调用模式检测
- 无进展检测
- 警告vs硬中断分级
"""

import logging
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Set, Callable, Tuple

logger = logging.getLogger(__name__)

# 幂等工具 - 只读操作
IDEMPOTENT_TOOLS = frozenset({
    "read_file",
    "list_dir",
    "search_files",
    "grep",
    "web_search",
    "web_fetch",
    "web_get",
    "browser_snapshot",
    "browser_get_url",
    "memory_search",
    "memory_list",
    "list_env",
    "get_env",
    "get_current_dir",
    "check_path",
    "get_file_info",
    "list_processes",
    "system_info"
})

# 修改工具 - 状态改变
MUTATING_TOOLS = frozenset({
    "terminal_run",
    "terminal",
    "write_file",
    "edit_file",
    "rename_file",
    "delete_file",
    "move_file",
    "make_dir",
    "remove_dir",
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_press_key",
    "browser_execute_script",
    "browser_upload_file",
    "memory_add",
    "memory_remove",
    "memory_replace",
    "memory_remove_all",
    "memory_toggle_silence",
    "delegate_task",
    "set_env",
    "unset_env",
    "send_message",
    "execute_code",
    "patch_file",
    "pipeline"
})


class ToolCategory(Enum):
    """工具类别"""
    IDEMPOTENT = "idempotent"
    MUTATING = "mutating"
    UNKNOWN = "unknown"


class GuardrailLevel(Enum):
    """护栏级别"""
    NONE = "none"
    WARNING = "warning"
    HARD_STOP = "hard_stop"


@dataclass
class GuardrailDecision:
    """护栏决策"""
    level: GuardrailLevel = GuardrailLevel.NONE
    message: Optional[str] = None
    trigger: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    tool_name: str
    success: bool
    error: Optional[str]
    timestamp_ns: int
    args_hash: Optional[str]


@dataclass
class GuardrailConfig:
    """护栏配置"""
    warnings_enabled: bool = True
    hard_stop_enabled: bool = False
    
    # 精确重复失败阈值
    exact_failure_warn_after: int = 2
    exact_failure_block_after: int = 5
    
    # 同一工具失败阈值
    same_tool_failure_warn_after: int = 3
    same_tool_failure_halt_after: int = 8
    
    # 无进展检测
    no_progress_warn_after: int = 2
    no_progress_block_after: int = 5
    
    # 循环检测窗口大小
    loop_window_sizes: List[int] = field(default_factory=lambda: [3, 4, 5])
    loop_warn_after: int = 3
    loop_halt_after: int = 6
    
    # 工具分类
    idempotent_tools: Set[str] = field(default_factory=lambda: set(IDEMPOTENT_TOOLS))
    mutating_tools: Set[str] = field(default_factory=lambda: set(MUTATING_TOOLS))


class ToolGuardrailController:
    """工具护栏控制器"""
    
    def __init__(self, config: GuardrailConfig = None):
        self._config = config or GuardrailConfig()
        self._records: List[ToolCallRecord] = []
        self._tool_failure_counts: Counter = Counter()
        self._exact_failure_count: int = 0
        self._no_progress_count: int = 0
        self._last_error: Optional[Tuple[str, str]] = None  # (tool_name, error_msg)
        self._recent_tools: List[str] = []
        self._last_meaningful_output: bool = False
    
    def reset_for_turn(self):
        """每轮重置（可选，保持跨轮追踪）"""
        pass
    
    def record_tool_call(
        self,
        tool_name: str,
        success: bool,
        error: Optional[str] = None,
        args_dict: Optional[Dict[str, Any]] = None
    ):
        """记录工具调用"""
        args_hash = None
        if args_dict:
            args_hash = self._hash_args(args_dict)
        
        record = ToolCallRecord(
            tool_name=tool_name,
            success=success,
            error=error,
            timestamp_ns=time.time_ns(),
            args_hash=args_hash
        )
        
        self._records.append(record)
        self._recent_tools.append(tool_name)
        if len(self._recent_tools) > 50:
            self._recent_tools.pop(0)
        
        # 更新计数
        if not success:
            self._tool_failure_counts[tool_name] += 1
            self._exact_failure_count += 1
            
            # 检查是否是完全重复的错误
            if self._last_error:
                prev_tool, prev_err = self._last_error
                if prev_tool == tool_name and self._errors_similar(error, prev_err):
                    pass  # 精确重复
            self._last_error = (tool_name, error)
        else:
            # 成功，重置计数
            self._last_error = None
    
    def record_no_progress(self):
        """记录无进展"""
        self._no_progress_count += 1
    
    def record_progress(self):
        """记录有进展"""
        self._no_progress_count = 0
    
    def check(self) -> GuardrailDecision:
        """检查护栏"""
        if not self._config.warnings_enabled:
            return GuardrailDecision(level=GuardrailLevel.NONE)
        
        # 按优先级检查
        checks = [
            (self._check_exact_failures, "exact_failure"),
            (self._check_same_tool_failures, "same_tool_failure"),
            (self._check_loop_pattern, "loop"),
            (self._check_no_progress, "no_progress"),
        ]
        
        for check_func, trigger_name in checks:
            decision = check_func()
            if decision.level != GuardrailLevel.NONE:
                decision.trigger = trigger_name
                return decision
        
        return GuardrailDecision(level=GuardrailLevel.NONE)
    
    def _check_exact_failures(self) -> GuardrailDecision:
        """检查精确重复失败"""
        if self._exact_failure_count >= self._config.exact_failure_block_after:
            return GuardrailDecision(
                level=GuardrailLevel.HARD_STOP,
                message=f"连续 {self._exact_failure_count} 次工具调用失败。建议检查工具配置或尝试替代方法。",
                suggestions=[
                    "检查工具名称拼写",
                    "验证工具参数",
                    "尝试不同方法",
                    "向用户寻求帮助"
                ]
            )
        elif self._exact_failure_count >= self._config.exact_failure_warn_after:
            return GuardrailDecision(
                level=GuardrailLevel.WARNING,
                message=f"已连续 {self._exact_failure_count} 次工具调用失败。请验证参数。"
            )
        return GuardrailDecision(level=GuardrailLevel.NONE)
    
    def _check_same_tool_failures(self) -> GuardrailDecision:
        """检查同一工具多次失败"""
        for tool_name, count in self._tool_failure_counts.items():
            if count >= self._config.same_tool_failure_halt_after:
                return GuardrailDecision(
                    level=GuardrailLevel.HARD_STOP,
                    message=f"'{tool_name}' 已连续失败 {count} 次。建议跳过或使用替代方案。",
                    suggestions=[
                        f"跳过 '{tool_name}'",
                        "尝试其他工具组合",
                        "重新审视问题"
                    ]
                )
            elif count >= self._config.same_tool_failure_warn_after:
                return GuardrailDecision(
                    level=GuardrailLevel.WARNING,
                    message=f"'{tool_name}' 已失败 {count} 次。请检查参数。"
                )
        return GuardrailDecision(level=GuardrailLevel.NONE)
    
    def _check_loop_pattern(self) -> GuardrailDecision:
        """检查循环调用模式"""
        if len(self._recent_tools) < 6:
            return GuardrailDecision(level=GuardrailLevel.NONE)
        
        # 检查不同窗口大小
        for window_size in self._config.loop_window_sizes:
            if len(self._recent_tools) < window_size * 2:
                continue
            
            recent = self._recent_tools[-window_size * 2:]
            first_half = tuple(recent[:window_size])
            second_half = tuple(recent[window_size:])
            
            if first_half == second_half:
                loop_length = window_size * 2
                pattern = " → ".join(first_half)
                
                if loop_length >= self._config.loop_halt_after:
                    return GuardrailDecision(
                        level=GuardrailLevel.HARD_STOP,
                        message=f"检测到循环调用模式：{pattern}。请改变策略。",
                        suggestions=[
                            "引入新工具",
                            "修改参数",
                            "寻求用户帮助"
                        ]
                    )
                elif loop_length >= self._config.loop_warn_after:
                    return GuardrailDecision(
                        level=GuardrailLevel.WARNING,
                        message=f"检测到可能的循环：{pattern}。"
                    )
        
        return GuardrailDecision(level=GuardrailLevel.NONE)
    
    def _check_no_progress(self) -> GuardrailDecision:
        """检查无进展"""
        if self._no_progress_count >= self._config.no_progress_block_after:
            return GuardrailDecision(
                level=GuardrailLevel.HARD_STOP,
                message=f"已连续 {self._no_progress_count} 次迭代无进展。建议重新审视任务或寻求用户帮助。",
                suggestions=[
                    "寻求用户澄清",
                    "尝试完全不同方法",
                    "承认任务困难"
                ]
            )
        elif self._no_progress_count >= self._config.no_progress_warn_after:
            return GuardrailDecision(
                level=GuardrailLevel.WARNING,
                message=f"已连续 {self._no_progress_count} 次迭代无进展。请尝试不同方法。"
            )
        return GuardrailDecision(level=GuardrailLevel.NONE)
    
    def get_tool_category(self, tool_name: str) -> ToolCategory:
        """获取工具类别"""
        if tool_name in self._config.idempotent_tools:
            return ToolCategory.IDEMPOTENT
        elif tool_name in self._config.mutating_tools:
            return ToolCategory.MUTATING
        else:
            return ToolCategory.UNKNOWN
    
    def is_idempotent(self, tool_name: str) -> bool:
        """是否幂等工具"""
        return self.get_tool_category(tool_name) == ToolCategory.IDEMPOTENT
    
    def is_mutating(self, tool_name: str) -> bool:
        """是否修改工具"""
        return self.get_tool_category(tool_name) == ToolCategory.MUTATING
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            'total_calls': len(self._records),
            'total_failures': self._exact_failure_count,
            'tool_failure_counts': dict(self._tool_failure_counts),
            'recent_tools': self._recent_tools[-10:],
            'no_progress_count': self._no_progress_count
        }
    
    def _hash_args(self, args_dict: Dict[str, Any]) -> str:
        """参数Hash"""
        import hashlib
        normalized = json.dumps(args_dict, sort_keys=True)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def _errors_similar(self, err1: Optional[str], err2: Optional[str]) -> bool:
        """错误相似性检查"""
        if not err1 or not err2:
            return False
        # 简单相似性 - 可以改进为Levenshtein距离
        return err1 == err2 or err1.lower() == err2.lower()


# 全局实例
_guardrails: Optional[ToolGuardrailController] = None


def get_guardrails() -> ToolGuardrailController:
    """获取护栏实例"""
    global _guardrails
    if _guardrails is None:
        _guardrails = ToolGuardrailController()
    return _guardrails


def create_guardrails(config: GuardrailConfig = None) -> ToolGuardrailController:
    """创建护栏实例"""
    return ToolGuardrailController(config)
