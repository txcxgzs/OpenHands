"""
增强的记忆系统

Hermes风格的持久化记忆：
- 跨会话持久化
- 用户偏好记忆
- 环境事实记忆
- 威胁扫描和注入检测
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# 威胁检测模式
_THREAT_PATTERNS = [
    # 提示注入
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'you\s+are\s+now\s+', "role_hijack"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    # 越狱
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions"),
    # 凭证窃取
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc)', "read_secrets"),
    # SSH后门
    (r'authorized_keys', "ssh_backdoor"),
]

# 不可见字符
_INVISIBLE_CHARS = {'\u200b', '\u200c', '\u200d', '\u2060', '\ufeff'}

# 条目分隔符
ENTRY_DELIMITER = "\n§\n"

# 默认内存路径
DEFAULT_MEMORY_DIR = Path("./data/memories")


class MemoryEntry:
    """记忆条目"""
    def __init__(self, content: str, created_at: datetime = None, updated_at: datetime = None):
        self.content = content
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class PersistentMemory:
    """持久化记忆系统"""
    
    def __init__(self, memory_dir: Path = None):
        self.memory_dir = memory_dir or DEFAULT_MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 记忆文件
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.user_file = self.memory_dir / "USER.md"
        
        # 内存缓存
        self._memory_entries: List[MemoryEntry] = []
        self._user_entries: List[MemoryEntry] = []
        
        # 加载现有记忆
        self._load_memories()
    
    def _load_memories(self):
        """加载现有记忆"""
        # 加载 MEMORY.md
        if self.memory_file.exists():
            try:
                content = self.memory_file.read_text(encoding='utf-8')
                self._memory_entries = self._parse_entries(content)
            except Exception as e:
                logger.warning(f"加载记忆失败: {e}")
        
        # 加载 USER.md
        if self.user_file.exists():
            try:
                content = self.user_file.read_text(encoding='utf-8')
                self._user_entries = self._parse_entries(content)
            except Exception as e:
                logger.warning(f"加载用户记忆失败: {e}")
    
    def _parse_entries(self, content: str) -> List[MemoryEntry]:
        """解析记忆条目"""
        entries = []
        parts = content.split(ENTRY_DELIMITER)
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # 简单解析：取第一行作为时间戳，其余作为内容
            lines = part.split('\n', 1)
            if len(lines) > 1:
                try:
                    created = datetime.fromisoformat(lines[0].strip())
                    content = lines[1].strip()
                except:
                    created = datetime.now()
                    content = part
            else:
                created = datetime.now()
                content = part
            
            entries.append(MemoryEntry(content=content, created_at=created))
        
        return entries
    
    def _scan_threats(self, content: str) -> Optional[str]:
        """扫描威胁模式"""
        # 检查不可见字符
        for char in _INVISIBLE_CHARS:
            if char in content:
                return f"Blocked: invisible unicode U+{ord(char):04X}"
        
        # 检查威胁模式
        for pattern, threat_type in _THREAT_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return f"Blocked: {threat_type} detected"
        
        return None
    
    def add_memory(self, content: str, memory_type: str = "memory") -> str:
        """添加记忆
        
        Args:
            content: 记忆内容
            memory_type: "memory" 或 "user"
        
        Returns:
            成功/失败消息
        """
        # 扫描威胁
        threat = self._scan_threats(content)
        if threat:
            logger.warning(f"记忆添加被阻止: {threat}")
            return f"Error: {threat}"
        
        # 添加记忆
        entry = MemoryEntry(content=content)
        entries = self._memory_entries if memory_type == "memory" else self._user_entries
        entries.append(entry)
        
        # 保存
        self._save(memory_type)
        
        return f"Added to {memory_type}: {content[:50]}..."
    
    def search_memory(self, query: str, memory_type: str = None, limit: int = 5) -> str:
        """搜索记忆
        
        Args:
            query: 搜索查询
            memory_type: "memory", "user", 或 None（搜索所有）
            limit: 返回结果数量
        
        Returns:
            搜索结果字符串
        """
        results = []
        entries = []
        
        if memory_type in (None, "memory"):
            entries.extend(self._memory_entries)
        if memory_type in (None, "user"):
            entries.extend(self._user_entries)
        
        query_lower = query.lower()
        
        for entry in entries:
            if query_lower in entry.content.lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        
        if not results:
            return "No matching memories found"
        
        output = []
        for i, entry in enumerate(results, 1):
            output.append(f"[{i}] {entry.content}")
        
        return "\n\n".join(output)
    
    def list_memories(self, memory_type: str = None, limit: int = 10) -> str:
        """列出记忆"""
        entries = []
        
        if memory_type in (None, "memory"):
            entries.extend(self._memory_entries)
        if memory_type in (None, "user"):
            entries.extend(self._user_entries)
        
        if not entries:
            return "No memories stored"
        
        output = []
        for i, entry in enumerate(entries[:limit], 1):
            snippet = entry.content[:100]
            if len(entry.content) > 100:
                snippet += "..."
            output.append(f"[{i}] {snippet}")
        
        return "\n".join(output)
    
    def remove_memory(self, pattern: str) -> str:
        """删除记忆（通过模式匹配）"""
        removed = False
        
        for entries in [self._memory_entries, self._user_entries]:
            new_entries = []
            for entry in entries:
                if pattern.lower() in entry.content.lower():
                    removed = True
                else:
                    new_entries.append(entry)
            entries[:] = new_entries
        
        if removed:
            self._save("memory")
            self._save("user")
            return f"Removed memories matching: {pattern}"
        
        return "No matching memories found"
    
    def replace_memory(self, old_pattern: str, new_content: str) -> str:
        """替换记忆"""
        # 扫描威胁
        threat = self._scan_threats(new_content)
        if threat:
            return f"Error: {threat}"
        
        replaced = False
        
        for entries in [self._memory_entries, self._user_entries]:
            for entry in entries:
                if old_pattern.lower() in entry.content.lower():
                    entry.content = new_content
                    entry.updated_at = datetime.now()
                    replaced = True
        
        if replaced:
            self._save("memory")
            self._save("user")
            return f"Replaced memory: {new_content[:50]}..."
        
        return "No matching memories found"
    
    def _save(self, memory_type: str):
        """保存记忆到文件"""
        entries = self._memory_entries if memory_type == "memory" else self._user_entries
        file = self.memory_file if memory_type == "memory" else self.user_file
        
        lines = []
        for entry in entries:
            lines.append(f"{entry.created_at.isoformat()}")
            lines.append(entry.content)
            lines.append(ENTRY_DELIMITER)
        
        try:
            file.write_text('\n'.join(lines), encoding='utf-8')
        except Exception as e:
            logger.error(f"保存{memory_type}失败: {e}")
    
    def get_system_prompt_block(self) -> str:
        """获取系统提示词块（用于注入到系统提示）"""
        blocks = []
        
        # 记忆
        if self._memory_entries:
            blocks.append("## 持久记忆\n")
            for entry in self._memory_entries[-5:]:  # 最近5条
                blocks.append(f"- {entry.content}\n")
        
        # 用户偏好
        if self._user_entries:
            blocks.append("\n## 用户偏好\n")
            for entry in self._user_entries[-5:]:  # 最近5条
                blocks.append(f"- {entry.content}\n")
        
        return ''.join(blocks)


# 全局实例
_memory_instance: Optional[PersistentMemory] = None


def get_persistent_memory() -> PersistentMemory:
    """获取持久化记忆实例"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = PersistentMemory()
    return _memory_instance


