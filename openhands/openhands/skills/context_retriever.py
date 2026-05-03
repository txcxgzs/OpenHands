"""
Context-Adaptive Reuse - 上下文自适应经验复用
参考 ReMe (arXiv 2512.10696) 和 CER (ACL 2025)
"""

from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging
import json
import re

logger = logging.getLogger(__name__)


@dataclass
class TaskContext:
    """任务上下文"""
    goal: str
    tools_used: Set[str] = field(default_factory=set)
    error_patterns: List[str] = field(default_factory=list)
    project_type: Optional[str] = None
    environment: Optional[str] = None
    keywords: List[str] = field(default_factory=list)


@dataclass
class SkillTrigger:
    """技能触发器"""
    tool_combinations: List[Set[str]] = field(default_factory=list)
    error_patterns: List[str] = field(default_factory=list)
    project_types: List[str] = field(default_factory=list)
    environments: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    """检索结果"""
    skill_name: str
    relevance_score: float
    match_reasons: List[str]
    matched_triggers: List[str]


class ContextAnalyzer:
    """上下文分析器"""
    
    PROJECT_PATTERNS = {
        "python": ["setup.py", "requirements.txt", "pyproject.toml", ".py"],
        "nodejs": ["package.json", "node_modules", ".js", ".ts"],
        "java": ["pom.xml", "build.gradle", ".java"],
        "go": ["go.mod", ".go"],
        "rust": ["Cargo.toml", ".rs"],
        "flask": ["app.py", "flask", "FLASK_APP"],
        "django": ["settings.py", "django", "manage.py"],
        "fastapi": ["fastapi", "APIRouter"],
        "react": ["react", "jsx", "tsx", "component"],
        "kubernetes": ["kubectl", "deployment.yaml", "k8s", "kubernetes"],
        "docker": ["Dockerfile", "docker-compose", "docker"],
    }
    
    ENVIRONMENT_PATTERNS = {
        "linux": ["linux", "ubuntu", "debian", "centos"],
        "windows": ["windows", "win32", "cmd", "powershell"],
        "macos": ["macos", "darwin", "osx"],
        "docker": ["docker", "container"],
        "kubernetes": ["kubernetes", "k8s", "kubectl"],
        "cloud": ["aws", "gcp", "azure", "cloud"],
    }
    
    def analyze(self, context: TaskContext) -> Dict[str, Any]:
        """分析上下文"""
        return {
            "project_type": self._detect_project_type(context),
            "environment": self._detect_environment(context),
            "tool_patterns": self._extract_tool_patterns(context),
            "error_patterns": self._extract_error_patterns(context),
            "keywords": self._extract_keywords(context),
        }
    
    def _detect_project_type(self, context: TaskContext) -> Optional[str]:
        """检测项目类型"""
        text = context.goal.lower()
        for proj_type, patterns in self.PROJECT_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in text:
                    return proj_type
        return None
    
    def _detect_environment(self, context: TaskContext) -> Optional[str]:
        """检测环境"""
        text = context.goal.lower()
        for env, patterns in self.ENVIRONMENT_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in text:
                    return env
        return None
    
    def _extract_tool_patterns(self, context: TaskContext) -> List[str]:
        """提取工具模式"""
        return list(context.tools_used)
    
    def _extract_error_patterns(self, context: TaskContext) -> List[str]:
        """提取错误模式"""
        return context.error_patterns
    
    def _extract_keywords(self, context: TaskContext) -> List[str]:
        """提取关键词"""
        keywords = []
        words = re.findall(r'\b[a-zA-Z]{3,}\b', context.goal.lower())
        stop_words = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was", "one", "our", "out"}
        for word in words:
            if word not in stop_words:
                keywords.append(word)
        return keywords[:10]


