"""
Utility-based Memory Refinement - 效用驱动记忆精炼
参考 ReMe (arXiv 2512.10696) 和 Memory-R1 (arXiv 2508.19828)
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class UsageStats:
    """使用统计"""
    recall_count: int = 0
    last_recall_time: Optional[datetime] = None
    averted_corrections: int = 0
    successful_applications: int = 0
    failed_applications: int = 0


@dataclass
class MemoryEntry:
    """记忆条目"""
    entry_id: str
    content: str
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    usage_stats: UsageStats = field(default_factory=UsageStats)
    utility_score: float = 0.0


@dataclass
class RefinementResult:
    """精炼结果"""
    promoted: List[str] = field(default_factory=list)
    demoted: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    consolidated: List[Tuple[str, str]] = field(default_factory=list)


class UtilityScorer:
    """
    效用评分器
    
    计算记忆条目的效用分数:
    - 检索频率（被 session_search 命中的次数）
    - 时间衰减（越老越低分）
    - 避免纠正价值（该记忆是否减少了用户纠正次数）
    """
    
    def __init__(
        self,
        recall_weight: float = 0.4,
        age_weight: float = 0.2,
        correction_weight: float = 0.3,
        success_weight: float = 0.1,
        decay_lambda: float = 0.1,  # 时间衰减系数
    ):
        self.recall_weight = recall_weight
        self.age_weight = age_weight
        self.correction_weight = correction_weight
        self.success_weight = success_weight
        self.decay_lambda = decay_lambda
    
    def score(self, entry: MemoryEntry, now: Optional[datetime] = None) -> float:
        """计算效用分数"""
        now = now or datetime.now()
        
        # 1. 检索频率分数 (归一化)
        recall_score = self._normalize_recall(entry.usage_stats.recall_count)
        
        # 2. 时间衰减分数
        age_days = (now - entry.created_at).days
        age_score = math.exp(-self.decay_lambda * age_days)
        
        # 3. 避免纠正分数
        correction_score = self._normalize_correction(entry.usage_stats.averted_corrections)
        
        # 4. 成功率分数
        total_apps = entry.usage_stats.successful_applications + entry.usage_stats.failed_applications
        if total_apps > 0:
            success_score = entry.usage_stats.successful_applications / total_apps
        else:
            success_score = 0.5  # 默认中等分数
        
        # 加权求和
        utility = (
            self.recall_weight * recall_score +
            self.age_weight * age_score +
            self.correction_weight * correction_score +
            self.success_weight * success_score
        )
        
        return min(1.0, max(0.0, utility))
    
    def _normalize_recall(self, count: int) -> float:
        """归一化检索次数"""
        # 使用 sigmoid 归一化
        return 1.0 / (1.0 + math.exp(-0.5 * (count - 5)))
    
    def _normalize_correction(self, count: int) -> float:
        """归一化避免纠正次数"""
        return min(1.0, count / 10.0)


class MemoryRefiner:
    """
    效用驱动记忆精炼器
    
    特性:
    - 效用评分系统
    - 自动淘汰低效用记忆
    - 高效用记忆升级为 Skill 候选
    - 记忆合并和压缩
    """
    
    DEFAULT_UTILITY_THRESHOLD = 0.3
    DEFAULT_PROMOTION_THRESHOLD = 0.8
    DEFAULT_MIN_AGE_DAYS = 7  # 最少存在天数才考虑淘汰
    
    def __init__(
        self,
        utility_threshold: float = DEFAULT_UTILITY_THRESHOLD,
        promotion_threshold: float = DEFAULT_PROMOTION_THRESHOLD,
        skill_manager: Optional[Any] = None,
    ):
        self.utility_threshold = utility_threshold
        self.promotion_threshold = promotion_threshold
        self.skill_manager = skill_manager
        self.scorer = UtilityScorer()
        
        self._entries: Dict[str, MemoryEntry] = {}
    
    def add_entry(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """添加记忆条目"""
        import uuid
        entry = MemoryEntry(
            entry_id=str(uuid.uuid4())[:8],
            content=content,
            metadata=metadata or {},
        )
        self._entries[entry.entry_id] = entry
        return entry
    
    def record_recall(self, entry_id: str):
        """记录检索"""
        if entry_id in self._entries:
            entry = self._entries[entry_id]
            entry.usage_stats.recall_count += 1
            entry.usage_stats.last_recall_time = datetime.now()
            self._update_score(entry)
    
    def record_correction_averted(self, entry_id: str):
        """记录避免纠正"""
        if entry_id in self._entries:
            entry = self._entries[entry_id]
            entry.usage_stats.averted_corrections += 1
            self._update_score(entry)
    
    def record_application(self, entry_id: str, success: bool):
        """记录应用"""
        if entry_id in self._entries:
            entry = self._entries[entry_id]
            if success:
                entry.usage_stats.successful_applications += 1
            else:
                entry.usage_stats.failed_applications += 1
            self._update_score(entry)
    
    def _update_score(self, entry: MemoryEntry):
        """更新效用分数"""
        entry.utility_score = self.scorer.score(entry)
    
    def refine(self) -> RefinementResult:
        """执行精炼"""
        result = RefinementResult()
        now = datetime.now()
        
        # 更新所有分数
        for entry in self._entries.values():
            self._update_score(entry)
        
        # 分类条目
        to_remove = []
        to_promote = []
        
        for entry_id, entry in self._entries.items():
            age_days = (now - entry.created_at).days
            
            # 检查是否应该淘汰
            if (entry.utility_score < self.utility_threshold and 
                age_days >= self.DEFAULT_MIN_AGE_DAYS):
                to_remove.append(entry_id)
            
            # 检查是否应该升级
            elif entry.utility_score >= self.promotion_threshold:
                to_promote.append(entry_id)
        
        # 执行淘汰
        for entry_id in to_remove:
            del self._entries[entry_id]
            result.removed.append(entry_id)
        
        # 执行升级
        for entry_id in to_promote:
            entry = self._entries[entry_id]
            if self.skill_manager:
                skill_name = self._create_skill_from_memory(entry)
                if skill_name:
                    result.promoted.append(entry_id)
        
        # 合并相似记忆
        result.consolidated = self._consolidate_similar()
        
        return result
    
    def _create_skill_from_memory(self, entry: MemoryEntry) -> Optional[str]:
        """从记忆创建技能"""
        if not self.skill_manager:
            return None
        
        try:
            skill = self.skill_manager.create_skill(
                name=f"learned-{entry.entry_id}",
                description=entry.content[:100],
                when_to_use=["When encountering similar situations"],
                steps=["Apply the learned knowledge"],
                pitfalls=[],
                category="learned",
            )
            return skill.name
        except Exception as e:
            logger.error(f"Failed to create skill from memory: {e}")
            return None
    
    def _consolidate_similar(self) -> List[Tuple[str, str]]:
        """合并相似记忆"""
        consolidated = []
        
        entries = list(self._entries.values())
        for i, entry1 in enumerate(entries):
            for entry2 in entries[i+1:]:
                if self._are_similar(entry1, entry2):
                    # 合并到 entry1
                    merged_content = self._merge_contents(entry1.content, entry2.content)
                    entry1.content = merged_content
                    entry1.usage_stats.recall_count += entry2.usage_stats.recall_count
                    entry1.usage_stats.averted_corrections += entry2.usage_stats.averted_corrections
                    
                    # 移除 entry2
                    if entry2.entry_id in self._entries:
                        del self._entries[entry2.entry_id]
                        consolidated.append((entry2.entry_id, entry1.entry_id))
        
        return consolidated
    
    def _are_similar(self, entry1: MemoryEntry, entry2: MemoryEntry) -> bool:
        """判断是否相似"""
        words1 = set(entry1.content.lower().split())
        words2 = set(entry2.content.lower().split())
        
        if not words1 or not words2:
            return False
        
        similarity = len(words1 & words2) / len(words1 | words2)
        return similarity > 0.7
    
    def _merge_contents(self, content1: str, content2: str) -> str:
        """合并内容"""
        # 简单合并：保留较长的内容
        if len(content1) >= len(content2):
            return content1
        return content2
    
    def get_top_entries(self, n: int = 10) -> List[MemoryEntry]:
        """获取最高效用的条目"""
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: e.utility_score,
            reverse=True,
        )
        return sorted_entries[:n]
    
    def get_low_entries(self, n: int = 10) -> List[MemoryEntry]:
        """获取最低效用的条目"""
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: e.utility_score,
        )
        return sorted_entries[:n]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._entries:
            return {
                "total_entries": 0,
                "avg_utility": 0,
                "total_recalls": 0,
                "total_corrections_averted": 0,
            }
        
        utilities = [e.utility_score for e in self._entries.values()]
        recalls = sum(e.usage_stats.recall_count for e in self._entries.values())
        corrections = sum(e.usage_stats.averted_corrections for e in self._entries.values())
        
        return {
            "total_entries": len(self._entries),
            "avg_utility": sum(utilities) / len(utilities),
            "max_utility": max(utilities),
            "min_utility": min(utilities),
            "total_recalls": recalls,
            "total_corrections_averted": corrections,
        }


memory_refiner = MemoryRefiner()