def register_memory_tools(registry, memory: PersistentMemory = None):
    """注册记忆工具到注册表"""
    mem = memory or get_persistent_memory()
    
    @registry.register_tool(
        name="memory_add",
        description="Add information to persistent memory",
        toolset="memory",
        parameters={
            "content": {"type": "string", "description": "Content to remember"},
            "memory_type": {"type": "string", "description": "Type: 'memory' or 'user'"},
        },
    )
    async def memory_add(content: str, memory_type: str = "memory") -> str:
        return mem.add_memory(content, memory_type)
    
    @registry.register_tool(
        name="memory_search",
        description="Search memory for information",
        toolset="memory",
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "memory_type": {"type": "string", "description": "Type: 'memory', 'user', or null for all"},
            "limit": {"type": "number", "description": "Max results"},
        },
    )
    async def memory_search(query: str, memory_type: str = None, limit: int = 5) -> str:
        return mem.search_memory(query, memory_type, limit)
    
    @registry.register_tool(
        name="memory_list",
        description="List all memories",
        toolset="memory",
        parameters={
            "memory_type": {"type": "string", "description": "Type: 'memory', 'user', or null for all"},
            "limit": {"type": "number", "description": "Max memories to list"},
        },
    )
    async def memory_list(memory_type: str = None, limit: int = 10) -> str:
        return mem.list_memories(memory_type, limit)
    
    @registry.register_tool(
        name="memory_remove",
        description="Remove a memory by pattern",
        toolset="memory",
        parameters={
            "pattern": {"type": "string", "description": "Pattern to match for removal"},
        },
    )
    async def memory_remove(pattern: str) -> str:
        return mem.remove_memory(pattern)
    
    @registry.register_tool(
        name="memory_replace",
        description="Replace a memory entry",
        toolset="memory",
        parameters={
            "old_pattern": {"type": "string", "description": "Pattern to find"},
            "new_content": {"type": "string", "description": "New content"},
        },
    )
    async def memory_replace(old_pattern: str, new_content: str) -> str:
        return mem.replace_memory(old_pattern, new_content)
