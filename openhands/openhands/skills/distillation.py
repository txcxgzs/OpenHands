"""
Multi-faceted Distillation - 多面经验蒸馏
参考 ReMe (arXiv 2512.10696) 和 Mem^n (arXiv 2508.06433)
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import json
import re

logger = logging.getLogger(__name__)


@dataclass
class SuccessPattern:
    """成功模式"""
    pattern_id: str
    description: str
    context: str
    actions: List[str]
    outcome: str
    confidence: float = 1.0


@dataclass
class FailureTrigger:
    """失败触发器"""
    trigger_id: str
    surface_symptom: str  # 表面症状
    root_cause: str       # 根本原因
    trigger_conditions: List[str]  # 触发条件
    prevention: str       # 预防措施
    examples: List[str] = field(default_factory=list)


@dataclass
class ContrastInsight:
    """对比洞察"""
    insight_id: str
    action_a: str  # 做了 A
    action_b: str  # 做了 B（对比）
    result_a: str  # A 的结果
    result_b: str  # B 的结果
    conclusion: str


@dataclass
class DecisionPoint:
    """决策点"""
    point_id: str
    description: str
    condition: str  # 条件
    options: List[str]  # 选项
    recommended: str  # 推荐
    rationale: str  # 理由


@dataclass
class DistillationResult:
    """蒸馏结果"""
    success_patterns: List[SuccessPattern] = field(default_factory=list)
    failure_triggers: List[FailureTrigger] = field(default_factory=list)
    contrast_insights: List[ContrastInsight] = field(default_factory=list)
    decision_points: List[DecisionPoint] = field(default_factory=list)


class MultiFacetedDistiller:
    """
    多面经验蒸馏器
    
    特性:
    - 成功模式识别
    - 失败触发器分析（表面症状 → 根本原因 → 预防措施）
    - 对比洞察（做了 A 成功 vs 做了 B 失败）
    - 决策点识别
    
    论文: ReMe (arXiv 2512.10696), Mem^n (arXiv 2508.06433)
    """
    
    def __init__(self, skill_manager: Optional[Any] = None):
        self.skill_manager = skill_manager
        
        self._success_patterns: Dict[str, SuccessPattern] = {}
        self._failure_triggers: Dict[str, FailureTrigger] = {}
        self._contrast_insights: Dict[str, ContrastInsight] = {}
        self._decision_points: Dict[str, DecisionPoint] = {}
    
    def distill(self, trajectory: Dict[str, Any]) -> DistillationResult:
        """从轨迹中蒸馏多面经验"""
        result = DistillationResult()
        
        steps = trajectory.get("steps", [])
        success = trajectory.get("success", False)
        
        # 提取成功模式
        if success:
            patterns = self._extract_success_patterns(steps, trajectory.get("goal", ""))
            result.success_patterns = patterns
            for p in patterns:
                self._success_patterns[p.pattern_id] = p
        
        # 提取失败触发器
        error_steps = [s for s in steps if s.get("is_error")]
        if error_steps:
            triggers = self._extract_failure_triggers(error_steps, steps)
            result.failure_triggers = triggers
            for t in triggers:
                self._failure_triggers[t.trigger_id] = t
        
        # 提取对比洞察
        insights = self._extract_contrast_insights(steps)
        result.contrast_insights = insights
        for i in insights:
            self._contrast_insights[i.insight_id] = i
        
        # 提取决策点
        decisions = self._identify_decision_points(steps)
        result.decision_points = decisions
        for d in decisions:
            self._decision_points[d.point_id] = d
        
        return result
    
    def _extract_success_patterns(
        self,
        steps: List[Dict],
        goal: str,
    ) -> List[SuccessPattern]:
        """提取成功模式"""
        patterns = []
        
        # 找到关键成功步骤序列
        successful_sequence = []
        for step in steps:
            if not step.get("is_error"):
                successful_sequence.append(step)
        
        if len(successful_sequence) >= 3:
            # 提取模式
            import uuid
            pattern = SuccessPattern(
                pattern_id=str(uuid.uuid4())[:8],
                description=f"Successful pattern for: {goal[:50]}",
                context=self._extract_context(steps),
                actions=[s.get("tool", s.get("name", "unknown")) for s in successful_sequence[:5]],
                outcome="Task completed successfully",
                confidence=0.8,
            )
            patterns.append(pattern)
        
        return patterns
    
    def _extract_failure_triggers(
        self,
        error_steps: List[Dict],
        all_steps: List[Dict],
    ) -> List[FailureTrigger]:
        """提取失败触发器"""
        triggers = []
        
        for error_step in error_steps:
            import uuid
            
            surface_symptom = error_step.get("result", error_step.get("error", "Unknown error"))[:100]
            
            # 分析根本原因
            root_cause = self._analyze_root_cause(error_step, all_steps)
            
            # 提取触发条件
            trigger_conditions = self._extract_trigger_conditions(error_step)
            
            # 生成预防措施
            prevention = self._generate_prevention(root_cause)
            
            trigger = FailureTrigger(
                trigger_id=str(uuid.uuid4())[:8],
                surface_symptom=surface_symptom,
                root_cause=root_cause,
                trigger_conditions=trigger_conditions,
                prevention=prevention,
                examples=[surface_symptom],
            )
            triggers.append(trigger)
        
        return triggers
    
    def _analyze_root_cause(self, error_step: Dict, all_steps: List[Dict]) -> str:
        """分析根本原因"""
        error_msg = error_step.get("result", error_step.get("error", "")).lower()
        
        # 常见错误模式映射
        error_patterns = {
            "permission denied": "Insufficient permissions - need to check access rights",
            "not found": "Resource does not exist - need to verify path/existence first",
            "timeout": "Operation took too long - need to optimize or increase timeout",
            "connection refused": "Service not available - need to check service status",
            "out of memory": "Resource exhaustion - need to reduce memory usage",
            "syntax error": "Invalid syntax - need to validate input/code",
            "imagepullbackoff": "Container image not available - need to push image first",
            "crashloopbackoff": "Application crashing - need to check logs and health checks",
        }
        
        for pattern, cause in error_patterns.items():
            if pattern in error_msg:
                return cause
        
        return f"Unknown root cause for: {error_msg[:50]}"
    
    def _extract_trigger_conditions(self, error_step: Dict) -> List[str]:
        """提取触发条件"""
        conditions = []
        
        tool = error_step.get("tool", error_step.get("name", "unknown"))
        args = error_step.get("arguments", {})
        
        conditions.append(f"Using {tool}")
        if args:
            for key, value in list(args.items())[:3]:
                conditions.append(f"With {key}={str(value)[:30]}")
        
        return conditions
    
    def _generate_prevention(self, root_cause: str) -> str:
        """生成预防措施"""
        prevention_map = {
            "Insufficient permissions": "Check and request appropriate permissions before operation",
            "Resource does not exist": "Verify resource existence before accessing",
            "Operation took too long": "Implement timeout handling and optimization",
            "Service not available": "Check service health before connecting",
            "Resource exhaustion": "Monitor and manage resource usage",
            "Invalid syntax": "Validate input before processing",
            "Container image not available": "Build and push image before deployment",
            "Application crashing": "Add health checks and error handling",
        }
        
        for key, prevention in prevention_map.items():
            if key.lower() in root_cause.lower():
                return prevention
        
        return f"Prevent by: {root_cause}"
    
    def _extract_contrast_insights(self, steps: List[Dict]) -> List[ContrastInsight]:
        """提取对比洞察"""
        insights = []
        
        # 找到错误和成功步骤的对比
        for i, step in enumerate(steps):
            if step.get("is_error") and i + 1 < len(steps):
                next_step = steps[i + 1]
                if not next_step.get("is_error"):
                    import uuid
                    insight = ContrastInsight(
                        insight_id=str(uuid.uuid4())[:8],
                        action_a=f"{step.get('tool', 'unknown')} (failed)",
                        action_b=f"{next_step.get('tool', 'unknown')} (succeeded)",
                        result_a=step.get("result", "")[:50],
                        result_b=next_step.get("result", "Success")[:50],
                        conclusion=f"After failure with {step.get('tool', 'unknown')}, try {next_step.get('tool', 'unknown')}",
                    )
                    insights.append(insight)
        
        return insights
    
    def _identify_decision_points(self, steps: List[Dict]) -> List[DecisionPoint]:
        """识别决策点"""
        decisions = []
        
        # 找到关键决策步骤
        for i, step in enumerate(steps):
            tool = step.get("tool", step.get("name", ""))
            
            # 某些工具代表关键决策点
            if tool in ["write_file", "terminal", "run_command", "kubectl", "docker"]:
                import uuid
                decision = DecisionPoint(
                    point_id=str(uuid.uuid4())[:8],
                    description=f"Decision at step {i+1}: {tool}",
                    condition=f"After {steps[i-1].get('tool', 'start') if i > 0 else 'start'}",
                    options=[f"Use {tool}", "Use alternative approach"],
                    recommended=f"Use {tool}",
                    rationale=f"Based on successful execution",
                )
                decisions.append(decision)
        
        return decisions[:5]  # 最多5个决策点
    
    def _extract_context(self, steps: List[Dict]) -> str:
        """提取上下文"""
        tools = set(s.get("tool", s.get("name", "unknown")) for s in steps)
        return f"Tools used: {', '.join(tools)}"
    
    def create_enhanced_skill(
        self,
        base_skill: Any,
        distillation: DistillationResult,
    ) -> Dict[str, Any]:
        """创建增强版技能"""
        skill_content = {
            "name": base_skill.name if base_skill else "enhanced-skill",
            "description": getattr(base_skill, 'description', 'Enhanced skill'),
            "steps": [],
            "pitfalls": [],
            "decision_points": [],
            "failure_triggers": [],
        }
        
        # 添加成功模式作为步骤
        for pattern in distillation.success_patterns:
            skill_content["steps"].extend(pattern.actions)
        
        # 添加失败触发器作为陷阱
        for trigger in distillation.failure_triggers:
            skill_content["pitfalls"].append(f"{trigger.surface_symptom} → {trigger.prevention}")
            skill_content["failure_triggers"].append({
                "symptom": trigger.surface_symptom,
                "cause": trigger.root_cause,
                "prevention": trigger.prevention,
            })
        
        # 添加决策点
        for decision in distillation.decision_points:
            skill_content["decision_points"].append({
                "description": decision.description,
                "condition": decision.condition,
                "options": decision.options,
                "recommended": decision.recommended,
            })
        
        return skill_content
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "success_patterns": len(self._success_patterns),
            "failure_triggers": len(self._failure_triggers),
            "contrast_insights": len(self._contrast_insights),
            "decision_points": len(self._decision_points),
        }


multi_faceted_distiller = MultiFacetedDistiller()