class ContextAwareRetriever:
    """
    上下文自适应检索器
    
    特性:
    - 基于当前任务上下文检索最相关的经验
    - 工具组合匹配
    - 错误模式匹配
    - 项目类型匹配
    - 环境特征匹配
    """
    
    def __init__(self, skill_manager: Optional[Any] = None):
        self.skill_manager = skill_manager
        self.context_analyzer = ContextAnalyzer()
        self._skill_triggers: Dict[str, SkillTrigger] = {}
    
    def register_skill_trigger(self, skill_name: str, trigger: SkillTrigger):
        """注册技能触发器"""
        self._skill_triggers[skill_name] = trigger
    
    def retrieve(self, context: TaskContext, top_k: int = 3) -> List[RetrievalResult]:
        """检索相关技能"""
        if not self.skill_manager:
            return []
        
        analysis = self.context_analyzer.analyze(context)
        results = []
        
        skills = self.skill_manager.list_skills()
        
        for skill in skills:
            result = self._score_skill(skill, context, analysis)
            if result.relevance_score > 0:
                results.append(result)
        
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:top_k]
    
    def _score_skill(
        self,
        skill: Any,
        context: TaskContext,
        analysis: Dict[str, Any],
    ) -> RetrievalResult:
        """计算技能相关性分数"""
        score = 0.0
        reasons = []
        matched_triggers = []
        
        skill_name = skill.name.lower()
        description = getattr(skill, 'description', '').lower()
        when_to_use = getattr(skill, 'when_to_use', [])
        
        # 1. 工具组合匹配
        tool_score = self._match_tool_combinations(skill_name, context.tools_used)
        if tool_score > 0:
            score += tool_score * 0.3
            reasons.append(f"Tool pattern matched")
            matched_triggers.append("tools")
        
        # 2. 错误模式匹配
        error_score = self._match_error_patterns(skill_name, context.error_patterns)
        if error_score > 0:
            score += error_score * 0.25
            reasons.append(f"Error pattern matched")
            matched_triggers.append("errors")
        
        # 3. 项目类型匹配
        if analysis.get("project_type"):
            proj_score = self._match_project_type(skill_name, analysis["project_type"])
            if proj_score > 0:
                score += proj_score * 0.2
                reasons.append(f"Project type matched: {analysis['project_type']}")
                matched_triggers.append("project")
        
        # 4. 环境匹配
        if analysis.get("environment"):
            env_score = self._match_environment(skill_name, analysis["environment"])
            if env_score > 0:
                score += env_score * 0.15
                reasons.append(f"Environment matched: {analysis['environment']}")
                matched_triggers.append("environment")
        
        # 5. 关键词匹配
        keyword_score = self._match_keywords(skill_name, description, analysis.get("keywords", []))
        if keyword_score > 0:
            score += keyword_score * 0.1
            reasons.append("Keywords matched")
            matched_triggers.append("keywords")
        
        return RetrievalResult(
            skill_name=skill.name,
            relevance_score=min(1.0, score),
            match_reasons=reasons,
            matched_triggers=matched_triggers,
        )
    
    def _match_tool_combinations(self, skill_name: str, tools_used: Set[str]) -> float:
        """匹配工具组合"""
        if not tools_used:
            return 0.0
        
        trigger = self._skill_triggers.get(skill_name)
        if trigger:
            for combo in trigger.tool_combinations:
                if combo.issubset(tools_used):
                    return 1.0
        
        # 从技能名称推断
        for tool in tools_used:
            if tool.lower() in skill_name:
                return 0.5
        
        return 0.0
    
    def _match_error_patterns(self, skill_name: str, error_patterns: List[str]) -> float:
        """匹配错误模式"""
        if not error_patterns:
            return 0.0
        
        trigger = self._skill_triggers.get(skill_name)
        if trigger:
            for pattern in trigger.error_patterns:
                for error in error_patterns:
                    if pattern.lower() in error.lower():
                        return 1.0
        
        return 0.0
    
    def _match_project_type(self, skill_name: str, project_type: str) -> float:
        """匹配项目类型"""
        if project_type.lower() in skill_name:
            return 1.0
        
        trigger = self._skill_triggers.get(skill_name)
        if trigger and project_type in trigger.project_types:
            return 1.0
        
        return 0.0
    
    def _match_environment(self, skill_name: str, environment: str) -> float:
        """匹配环境"""
        if environment.lower() in skill_name:
            return 1.0
        
        trigger = self._skill_triggers.get(skill_name)
        if trigger and environment in trigger.environments:
            return 1.0
        
        return 0.0
    
    def _match_keywords(self, skill_name: str, description: str, keywords: List[str]) -> float:
        """匹配关键词"""
        if not keywords:
            return 0.0
        
        matches = 0
        text = (skill_name + " " + description).lower()
        for keyword in keywords:
            if keyword in text:
                matches += 1
        
        return matches / len(keywords) if keywords else 0.0
    
    def build_inverted_index(self):
        """构建倒排索引"""
        if not self.skill_manager:
            return
        
        for skill in self.skill_manager.list_skills():
            trigger = SkillTrigger()
            
            # 从技能内容提取触发器
            skill_name = skill.name.lower()
            
            # 工具组合
            if "deploy" in skill_name:
                trigger.tool_combinations.append({"terminal", "write_file"})
            if "k8s" in skill_name or "kubernetes" in skill_name:
                trigger.tool_combinations.append({"terminal"})
                trigger.environments.append("kubernetes")
            if "docker" in skill_name:
                trigger.environments.append("docker")
            
            # 项目类型
            for proj_type in ContextAnalyzer.PROJECT_PATTERNS.keys():
                if proj_type in skill_name:
                    trigger.project_types.append(proj_type)
            
            self._skill_triggers[skill.name] = trigger


context_aware_retriever = ContextAwareRetriever()
