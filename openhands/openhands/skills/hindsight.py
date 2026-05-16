"""
Hindsight Experience Replay - 失败轨迹回收
参考 AgentHER (arXiv 2603.21357)
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """失败类型"""
    ENVIRONMENT_ERROR = "environment_error"
    KNOWLEDGE_GAP = "knowledge_gap"
    STRATEGY_ERROR = "strategy_error"
    GOAL_UNREACHABLE = "goal_unreachable"
    RESOURCE_LIMIT = "resource_limit"
    TIMEOUT = "timeout"


@dataclass
class TrajectoryStep:
    """轨迹步骤"""
    step_id: int
    tool_name: str
    arguments: Dict[str, Any]
    result: str
    is_error: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Trajectory:
    """执行轨迹"""
    trajectory_id: str
    goal: str
    steps: List[TrajectoryStep] = field(default_factory=list)
    final_outcome: str = ""
    success: bool = False
    failure_type: Optional[FailureType] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def step_count(self) -> int:
        return len(self.steps)
    
    @property
    def error_count(self) -> int:
        return sum(1 for s in self.steps if s.is_error)


@dataclass
class AntiPattern:
    """反模式"""
    name: str
    description: str
    failure_type: FailureType
    triggers: List[str]  # 触发条件
    symptoms: List[str]  # 症状
    prevention: List[str]  # 预防措施
    related_skill: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class HindsightResult:
    """后见之明结果"""
    original_goal: str
    actual_outcome: str
    alternative_goals: List[str]
    relabeled_trajectory: Optional[Trajectory]
    anti_patterns: List[AntiPattern]
    lessons_learned: List[str]


class HindsightReplay:
    """
    失败轨迹回收系统
    
    特性:
    - 将失败轨迹转化为教学信号
    - 失败分类：环境错误 / 知识不足 / 策略错误 / 目标不可达
    - 结果提取：从失败轨迹中提取部分成功的子目标
    - LLM 引导重标注：将轨迹改写为"如何避免这个错误"的教学案例
    - Anti-Pattern Skill：专门记录"不要这样做"的经验
    
    论文: AgentHER (arXiv 2603.21357)
    数据效率提升 2 倍，97.7% 重标注精度
    """
    
    def __init__(self, skill_manager: Optional[Any] = None):
        self.skill_manager = skill_manager
        self._trajectories: Dict[str, Trajectory] = {}
        self._anti_patterns: Dict[str, AntiPattern] = {}
    
    def record_trajectory(
        self,
        goal: str,
        steps: List[TrajectoryStep],
        final_outcome: str,
        success: bool,
    ) -> Trajectory:
        """记录轨迹"""
        import uuid
        trajectory = Trajectory(
            trajectory_id=str(uuid.uuid4())[:8],
            goal=goal,
            steps=steps,
            final_outcome=final_outcome,
            success=success,
        )
        
        if not success:
            trajectory.failure_type = self._classify_failure(trajectory)
        
        self._trajectories[trajectory.trajectory_id] = trajectory
        return trajectory
    
    def _classify_failure(self, trajectory: Trajectory) -> FailureType:
        """分类失败类型"""
        error_steps = [s for s in trajectory.steps if s.is_error]
        
        if not error_steps:
            return FailureType.GOAL_UNREACHABLE
        
        # 检查环境错误
        env_keywords = ["permission denied", "not found", "connection refused", "timeout", "out of memory"]
        for step in error_steps:
            result_lower = step.result.lower()
            for kw in env_keywords:
                if kw in result_lower:
                    if kw == "timeout":
                        return FailureType.TIMEOUT
                    return FailureType.ENVIRONMENT_ERROR
        
        # 检查资源限制
        resource_keywords = ["rate limit", "quota", "budget", "limit exceeded"]
        for step in error_steps:
            result_lower = step.result.lower()
            for kw in resource_keywords:
                if kw in result_lower:
                    return FailureType.RESOURCE_LIMIT
        
        # 检查策略错误
        if trajectory.error_count > trajectory.step_count * 0.5:
            return FailureType.STRATEGY_ERROR
        
        return FailureType.KNOWLEDGE_GAP
    
    def relabel_trajectory(self, trajectory: Trajectory) -> HindsightResult:
        """重标注失败轨迹"""
        alternative_goals = self._extract_alternative_goals(trajectory)
        anti_patterns = self._extract_anti_patterns(trajectory)
        lessons_learned = self._extract_lessons(trajectory)
        
        relabeled = None
        if alternative_goals:
            relabeled = Trajectory(
                trajectory_id=f"{trajectory.trajectory_id}_relabeled",
                goal=alternative_goals[0],
                steps=trajectory.steps,
                final_outcome=trajectory.final_outcome,
                success=True,  # 重标注为成功
            )
        
        return HindsightResult(
            original_goal=trajectory.goal,
            actual_outcome=trajectory.final_outcome,
            alternative_goals=alternative_goals,
            relabeled_trajectory=relabeled,
            anti_patterns=anti_patterns,
            lessons_learned=lessons_learned,
        )
    
    def _extract_alternative_goals(self, trajectory: Trajectory) -> List[str]:
        """提取替代目标"""
        alternatives = []
        
        # 找到部分成功的步骤
        successful_steps = [s for s in trajectory.steps if not s.is_error]
        
        if successful_steps:
            # 提取成功的子任务
            tool_sequence = [s.tool_name for s in successful_steps]
            if "write_file" in tool_sequence:
                alternatives.append("Create and write a file successfully")
            if "read_file" in tool_sequence:
                alternatives.append("Read and understand file content")
            if "terminal" in tool_sequence or "run_command" in tool_sequence:
                alternatives.append("Execute terminal commands")
        
        # 根据失败类型生成替代目标
        if trajectory.failure_type == FailureType.ENVIRONMENT_ERROR:
            alternatives.append(f"Identify environment limitations: {trajectory.final_outcome[:100]}")
        elif trajectory.failure_type == FailureType.KNOWLEDGE_GAP:
            alternatives.append(f"Discover knowledge gap: {trajectory.goal[:100]}")
        
        return alternatives
    
    def _extract_anti_patterns(self, trajectory: Trajectory) -> List[AntiPattern]:
        """提取反模式"""
        anti_patterns = []
        
        error_steps = [s for s in trajectory.steps if s.is_error]
        
        for step in error_steps:
            anti_pattern = AntiPattern(
                name=f"avoid_{step.tool_name}_error",
                description=f"Error when using {step.tool_name}: {step.result[:100]}",
                failure_type=trajectory.failure_type or FailureType.STRATEGY_ERROR,
                triggers=[f"Using {step.tool_name} with arguments: {json.dumps(step.arguments)[:100]}"],
                symptoms=[step.result[:200]],
                prevention=[f"Check conditions before calling {step.tool_name}"],
            )
            anti_patterns.append(anti_pattern)
            self._anti_patterns[anti_pattern.name] = anti_pattern
        
        return anti_patterns
    
    def _extract_lessons(self, trajectory: Trajectory) -> List[str]:
        """提取教训"""
        lessons = []
        
        if trajectory.failure_type == FailureType.ENVIRONMENT_ERROR:
            lessons.append("Always check environment prerequisites before execution")
        elif trajectory.failure_type == FailureType.KNOWLEDGE_GAP:
            lessons.append("Research and gather information before attempting complex tasks")
        elif trajectory.failure_type == FailureType.STRATEGY_ERROR:
            lessons.append("Break down complex tasks into smaller, verifiable steps")
        elif trajectory.failure_type == FailureType.RESOURCE_LIMIT:
            lessons.append("Monitor resource usage and implement rate limiting")
        elif trajectory.failure_type == FailureType.TIMEOUT:
            lessons.append("Set appropriate timeouts and implement retry logic")
        
        # 从错误步骤中提取具体教训
        error_steps = [s for s in trajectory.steps if s.is_error]
        for step in error_steps[:3]:  # 只取前3个错误
            lessons.append(f"Avoid: {step.tool_name} -> {step.result[:100]}")
        
        return lessons
    
    def create_anti_pattern_skill(self, trajectory: Trajectory) -> Optional[str]:
        """创建反模式技能"""
        if not self.skill_manager:
            return None
        
        result = self.relabel_trajectory(trajectory)
        
        if not result.anti_patterns:
            return None
        
        # 创建 Anti-Pattern Skill
        skill_name = f"avoid-{trajectory.trajectory_id}"
        description = f"Anti-patterns learned from failed task: {trajectory.goal[:100]}"
        
        when_to_use = [
            "Before attempting similar tasks",
            "When encountering similar errors",
            "During planning phase for complex operations",
        ]
        
        steps = [
            f"Check prerequisites: {', '.join([p.trigger for p in result.anti_patterns])}",
            "Verify environment conditions",
            "Have fallback strategies ready",
        ]
        
        pitfalls = [p.description for p in result.anti_patterns]
        
        try:
            skill = self.skill_manager.create_skill(
                name=skill_name,
                description=description,
                when_to_use=when_to_use,
                steps=steps,
                pitfalls=pitfalls,
                category="anti-patterns",
            )
            return skill.name
        except Exception as e:
            logger.error(f"Failed to create anti-pattern skill: {e}")
            return None
    
    def get_failed_trajectories(self) -> List[Trajectory]:
        """获取所有失败轨迹"""
        return [t for t in self._trajectories.values() if not t.success]
    
    def get_anti_patterns(self) -> List[AntiPattern]:
        """获取所有反模式"""
        return list(self._anti_patterns.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._trajectories)
        failed = sum(1 for t in self._trajectories.values() if not t.success)
        
        failure_types = {}
        for t in self._trajectories.values():
            if t.failure_type:
                ft = t.failure_type.value
                failure_types[ft] = failure_types.get(ft, 0) + 1
        
        return {
            "total_trajectories": total,
            "failed_trajectories": failed,
            "success_rate": (total - failed) / total if total > 0 else 0,
            "anti_patterns_count": len(self._anti_patterns),
            "failure_types": failure_types,
        }


hindsight_replay = HindsightReplay()
