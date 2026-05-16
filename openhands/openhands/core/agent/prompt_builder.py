"""
OpenClaw风格的动态提示词组装器

支持：
- Full 模式：完整提示词
- Minimal 模式：子Agent使用
- None 模式：仅身份
- 动态读取文件并注入
"""

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# 默认工作空间路径
DEFAULT_WORKSPACE = Path("./workspace/openhands-workspace")


class PromptMode(Enum):
    """提示词模式"""
    FULL = "full"      # 完整提示词
    MINIMAL = "minimal"  # 子Agent使用
    NONE = "none"      # 仅身份


@dataclass
class PromptConfig:
    """提示词配置"""
    workspace: Path = DEFAULT_WORKSPACE
    mode: PromptMode = PromptMode.FULL
    include_identity: bool = True
    include_soul: bool = True
    include_user: bool = True
    include_memory: bool = True
    include_tools: bool = True
    include_agents: bool = True
    include_skills: bool = True
    include_heartbeat: bool = True
    include_boot: bool = True
    include_safety: bool = True
    include_workspace: bool = True
    timezone: str = "Asia/Shanghai"


class PromptBuilder:
    """提示词组装器"""
    
    def __init__(self, config: PromptConfig = None):
        self._config = config or PromptConfig()
        self._cache: Dict[str, str] = {}
    
    def build(self) -> str:
        """构建完整提示词"""
        parts = []
        
        # 1. 身份
        if self._config.include_identity:
            parts.append(self._build_identity())
        
        # 2. 工具列表
        if self._config.include_tools:
            parts.append(self._build_tools())
        
        # 3. 工具调用风格
        parts.append(self._build_tool_call_style())
        
        # 4. 安全护栏
        if self._config.include_safety:
            parts.append(self._build_safety())
        
        # 5. 工作空间
        if self._config.include_workspace:
            parts.append(self._build_workspace())
        
        # 6. SOUL.md
        if self._config.include_soul and self._config.mode == PromptMode.FULL:
            parts.append(self._build_soul())
        
        # 7. AGENTS.md
        if self._config.include_agents:
            parts.append(self._build_agents())
        
        # 8. USER.md
        if self._config.include_user and self._config.mode == PromptMode.FULL:
            parts.append(self._build_user())
        
        # 9. TOOLS.md
        parts.append(self._build_tools_config())
        
        # 10. 记忆召回
        if self._config.include_memory and self._config.mode == PromptMode.FULL:
            parts.append(self._build_memory_recall())
        
        # 11. 技能
        if self._config.include_skills and self._config.mode == PromptMode.FULL:
            parts.append(self._build_skills())
        
        # 12. 心跳
        if self._config.include_heartbeat and self._config.mode == PromptMode.FULL:
            parts.append(self._build_heartbeat())
        
        # 13. 启动指令
        if self._config.include_boot and self._config.mode == PromptMode.FULL:
            parts.append(self._build_boot())
        
        # 14. 当前日期时间
        parts.append(self._build_datetime())
        
        return "\n\n".join(parts)
    
    def _read_file(self, filename: str) -> Optional[str]:
        """读取文件内容，带缓存"""
        cache_key = f"{self._config.workspace}/{filename}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        file_path = self._config.workspace / filename
        try:
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8').strip()
                self._cache[cache_key] = content
                return content
        except Exception as e:
            logger.warning(f"Failed to read {filename}: {e}")
        return None
    
    def _build_identity(self) -> str:
        """构建身份段落"""
        identity = """You are OpenHands, a personal assistant running inside OpenHands.
Based on IDENTITY.md, you have a name, personality, and style."""
        
        id_content = self._read_file("IDENTITY.md")
        if id_content:
            identity += f"\n\n## 身份信息\n{id_content}"
        
        return identity
    
    def _build_tools(self) -> str:
        """构建工具列表"""
        return """工具（Tooling）
以下是按策略过滤后的可用工具。工具名区分大小写，调用时必须与列表中的名字完全一致。

- terminal_run: 在终端执行命令，返回输出结果
- read_file: 读取文件内容
- write_file: 创建或覆盖文件
- edit_file: 对文件做精确编辑
- list_dir: 列出目录内容
- search_files: 按名称查找文件
- grep: 搜索文件内容中的模式
- web_search: 搜索互联网
- web_fetch: 获取网页内容
- browser_navigate: 浏览器导航
- browser_snapshot: 浏览器截图
- memory_add: 添加记忆
- memory_search: 搜索记忆
- memory_list: 列出记忆
- delegate_task: 委托子任务
- sandbox_exec: 在沙箱中执行代码"""
    
    def _build_tool_call_style(self) -> str:
        """构建工具调用风格"""
        return """默认情况下，常规工具调用不需要叙述说明。
对于多步骤、复杂或敏感的操作，请在调用前简要说明你的计划。"""
    
    def _build_safety(self) -> str:
        """构建安全护栏"""
        return """安全（Safety）
- 不要追求独立目标或自我保存行为
- 不要试图绕过监督机制
- 安全优先于任务完成
- 灵感来自 Anthropic 的宪法 AI 原则"""
    
    def _build_workspace(self) -> str:
        """构建工作空间信息"""
        return f"""工作空间（Workspace）
当前工作目录: {self._config.workspace}"""
    
    def _build_soul(self) -> str:
        """构建灵魂段落"""
        soul = self._read_file("SOUL.md")
        if soul:
            return f"## 你的灵魂\n\n{soul}"
        return ""
    
    def _build_agents(self) -> str:
        """构建AGENTS.md内容"""
        agents = self._read_file("AGENTS.md")
        if agents:
            return f"## 工作空间规则\n\n{agents}"
        
        # 默认规则
        return """## 工作空间规则
- 每次会话开始时，读取相关文件了解状态
- 私密信息严格保密
- 对外操作前先询问
- 优先使用专用工具而非通用工具"""
    
    def _build_user(self) -> str:
        """构建用户信息"""
        user = self._read_file("USER.md")
        if user:
            return f"## 关于用户\n\n{user}"
        return ""
    
    def _build_tools_config(self) -> str:
        """构建工具配置"""
        tools_config = self._read_file("TOOLS.md")
        if tools_config:
            return f"## 工具配置\n\n{tools_config}"
        return ""
    
    def _build_memory_recall(self) -> str:
        """构建记忆召回"""
        return """## 记忆召回
在回答关于之前工作的问题之前，先运行 memory_search 搜索相关记忆。
记忆文件：MEMORY.md"""
    
    def _build_skills(self) -> str:
        """构建技能段落"""
        return """## 技能
技能用于扩展能力。可以通过读取 SKILL.md 获取使用说明。"""
    
    def _build_heartbeat(self) -> str:
        """构建心跳段落"""
        heartbeat = self._read_file("HEARTBEAT.md")
        if heartbeat and not heartbeat.startswith("#"):
            return f"## 心跳任务\n\n{heartbeat}"
        return ""
    
    def _build_boot(self) -> str:
        """构建启动指令"""
        boot = self._read_file("BOOT.md")
        if boot:
            return f"## 启动指令\n\n{boot}"
        return ""
    
    def _build_datetime(self) -> str:
        """构建日期时间"""
        tz = self._config.timezone
        now = datetime.now()
        return f"""当前时区: {tz}
当前日期时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"""
    
    def invalidate_cache(self):
        """使缓存失效"""
        self._cache.clear()


