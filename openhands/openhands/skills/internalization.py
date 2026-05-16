"""
Knowledge Internalization - 知识内化
参考 ELL Framework (arXiv 2508.19005)
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


INTERNALIZATION_THRESHOLD = 20  # 使用次数阈值
MAX_INTERNALIZED_RULES = 50    # 最大内化规则数


@dataclass
class InternalizedRule:
    """内化规则"""
    rule_id: str
    rule: str
    source_skill: str
    usage_count: int
    internalized_at: datetime = field(default_factory=datetime.now)
    token_saved: int = 0  # 节省的 token 数


@dataclass
class InternalizationResult:
    """内化结果"""
    internalized: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    removed_from_index: List[str] = field(default_factory=list)


class KnowledgeInternalizer:
    """
    知识内化器
    
    特性:
    - 将高频使用的显性经验内化为系统提示词中的简洁规则
    - 高频经验零检索成本
    - 系统提示词 Token 消耗降低 30-50%
    
    论文: ELL Framework (arXiv 2508.19005)
    """
    
    def __init__(
        self,
        internalization_threshold: int = INTERNALIZATION_THRESHOLD,
        max_rules: int = MAX_INTERNALIZED_RULES,
        skill_manager: Optional[Any] = None,
        rules_file: Optional[Path] = None,
    ):
        self.threshold = internalization_threshold
        self.max_rules = max_rules
        self.skill_manager = skill_manager
        
        self.rules_file = rules_file or Path.home() / ".openhands" / "internalized_rules.json"
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._rules: Dict[str, InternalizedRule] = {}
        self._load_rules()
    
    def _load_rules(self):
        """加载内化规则"""
        if self.rules_file.exists():
            try:
                data = json.loads(self.rules_file.read_text())
                for rule_data in data.get("rules", []):
                    rule = InternalizedRule(
                        rule_id=rule_data["rule_id"],
                        rule=rule_data["rule"],
                        source_skill=rule_data["source_skill"],
                        usage_count=rule_data["usage_count"],
                        internalized_at=datetime.fromisoformat(rule_data["internalized_at"]),
                        token_saved=rule_data.get("token_saved", 0),
                    )
                    self._rules[rule.rule_id] = rule
            except Exception as e:
                logger.warning(f"Failed to load internalized rules: {e}")
    
    def _save_rules(self):
        """保存内化规则"""
        data = {
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "rule": r.rule,
                    "source_skill": r.source_skill,
                    "usage_count": r.usage_count,
                    "internalized_at": r.internalized_at.isoformat(),
                    "token_saved": r.token_saved,
                }
                for r in self._rules.values()
            ],
            "updated_at": datetime.now().isoformat(),
        }
        self.rules_file.write_text(json.dumps(data, indent=2))
    
    def check_and_internalize(
        self,
        skill_name: str,
        usage_count: int,
        skill_content: str,
    ) -> Optional[InternalizedRule]:
        """检查并内化技能"""
        if usage_count < self.threshold:
            return None
        
        if len(self._rules) >= self.max_rules:
            # 移除使用最少的规则
            self._evict_lowest_usage_rule()
        
        # 提取核心规则
        core_rule = self._extract_core_rule(skill_name, skill_content)
        if not core_rule:
            return None
        
        import uuid
        rule = InternalizedRule(
            rule_id=str(uuid.uuid4())[:8],
            rule=core_rule,
            source_skill=skill_name,
            usage_count=usage_count,
            token_saved=self._estimate_token_savings(skill_content, core_rule),
        )
        
        self._rules[rule.rule_id] = rule
        self._save_rules()
        
        logger.info(f"Internalized skill '{skill_name}' as rule: {core_rule[:50]}...")
        
        return rule
    
    def _extract_core_rule(self, skill_name: str, content: str) -> Optional[str]:
        """提取核心规则"""
        # 从技能内容中提取最核心的 1-3 条规则
        
        # 查找 Pitfalls 部分
        pitfalls = self._extract_section(content, "Pitfalls")
        if pitfalls:
            # 取第一个 pitfall 作为规则
            for line in pitfalls.split("\n"):
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    return line[2:]
        
        # 查找 Steps 部分
        steps = self._extract_section(content, "Steps")
        if steps:
            # 取第一个步骤作为规则
            for line in steps.split("\n"):
                line = line.strip()
                if re.match(r'^\d+\.\s', line):
                    return re.sub(r'^\d+\.\s', '', line)
        
        # 使用技能名称生成规则
        return f"Follow best practices for {skill_name}"
    
    def _extract_section(self, content: str, section_name: str) -> Optional[str]:
        """提取章节内容"""
        import re
        pattern = rf'## {section_name}\n(.*?)(?=\n## |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    def _estimate_token_savings(self, skill_content: str, rule: str) -> int:
        """估算节省的 token 数"""
        # 粗略估算：技能内容 token - 规则 token
        skill_tokens = len(skill_content) // 4
        rule_tokens = len(rule) // 4
        return max(0, skill_tokens - rule_tokens)
    
    def _evict_lowest_usage_rule(self):
        """淘汰使用最少的规则"""
        if not self._rules:
            return
        
        lowest_rule = min(self._rules.values(), key=lambda r: r.usage_count)
        del self._rules[lowest_rule.rule_id]
        self._save_rules()
    
    def get_internalized_prompt(self) -> str:
        """获取内化规则的系统提示词"""
        if not self._rules:
            return ""
        
        lines = ["## Internalized Best Practices\n"]
        lines.append("These rules have been learned from experience and should be followed automatically:\n")
        
        for rule in sorted(self._rules.values(), key=lambda r: r.usage_count, reverse=True):
            lines.append(f"- {rule.rule}")
        
        return "\n".join(lines)
    
    def get_rules_for_context(self, context: str) -> List[InternalizedRule]:
        """获取与上下文相关的规则"""
        relevant = []
        context_lower = context.lower()
        
        for rule in self._rules.values():
            # 简单的关键词匹配
            if any(kw in context_lower for kw in rule.rule.lower().split()[:5]):
                relevant.append(rule)
        
        return relevant
    
    def record_rule_usage(self, rule_id: str):
        """记录规则使用"""
        if rule_id in self._rules:
            self._rules[rule_id].usage_count += 1
            self._save_rules()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_token_saved = sum(r.token_saved for r in self._rules.values())
        
        return {
            "total_rules": len(self._rules),
            "max_rules": self.max_rules,
            "threshold": self.threshold,
            "total_token_saved": total_token_saved,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "rule": r.rule[:50],
                    "source": r.source_skill,
                    "usage": r.usage_count,
                }
                for r in self._rules.values()
            ],
        }


knowledge_internalizer = KnowledgeInternalizer()


import re
