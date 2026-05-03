"""
Experience Compression Spectrum - 经验压缩谱
参考 arXiv 2604.15877
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import json
import re

logger = logging.getLogger(__name__)


class CompressionLevel(Enum):
    """压缩级别"""
    RAW_TRAJECTORY = "raw_trajectory"      # 原始轨迹 (1x)
    EPISODIC_MEMORY = "episodic_memory"    # 情景记忆 (5-20x)
    PROCEDURAL_SKILL = "procedural_skill"  # 程序性技能 (50-500x)
    DECLARATIVE_RULE = "declarative_rule"  # 声明性规则 (1000x+)


@dataclass
class RawTrajectory:
    """原始轨迹"""
    trajectory_id: str
    goal: str
    steps: List[Dict[str, Any]]
    final_result: str
    success: bool
    token_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class EpisodicMemory:
    """情景记忆 - 5-20x 压缩"""
    memory_id: str
    title: str
    summary: str
    key_actions: List[str]
    errors_encountered: List[str]
    solutions_applied: List[str]
    context: str
    source_trajectory: str
    token_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ProceduralSkill:
    """程序性技能 - 50-500x 压缩"""
    skill_id: str
    name: str
    description: str
    steps: List[str]
    pitfalls: List[str]
    decision_points: List[str]
    source_episodic: List[str]
    usage_count: int = 0
    token_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DeclarativeRule:
    """声明性规则 - 1000x+ 压缩"""
    rule_id: str
    rule: str
    context: str
    confidence: float = 1.0
    source_skill: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


class ExperienceCompressor:
    """
    经验压缩谱
    
    四级压缩管线:
    原始轨迹 → 情景记忆 → 程序性技能 → 声明性规则
    
    论文: Experience Compression Spectrum (arXiv 2604.15877)
    """
    
    def __init__(self, skill_manager: Optional[Any] = None):
        self.skill_manager = skill_manager
        
        self._raw_trajectories: Dict[str, RawTrajectory] = {}
        self._episodic_memories: Dict[str, EpisodicMemory] = {}
        self._procedural_skills: Dict[str, ProceduralSkill] = {}
        self._declarative_rules: Dict[str, DeclarativeRule] = {}
    
    def record_raw_trajectory(
        self,
        goal: str,
        steps: List[Dict[str, Any]],
        final_result: str,
        success: bool,
    ) -> RawTrajectory:
        """记录原始轨迹"""
        import uuid
        trajectory = RawTrajectory(
            trajectory_id=str(uuid.uuid4())[:8],
            goal=goal,
            steps=steps,
            final_result=final_result,
            success=success,
            token_count=self._estimate_tokens(goal + str(steps) + final_result),
        )
        self._raw_trajectories[trajectory.trajectory_id] = trajectory
        return trajectory
    
    def compress_to_episodic(self, trajectory: RawTrajectory) -> EpisodicMemory:
        """压缩到情景记忆 (5-20x)"""
        import uuid
        
        # 提取关键信息
        key_actions = self._extract_key_actions(trajectory.steps)
        errors = self._extract_errors(trajectory.steps)
        solutions = self._extract_solutions(trajectory.steps)
        
        # 生成摘要
        summary = self._generate_summary(trajectory)
        
        memory = EpisodicMemory(
            memory_id=str(uuid.uuid4())[:8],
            title=f"Experience: {trajectory.goal[:50]}",
            summary=summary,
            key_actions=key_actions,
            errors_encountered=errors,
            solutions_applied=solutions,
            context=self._extract_context(trajectory),
            source_trajectory=trajectory.trajectory_id,
            token_count=self._estimate_tokens(summary + str(key_actions) + str(errors)),
        )
        
        self._episodic_memories[memory.memory_id] = memory
        return memory
    
    def compress_to_procedural(self, memories: List[EpisodicMemory]) -> ProceduralSkill:
        """压缩到程序性技能 (50-500x)"""
        import uuid
        
        # 合并多个情景记忆
        all_actions = []
        all_errors = []
        all_solutions = []
        
        for mem in memories:
            all_actions.extend(mem.key_actions)
            all_errors.extend(mem.errors_encountered)
            all_solutions.extend(mem.solutions_applied)
        
        # 提取通用步骤
        steps = self._generalize_steps(all_actions)
        pitfalls = self._extract_pitfalls(all_errors, all_solutions)
        decision_points = self._extract_decision_points(memories)
        
        skill = ProceduralSkill(
            skill_id=str(uuid.uuid4())[:8],
            name=self._generate_skill_name(memories),
            description=self._generate_skill_description(memories),
            steps=steps,
            pitfalls=pitfalls,
            decision_points=decision_points,
            source_episodic=[m.memory_id for m in memories],
            token_count=self._estimate_tokens(str(steps) + str(pitfalls)),
        )
        
        self._procedural_skills[skill.skill_id] = skill
        return skill
    
    def compress_to_declarative(self, skill: ProceduralSkill) -> DeclarativeRule:
        """压缩到声明性规则 (1000x+)"""
        import uuid
        
        # 从技能中提取核心规则
        rule_text = self._extract_core_rule(skill)
        
        rule = DeclarativeRule(
            rule_id=str(uuid.uuid4())[:8],
            rule=rule_text,
            context=skill.description,
            confidence=1.0,
            source_skill=skill.skill_id,
        )
        
        self._declarative_rules[rule.rule_id] = rule
        return rule
    
    def auto_compress(self, trajectory: RawTrajectory) -> Tuple[EpisodicMemory, Optional[ProceduralSkill], Optional[DeclarativeRule]]:
        """自动压缩流程"""
        # Level 1: 原始轨迹 → 情景记忆
        episodic = self.compress_to_episodic(trajectory)
        
        procedural = None
        declarative = None
        
        # 检查是否有相似的情景记忆可以合并
        similar_memories = self._find_similar_episodic(episodic)
        if len(similar_memories) >= 2:  # 至少2个相似记忆才创建技能
            similar_memories.append(episodic)
            procedural = self.compress_to_procedural(similar_memories)
            
            # 如果技能使用次数足够，提取规则
            if procedural.usage_count >= 5:
                declarative = self.compress_to_declarative(procedural)
        
        return episodic, procedural, declarative
    
    def _extract_key_actions(self, steps: List[Dict]) -> List[str]:
        """提取关键动作"""
        actions = []
        for step in steps:
            tool = step.get("tool", step.get("name", "unknown"))
            if not step.get("is_error"):
                actions.append(f"{tool}: {step.get('summary', '')[:50]}")
        return actions[:10]  # 最多10个
    
    def _extract_errors(self, steps: List[Dict]) -> List[str]:
        """提取错误"""
        errors = []
        for step in steps:
            if step.get("is_error"):
                errors.append(step.get("result", step.get("error", ""))[:100])
        return errors
    
    def _extract_solutions(self, steps: List[Dict]) -> List[str]:
        """提取解决方案"""
        solutions = []
        for i, step in enumerate(steps):
            if step.get("is_error") and i + 1 < len(steps):
                next_step = steps[i + 1]
                if not next_step.get("is_error"):
                    solutions.append(f"After error, used {next_step.get('tool', 'unknown')}")
        return solutions
    
    def _generate_summary(self, trajectory: RawTrajectory) -> str:
        """生成摘要"""
        success_status = "succeeded" if trajectory.success else "failed"
        return f"Task '{trajectory.goal[:50]}' {success_status} with {len(trajectory.steps)} steps"
    
    def _extract_context(self, trajectory: RawTrajectory) -> str:
        """提取上下文"""
        tools_used = set(s.get("tool", s.get("name", "unknown")) for s in trajectory.steps)
        return f"Tools used: {', '.join(tools_used)}"
    
    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数"""
        return len(text) // 4  # 粗略估算
    
    def _generalize_steps(self, actions: List[str]) -> List[str]:
        """泛化步骤"""
        # 去重并保留顺序
        seen = set()
        unique = []
        for action in actions:
            key = action.split(":")[0] if ":" in action else action
            if key not in seen:
                seen.add(key)
                unique.append(action)
        return unique[:10]
    
    def _extract_pitfalls(self, errors: List[str], solutions: List[str]) -> List[str]:
        """提取陷阱"""
        pitfalls = []
        for error in errors[:5]:
            pitfalls.append(f"Watch out for: {error[:80]}")
        return pitfalls
    
    def _extract_decision_points(self, memories: List[EpisodicMemory]) -> List[str]:
        """提取决策点"""
        return ["Check prerequisites before starting", "Verify results after each step"]
    
    def _generate_skill_name(self, memories: List[EpisodicMemory]) -> str:
        """生成技能名称"""
        if memories:
            first_goal = memories[0].title.replace("Experience: ", "")
            return f"skill-{first_goal[:30]}".replace(" ", "-").lower()
        return "general-skill"
    
    def _generate_skill_description(self, memories: List[EpisodicMemory]) -> str:
        """生成技能描述"""
        if memories:
            return f"Learned from {len(memories)} similar experiences"
        return "General skill"
    
    def _extract_core_rule(self, skill: ProceduralSkill) -> str:
        """提取核心规则"""
        if skill.steps:
            return f"Always: {skill.steps[0][:100]}"
        return f"Follow: {skill.description[:100]}"
    
    def _find_similar_episodic(self, memory: EpisodicMemory) -> List[EpisodicMemory]:
        """查找相似的情景记忆"""
        similar = []
        for mem in self._episodic_memories.values():
            if mem.memory_id == memory.memory_id:
                continue
            # 简单相似度检查
            if self._similarity(mem.summary, memory.summary) > 0.5:
                similar.append(mem)
        return similar
    
    def _similarity(self, s1: str, s2: str) -> float:
        """计算相似度"""
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """获取压缩统计"""
        return {
            "raw_trajectories": len(self._raw_trajectories),
            "episodic_memories": len(self._episodic_memories),
            "procedural_skills": len(self._procedural_skills),
            "declarative_rules": len(self._declarative_rules),
            "compression_ratios": {
                "episodic": "5-20x",
                "procedural": "50-500x",
                "declarative": "1000x+",
            },
        }


experience_compressor = ExperienceCompressor()
