"""
Curator - 后台审查机制
参考 Hermes Agent 的 Curator 系统
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import json
import logging
import threading
import time

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_HOURS = 24 * 7  # 7 天间隔
DEFAULT_MIN_IDLE_HOURS = 2  # 最少空闲 2 小时
DEFAULT_STALE_AFTER_DAYS = 30  # 30 天未使用标记为过时
DEFAULT_ARCHIVE_AFTER_DAYS = 90  # 90 天未使用归档


class SkillState(Enum):
    """技能状态"""
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"


@dataclass
class CuratorState:
    """Curator 状态"""
    enabled: bool = True
    paused: bool = False
    last_run_at: Optional[datetime] = None
    total_runs: int = 0
    consolidations: int = 0
    prunings: int = 0


@dataclass
class CuratorConfig:
    """Curator 配置"""
    interval_hours: int = DEFAULT_INTERVAL_HOURS
    min_idle_hours: int = DEFAULT_MIN_IDLE_HOURS
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS
    archive_after_days: int = DEFAULT_ARCHIVE_AFTER_DAYS
    max_skills_to_review: int = 50
    enable_auto_archive: bool = True


@dataclass
class ConsolidationResult:
    """整合结果"""
    consolidated: List[str] = field(default_factory=list)
    pruned: List[str] = field(default_factory=list)
    archived: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class Curator:
    """
    Curator 后台审查机制
    
    特性:
    - 空闲触发（非 cron）
    - 两阶段执行：自动状态转换 + LLM 审查整合
    - Skill 生命周期：ACTIVE → STALE → ARCHIVED → deleted
    - 分类与对账系统
    """
    
    def __init__(
        self,
        state_dir: Optional[Path] = None,
        config: Optional[CuratorConfig] = None,
        skill_manager: Optional[Any] = None,
    ):
        self.state_dir = state_dir or Path.home() / ".openhands" / "curator"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = config or CuratorConfig()
        self.skill_manager = skill_manager
        
        self._state_file = self.state_dir / "curator_state.json"
        self._state = self._load_state()
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def _load_state(self) -> CuratorState:
        """加载状态"""
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                return CuratorState(
                    enabled=data.get("enabled", True),
                    paused=data.get("paused", False),
                    last_run_at=datetime.fromisoformat(data["last_run_at"]) if data.get("last_run_at") else None,
                    total_runs=data.get("total_runs", 0),
                    consolidations=data.get("consolidations", 0),
                    prunings=data.get("prunings", 0),
                )
            except Exception as e:
                logger.warning(f"Failed to load curator state: {e}")
        
        return CuratorState()
    
    def _save_state(self):
        """保存状态"""
        data = {
            "enabled": self._state.enabled,
            "paused": self._state.paused,
            "last_run_at": self._state.last_run_at.isoformat() if self._state.last_run_at else None,
            "total_runs": self._state.total_runs,
            "consolidations": self._state.consolidations,
            "prunings": self._state.prunings,
        }
        self._state_file.write_text(json.dumps(data, indent=2))
    
    def is_enabled(self) -> bool:
        """是否启用"""
        return self._state.enabled
    
    def is_paused(self) -> bool:
        """是否暂停"""
        return self._state.paused
    
    def pause(self):
        """暂停"""
        self._state.paused = True
        self._save_state()
    
    def resume(self):
        """恢复"""
        self._state.paused = False
        self._save_state()
    
    def enable(self):
        """启用"""
        self._state.enabled = True
        self._save_state()
    
    def disable(self):
        """禁用"""
        self._state.enabled = False
        self._save_state()
    
    def should_run_now(self, now: Optional[datetime] = None) -> bool:
        """是否应该运行"""
        if not self.is_enabled():
            return False
        if self.is_paused():
            return False
        
        now = now or datetime.now()
        
        if self._state.last_run_at is None:
            self._state.last_run_at = now
            self._save_state()
            return False
        
        elapsed = now - self._state.last_run_at
        return elapsed >= timedelta(hours=self.config.interval_hours)
    
    def run(self, force: bool = False) -> ConsolidationResult:
        """运行审查"""
        if not force and not self.should_run_now():
            logger.debug("Curator not due to run")
            return ConsolidationResult()
        
        logger.info("Starting curator run...")
        
        result = ConsolidationResult()
        
        # 阶段1: 自动状态转换
        transitions = self._apply_automatic_transitions()
        result.archived = transitions.get("archived", [])
        result.pruned = transitions.get("stale", [])
        
        # 阶段2: LLM 审查整合
        if self.skill_manager:
            consolidations = self._run_llm_consolidation()
            result.consolidated = consolidations.get("consolidated", [])
            result.errors = consolidations.get("errors", [])
        
        # 更新状态
        self._state.last_run_at = datetime.now()
        self._state.total_runs += 1
        self._state.consolidations += len(result.consolidated)
        self._state.prunings += len(result.pruned)
        self._save_state()
        
        logger.info(f"Curator run completed: {len(result.consolidated)} consolidated, {len(result.pruned)} pruned")
        
        return result
    
    def _apply_automatic_transitions(self, now: Optional[datetime] = None) -> Dict[str, List[str]]:
        """自动状态转换"""
        now = now or datetime.now()
        
        stale_cutoff = now - timedelta(days=self.config.stale_after_days)
        archive_cutoff = now - timedelta(days=self.config.archive_after_days)
        
        transitions = {
            "stale": [],
            "active": [],
            "archived": [],
        }
        
        if not self.skill_manager:
            return transitions
        
        for skill in self.skill_manager.list_skills():
            skill_name = skill.name
            anchor = skill.metadata.updated
            
            if anchor <= archive_cutoff:
                if self.config.enable_auto_archive:
                    self._archive_skill(skill_name)
                    transitions["archived"].append(skill_name)
            elif anchor <= stale_cutoff and skill.metadata.state == SkillState.ACTIVE:
                self._set_skill_state(skill_name, SkillState.STALE)
                transitions["stale"].append(skill_name)
            elif anchor > stale_cutoff and skill.metadata.state == SkillState.STALE:
                self._set_skill_state(skill_name, SkillState.ACTIVE)
                transitions["active"].append(skill_name)
        
        return transitions
    
    def _run_llm_consolidation(self) -> Dict[str, List[str]]:
        """LLM 审查整合"""
        # 这里需要 LLM 来分析技能并整合
        # 简化实现：返回空结果
        return {"consolidated": [], "errors": []}
    
    def _archive_skill(self, name: str):
        """归档技能"""
        if self.skill_manager:
            skill = self.skill_manager.get_skill(name)
            if skill:
                skill.metadata.state = SkillState.ARCHIVED
    
    def _set_skill_state(self, name: str, state: SkillState):
        """设置技能状态"""
        if self.skill_manager:
            skill = self.skill_manager.get_skill(name)
            if skill:
                skill.metadata.state = state
    
    def start_background(self, check_interval_seconds: int = 3600):
        """启动后台运行"""
        if self._running:
            return
        
        self._running = True
        
        def _run_loop():
            while self._running:
                try:
                    if self.should_run_now():
                        self.run()
                except Exception as e:
                    logger.error(f"Curator error: {e}")
                
                time.sleep(check_interval_seconds)
        
        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()
    
    def stop_background(self):
        """停止后台运行"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "enabled": self._state.enabled,
            "paused": self._state.paused,
            "last_run_at": self._state.last_run_at.isoformat() if self._state.last_run_at else None,
            "total_runs": self._state.total_runs,
            "consolidations": self._state.consolidations,
            "prunings": self._state.prunings,
            "next_run_in_hours": self._get_next_run_hours(),
        }
    
    def _get_next_run_hours(self) -> Optional[float]:
        """获取下次运行时间（小时）"""
        if not self._state.last_run_at:
            return 0.0
        
        elapsed = datetime.now() - self._state.last_run_at
        remaining = timedelta(hours=self.config.interval_hours) - elapsed
        return remaining.total_seconds() / 3600 if remaining.total_seconds() > 0 else 0.0


curator = Curator()
