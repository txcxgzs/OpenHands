"""
Meta Evolution - 自指式元进化
参考 Promptbreeder (ICML 2024)
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EvolutionMetric:
    """进化指标"""
    metric_id: str
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StrategyConfig:
    """策略配置"""
    config_id: str
    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    performance_score: float = 0.0
    usage_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class EvolutionResult:
    """进化结果"""
    old_config: Optional[StrategyConfig] = None
    new_config: Optional[StrategyConfig] = None
    improvement: float = 0.0
    changes: List[str] = field(default_factory=list)
    reasoning: str = ""


class MetaEvolutionLayer:
    """
    自指式元进化层
    
    特性:
    - 进化"如何进化"的元策略
    - 动态调整 Nudge 间隔
    - 自适应审查提示词
    - 动态 Curator 整合策略
    - 自适应 Memory 容量限制
    
    论文: Promptbreeder (ICML 2024)
    """
    
    DEFAULT_CONFIG_FILE = "meta_evolution_config.json"
    
    def __init__(
        self,
        config_dir: Optional[Path] = None,
        nudge_engine: Optional[Any] = None,
        skill_manager: Optional[Any] = None,
    ):
        self.config_dir = config_dir or Path.home() / ".openhands" / "meta_evolution"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.nudge_engine = nudge_engine
        self.skill_manager = skill_manager
        
        self._config_file = self.config_dir / self.DEFAULT_CONFIG_FILE
        self._current_config: Optional[StrategyConfig] = None
        self._historical_configs: List[StrategyConfig] = []
        self._metrics: List[EvolutionMetric] = []
        
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        if self._config_file.exists():
            try:
                data = json.loads(self._config_file.read_text())
                self._current_config = StrategyConfig(
                    config_id=data.get("config_id", "default"),
                    name=data.get("name", "default"),
                    parameters=data.get("parameters", self._default_parameters()),
                    performance_score=data.get("performance_score", 0.0),
                    usage_count=data.get("usage_count", 0),
                    created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
                    updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
                )
            except Exception as e:
                logger.warning(f"Failed to load meta evolution config: {e}")
        
        if not self._current_config:
            self._current_config = StrategyConfig(
                config_id="default",
                name="default",
                parameters=self._default_parameters(),
            )
    
    def _default_parameters(self) -> Dict[str, Any]:
        """默认参数"""
        return {
            "memory_nudge_interval": 10,
            "skill_nudge_interval": 10,
            "creation_complexity_threshold": 5,
            "memory_char_limit": 2200,
            "user_memory_char_limit": 1375,
            "curator_interval_hours": 168,  # 7天
            "curator_min_idle_hours": 2,
            "max_skills": 100,
            "review_max_iterations": 8,
            "enable_background_review": True,
        }
    
    def _save_config(self):
        """保存配置"""
        if self._current_config:
            data = {
                "config_id": self._current_config.config_id,
                "name": self._current_config.name,
                "parameters": self._current_config.parameters,
                "performance_score": self._current_config.performance_score,
                "usage_count": self._current_config.usage_count,
                "created_at": self._current_config.created_at.isoformat(),
                "updated_at": self._current_config.updated_at.isoformat(),
            }
            self._config_file.write_text(json.dumps(data, indent=2))
    
    def get_current_config(self) -> StrategyConfig:
        """获取当前配置"""
        return self._current_config
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """获取参数"""
        if self._current_config:
            return self._current_config.parameters.get(key, default)
        return default
    
    def record_metric(self, name: str, value: float):
        """记录指标"""
        import uuid
        metric = EvolutionMetric(
            metric_id=str(uuid.uuid4())[:8],
            name=name,
            value=value,
        )
        self._metrics.append(metric)
        
        # 只保留最近 100 个指标
        if len(self._metrics) > 100:
            self._metrics = self._metrics[-100:]
    
    def evolve(self) -> EvolutionResult:
        """执行进化"""
        result = EvolutionResult()
        result.old_config = self._current_config
        
        # 分析历史效果
        analysis = self._analyze_historical_performance()
        
        # 生成新配置
        new_params = self._generate_new_parameters(analysis)
        
        import uuid
        new_config = StrategyConfig(
            config_id=str(uuid.uuid4())[:8],
            name=f"evolved_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            parameters=new_params,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        result.new_config = new_config
        result.changes = self._compute_changes(result.old_config.parameters, new_params)
        result.reasoning = self._generate_reasoning(analysis, result.changes)
        
        # 需要用户确认才应用
        # self._apply_config(new_config)
        
        return result
    
    def _analyze_historical_performance(self) -> Dict[str, Any]:
        """分析历史表现"""
        analysis = {
            "avg_skill_usage": 0.0,
            "skill_success_rate": 0.0,
            "memory_hit_rate": 0.0,
            "review_effectiveness": 0.0,
        }
        
        if self._metrics:
            # 计算平均指标
            skill_usage_metrics = [m for m in self._metrics if m.name == "skill_usage"]
            if skill_usage_metrics:
                analysis["avg_skill_usage"] = sum(m.value for m in skill_usage_metrics) / len(skill_usage_metrics)
            
            success_metrics = [m for m in self._metrics if m.name == "skill_success"]
            if success_metrics:
                analysis["skill_success_rate"] = sum(m.value for m in success_metrics) / len(success_metrics)
            
            memory_metrics = [m for m in self._metrics if m.name == "memory_hit"]
            if memory_metrics:
                analysis["memory_hit_rate"] = sum(m.value for m in memory_metrics) / len(memory_metrics)
        
        return analysis
    
    def _generate_new_parameters(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成新参数"""
        new_params = self._current_config.parameters.copy()
        
        # 根据分析结果调整参数
        
        # 如果技能使用率低，降低创建阈值
        if analysis["avg_skill_usage"] < 0.3:
            new_params["creation_complexity_threshold"] = max(3, new_params.get("creation_complexity_threshold", 5) - 1)
        
        # 如果成功率高，可以增加 nudge 间隔
        if analysis["skill_success_rate"] > 0.8:
            new_params["skill_nudge_interval"] = min(20, new_params.get("skill_nudge_interval", 10) + 2)
        
        # 如果记忆命中率低，调整记忆限制
        if analysis["memory_hit_rate"] < 0.5:
            new_params["memory_char_limit"] = min(5000, new_params.get("memory_char_limit", 2200) + 200)
        
        return new_params
    
    def _compute_changes(self, old_params: Dict, new_params: Dict) -> List[str]:
        """计算变化"""
        changes = []
        for key in set(old_params.keys()) | set(new_params.keys()):
            old_val = old_params.get(key)
            new_val = new_params.get(key)
            if old_val != new_val:
                changes.append(f"{key}: {old_val} → {new_val}")
        return changes
    
    def _generate_reasoning(self, analysis: Dict, changes: List[str]) -> str:
        """生成推理说明"""
        reasoning_parts = [
            f"Based on performance analysis:",
            f"- Average skill usage: {analysis['avg_skill_usage']:.2f}",
            f"- Skill success rate: {analysis['skill_success_rate']:.2f}",
            f"- Memory hit rate: {analysis['memory_hit_rate']:.2f}",
            "",
            "Proposed changes:",
        ]
        
        for change in changes:
            reasoning_parts.append(f"- {change}")
        
        return "\n".join(reasoning_parts)
    
    def apply_config(self, config: StrategyConfig, require_confirmation: bool = True) -> bool:
        """应用配置"""
        if require_confirmation:
            logger.info(f"New config requires confirmation: {config.name}")
            return False
        
        self._historical_configs.append(self._current_config)
        self._current_config = config
        self._save_config()
        
        # 应用到各组件
        self._apply_to_components()
        
        return True
    
    def _apply_to_components(self):
        """应用到各组件"""
        if self.nudge_engine and self._current_config:
            params = self._current_config.parameters
            self.nudge_engine.config.memory_nudge_interval = params.get("memory_nudge_interval", 10)
            self.nudge_engine.config.skill_nudge_interval = params.get("skill_nudge_interval", 10)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "current_config": {
                "name": self._current_config.name if self._current_config else None,
                "performance_score": self._current_config.performance_score if self._current_config else 0,
                "usage_count": self._current_config.usage_count if self._current_config else 0,
            },
            "historical_configs_count": len(self._historical_configs),
            "metrics_count": len(self._metrics),
            "parameters": self._current_config.parameters if self._current_config else {},
        }


meta_evolution = MetaEvolutionLayer()