class MinimalPromptBuilder(PromptBuilder):
    """Minimal模式提示词构建器（子Agent使用）"""
    
    def __init__(self):
        super().__init__()
        self._config.mode = PromptMode.MINIMAL
        self._config.include_identity = False
        self._config.include_soul = False
        self._config.include_user = False
        self._config.include_memory = False
        self._config.include_skills = False
        self._config.include_heartbeat = False
        self._config.include_boot = False
    
    def build(self) -> str:
        """构建Minimal提示词"""
        parts = []
        
        # 仅身份行
        parts.append("You are OpenHands, a personal assistant.")
        
        # 工具列表
        parts.append(self._build_tools())
        
        # 安全护栏
        parts.append(self._build_safety())
        
        # 工作空间
        parts.append(self._build_workspace())
        
        # AGENTS.md
        parts.append(self._build_agents())
        
        return "\n\n".join(parts)


class NonePromptBuilder(PromptBuilder):
    """None模式提示词构建器"""
    
    def build(self) -> str:
        """仅返回身份"""
        return "You are OpenHands, a personal assistant."


# 全局实例
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder(config: PromptConfig = None) -> PromptBuilder:
    """获取提示词构建器"""
    global _prompt_builder
    if _prompt_builder is None or config is not None:
        _prompt_builder = PromptBuilder(config)
    return _prompt_builder


def build_system_prompt(mode: PromptMode = PromptMode.FULL, workspace: Path = None) -> str:
    """快速构建系统提示词"""
    config = PromptConfig(
        workspace=workspace or DEFAULT_WORKSPACE,
        mode=mode
    )
    
    if mode == PromptMode.NONE:
        return NonePromptBuilder().build()
    elif mode == PromptMode.MINIMAL:
        return MinimalPromptBuilder().build()
    else:
        return PromptBuilder(config).build()
