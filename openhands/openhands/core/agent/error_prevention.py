"""
错误历史和失败轨迹记录器

实现Hermes风格的犯错防止再犯机制：
1. 保存失败对话到轨迹文件
2. 记录工具调用失败历史
3. 提供基于历史的智能提示词调整
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# 失败轨迹存储路径
TRAJECTORY_DIR = Path("./data/trajectories")
FAILED_TRAJECTORIES_FILE = TRAJECTORY_DIR / "failed_trajectories.jsonl"
SUCCESS_TRAJECTORIES_FILE = TRAJECTORY_DIR / "trajectory_samples.jsonl"

# 错误模式存储
ERROR_HISTORY_FILE = TRAJECTORY_DIR / "error_history.json"

# 连续错误阈值
MAX_CONSECUTIVE_TOOL_ERRORS = 3


class ErrorHistory:
    """错误历史记录器 - 防止重复错误"""
    
    def __init__(self):
        self._tool_errors: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._session_errors: List[Dict[str, Any]] = []
        self._consecutive_tool_errors: int = 0
        self._last_error_type: Optional[str] = None
        
        # 确保目录存在
        TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)
        
        # 加载历史记录
        self._load_history()
    
    def _load_history(self):
        """加载历史错误记录"""
        try:
            if ERROR_HISTORY_FILE.exists():
                with open(ERROR_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._tool_errors = defaultdict(list, data.get('tool_errors', {}))
                    self._session_errors = data.get('session_errors', [])
        except Exception as e:
            logger.warning(f"加载错误历史失败: {e}")
    
    def _save_history(self):
        """保存错误历史"""
        try:
            data = {
                'tool_errors': dict(self._tool_errors),
                'session_errors': self._session_errors[-100:]  # 只保留最近100条
            }
            with open(ERROR_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存错误历史失败: {e}")
    
    def record_tool_error(self, tool_name: str, error: str, args: Dict[str, Any] = None):
        """记录工具调用错误"""
        self._consecutive_tool_errors += 1
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'tool': tool_name,
            'error': error[:500],  # 截断长错误
            'args': args if args else {}
        }
        
        self._tool_errors[tool_name].append(entry)
        
        # 只保留最近10次错误
        if len(self._tool_errors[tool_name]) > 10:
            self._tool_errors[tool_name] = self._tool_errors[tool_name][-10:]
        
        self._last_error_type = tool_name
        self._save_history()
    
    def record_tool_success(self, tool_name: str):
        """记录工具调用成功"""
        if self._consecutive_tool_errors > 0:
            self._consecutive_tool_errors -= 1
    
    def get_tool_error_count(self, tool_name: str) -> int:
        """获取工具的错误次数"""
        return len(self._tool_errors.get(tool_name, []))
    
    def get_recent_errors(self, tool_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取工具最近的错误"""
        return self._tool_errors.get(tool_name, [])[-limit:]
    
    def should_avoid_tool(self, tool_name: str) -> bool:
        """检查是否应该避免使用某个工具"""
        recent_errors = self.get_recent_errors(tool_name, limit=3)
        if len(recent_errors) < 2:
            return False
        
        # 如果最近3次调用都失败了，建议避免
        return len(recent_errors) >= 2
    
    def get_avoidance_guidance(self, tool_name: str) -> str:
        """获取工具使用指导（避免重复错误）"""
        recent = self.get_recent_errors(tool_name, limit=3)
        if not recent or len(recent) < 2:
            return ""
        
        # 提取常见错误模式
        error_patterns = [e['error'][:100] for e in recent]
        
        guidance = f"\n\n⚠️ 注意：{tool_name} 最近调用失败了 {len(recent)} 次\n"
        guidance += "之前的错误：\n"
        for i, pattern in enumerate(error_patterns, 1):
            guidance += f"  {i}. {pattern}\n"
        guidance += "建议：先检查问题原因，或尝试其他方法\n"
        
        return guidance
    
    def record_session_error(self, error_type: str, error: str, context: Dict[str, Any] = None):
        """记录会话级错误"""
        self._session_errors.append({
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'error': error[:500],
            'context': context or {}
        })
        self._save_history()
    
    def get_consecutive_error_count(self) -> int:
        """获取连续错误计数"""
        return self._consecutive_tool_errors
    
    def should_stop_execution(self) -> bool:
        """检查是否应该停止执行"""
        return self._consecutive_tool_errors >= MAX_CONSECUTIVE_TOOL_ERRORS
    
    def reset_consecutive_errors(self):
        """重置连续错误计数"""
        self._consecutive_tool_errors = 0


class TrajectoryRecorder:
    """轨迹记录器 - 保存成功/失败对话"""
    
    @staticmethod
    def save_trajectory(messages: List[Dict[str, Any]], model: str, completed: bool, error: str = None):
        """保存对话轨迹"""
        try:
            TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)
            
            filename = SUCCESS_TRAJECTORIES_FILE if completed else FAILED_TRAJECTORIES_FILE
            
            entry = {
                'conversations': messages,
                'timestamp': datetime.now().isoformat(),
                'model': model,
                'completed': completed,
            }
            
            if error:
                entry['error'] = error
            
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
            logger.info(f"轨迹已保存: {'成功' if completed else '失败'} -> {filename.name}")
        except Exception as e:
            logger.warning(f"保存轨迹失败: {e}")
    
    @staticmethod
    def get_failed_patterns(limit: int = 20) -> List[Dict[str, Any]]:
        """获取失败的模式（用于学习）"""
        patterns = []
        try:
            if not FAILED_TRAJECTORIES_FILE.exists():
                return patterns
            
            with open(FAILED_TRAJECTORIES_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if len(patterns) >= limit:
                        break
                    try:
                        entry = json.loads(line.strip())
                        patterns.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"读取失败轨迹失败: {e}")
        
        return patterns


class PreventionGuidance:
    """防止再犯指导生成器"""
    
    def __init__(self, error_history: ErrorHistory):
        self._error_history = error_history
    
    def get_system_guidance(self) -> str:
        """获取系统级指导（添加到系统提示词）"""
        guidance_parts = []
        
        # 检查是否有严重的工具错误历史
        for tool_name, errors in self._error_history._tool_errors.items():
            if len(errors) >= 3:
                recent_errors = errors[-3:]
                guidance_parts.append(
                    f"\n📌 重要：{tool_name} 之前调用失败过多次。"
                    f"请在调用前确认参数正确，或考虑替代方案。"
                )
        
        if guidance_parts:
            return "\n\n".join(guidance_parts) + "\n"
        return ""
    
    def get_pre_tool_guidance(self, tool_name: str) -> str:
        """获取工具调用前的指导"""
        return self._error_history.get_avoidance_guidance(tool_name)


# 全局实例
_error_history: Optional[ErrorHistory] = None


def get_error_history() -> ErrorHistory:
    """获取错误历史实例"""
    global _error_history
    if _error_history is None:
        _error_history = ErrorHistory()
    return _error_history


def get_prevention_guidance() -> PreventionGuidance:
    """获取防止再犯指导"""
    return PreventionGuidance(get_error_history())
