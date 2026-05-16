"""
完整的持久化记忆系统 - 100%对齐Hermes

功能：
- MEMORY.md持久化记忆
- USER.md用户偏好
- 安全的威胁扫描
- 记忆CRUD操作
- 搜索和替换
- 系统提示集成
"""

import logging
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from datetime import datetime

from openhands.core.security import (
    get_security_guard,
    SecurityCheckResult
)

logger = logging.getLogger(__name__)

# 默认记忆目录
DEFAULT_MEMORY_DIR = Path("./data/memories")

# 记忆文件名
MEMORY_FILENAME = "MEMORY.md"
USER_FILENAME = "USER.md"

# 条目分隔符
ENTRY_DELIMITER = "\n§\n"


@dataclass
class MemoryEntry:
    """记忆条目"""
    content: str
    created_at: str
    updated_at: str
    
    @classmethod
    def create(cls, content: str) -> 'MemoryEntry':
        now = datetime.now().isoformat()
        return cls(content=content, created_at=now, updated_at=now)
    
    def update_content(self, new_content: str) -> 'MemoryEntry':
        self.content = new_content
        self.updated_at = datetime.now().isoformat()
        return self
    
    def to_line_format(self) -> str:
        return f"{self.created_at}\n{self.content}"


class PersistentMemory:
    """持久化记忆系统"""
    
    def __init__(self, memory_dir: Path = None):
        self._memory_dir = memory_dir or DEFAULT_MEMORY_DIR
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件路径
        self._memory_file = self._memory_dir / MEMORY_FILENAME
        self._user_file = self._memory_dir / USER_FILENAME
        
        # 内存缓存
        self._memory_entries: List[MemoryEntry] = []
        self._user_entries: List[MemoryEntry] = []
        self._silent_mode: bool = False
        
        # 加载
        self._load_all()
    
    def _load_all(self):
        """加载所有记忆"""
        if self._memory_file.exists():
            try:
                self._memory_entries = self._parse_from_file(self._memory_file)
            except Exception as e:
                logger.warning(f"Failed to load memory: {e}")
        
        if self._user_file.exists():
            try:
                self._user_entries = self._parse_from_file(self._user_file)
            except Exception as e:
                logger.warning(f"Failed to load user preferences: {e}")
    
    def _parse_from_file(self, file: Path) -> List[MemoryEntry]:
        """从文件解析"""
        entries: List[MemoryEntry] = []
        content = file.read_text(encoding='utf-8')
        
        if not content.strip():
            return entries
        
        parts = content.split(ENTRY_DELIMITER)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            lines = part.split('\n', 1)
            if len(lines) == 2:
                created_at_str = lines[0].strip()
                entry_content = lines[1].strip()
                
                try:
                    datetime.fromisoformat(created_at_str)
                    entries.append(MemoryEntry(
                        content=entry_content,
                        created_at=created_at_str,
                        updated_at=created_at_str
                    ))
                except:
                    entries.append(MemoryEntry.create(part))
            else:
                entries.append(MemoryEntry.create(part))
        
        return entries
    
    def _save_to_file(self, file: Path, entries: List[MemoryEntry]):
        """保存到文件"""
        if not entries:
            if file.exists():
                file.unlink()
            return
        
        lines = []
        for entry in entries:
            lines.append(entry.to_line_format())
            lines.append(ENTRY_DELIMITER)
        
        content = '\n'.join(lines)
        file.write_text(content, encoding='utf-8')
    
    def add_memory(self, content: str, is_user: bool = False) -> str:
        """添加记忆"""
        guard = get_security_guard()
        check = guard.validate_memory_write(content)
        
        if not check.is_safe:
            return f"Error: Detected threats: {', '.join(check.threats)}"
        
        sanitized_content = check.sanitized_text or content
        entry = MemoryEntry.create(sanitized_content)
        
        if is_user:
            self._user_entries.append(entry)
            self._save_to_file(self._user_file, self._user_entries)
            msg = f"Added to USER.md: {sanitized_content[:100]}"
        else:
            self._memory_entries.append(entry)
            self._save_to_file(self._memory_file, self._memory_entries)
            msg = f"Added to MEMORY.md: {sanitized_content[:100]}"
        
        if len(sanitized_content) > 100:
            msg += "..."
        
        if not self._silent_mode:
            return msg
        return ""
    
    def add_user(self, content: str) -> str:
        """添加用户偏好"""
        return self.add_memory(content, is_user=True)
    
    def search_memory(self, query: str, is_user: bool = None) -> str:
        """搜索记忆"""
        entries = self._get_all_entries(is_user)
        query_lower = query.lower()
        matches = []
        
        for entry in entries:
            if query_lower in entry.content.lower():
                matches.append(entry.content)
        
        if not matches:
            return "No matching memories found"
        
        if len(matches) <= 5:
            return "\n\n".join(matches)
        else:
            head = matches[:3]
            tail = matches[-2:]
            result = "\n\n".join(head)
            result += f"\n\n[... and {len(matches) - 5} more ...]\n\n"
            result += "\n\n".join(tail)
            return result
    
    def list_memory(self, is_user: bool = None, limit: int = 10) -> str:
        """列出记忆"""
        entries = self._get_all_entries(is_user)
        if not entries:
            return "No memories stored"
        
        result = []
        for entry in entries[-limit:]:
            snippet = entry.content[:100]
            if len(entry.content) > 100:
                snippet += "..."
            result.append(f"- {snippet}")
        
        return "\n".join(result)
    
    def remove_memory(self, pattern: str) -> str:
        """移除记忆"""
        removed = []
        removed.extend(self._remove_from_list(self._memory_entries, pattern))
        removed.extend(self._remove_from_list(self._user_entries, pattern))
        
        if removed:
            self._save_to_file(self._memory_file, self._memory_entries)
            self._save_to_file(self._user_file, self._user_entries)
            return f"Removed {len(removed)} matching memories"
        return "No matching memories found"
    
    def remove_all_memories(self) -> str:
        """移除所有记忆"""
        self._memory_entries.clear()
        self._user_entries.clear()
        self._save_to_file(self._memory_file, [])
        self._save_to_file(self._user_file, [])
        return "Removed all memories"
    
    def replace_memory(self, old: str, new: str) -> str:
        """替换记忆"""
        guard = get_security_guard()
        check = guard.validate_memory_write(new)
        
        if not check.is_safe:
            return f"Error: Detected threats: {', '.join(check.threats)}"
        
        new_sanitized = check.sanitized_text or new
        old_lower = old.lower()
        
        replaced = 0
        for entries in [self._memory_entries, self._user_entries]:
            for entry in entries:
                if old_lower in entry.content.lower():
                    entry.update_content(new_sanitized)
                    replaced += 1
        
        if replaced > 0:
            self._save_to_file(self._memory_file, self._memory_entries)
            self._save_to_file(self._user_file, self._user_entries)
            return f"Replaced {replaced} matching memories"
        
        return "No matching memories found"
    
    def toggle_silence(self) -> str:
        """切换静默模式"""
        self._silent_mode = not self._silent_mode
        return f"Silence {'enabled' if self._silent_mode else 'disabled'}"
    
    def get_system_prompt_segment(self) -> str:
        """获取系统提示片段"""
        segments = []
        
        if self._memory_entries:
            segments.append("## Persistent memory - MEMORY.md\n")
            for entry in self._memory_entries[-8:]:
                segments.append(f"- {entry.content}\n")
        
        if self._user_entries:
            segments.append("\n## User preferences - USER.md\n")
            for entry in self._user_entries[-8:]:
                segments.append(f"- {entry.content}\n")
        
        return ''.join(segments)
    
    def _get_all_entries(self, is_user: bool = None) -> List[MemoryEntry]:
        """获取所有条目"""
        if is_user is True:
            return self._user_entries
        elif is_user is False:
            return self._memory_entries
        else:
            return self._memory_entries + self._user_entries
    
    def _remove_from_list(self, entries: List[MemoryEntry], pattern: str) -> List[str]:
        """从列表移除"""
        pattern_lower = pattern.lower()
        removed_content = []
        new_entries = []
        
        for entry in entries:
            if pattern_lower in entry.content.lower():
                removed_content.append(entry.content)
            else:
                new_entries.append(entry)
        
        entries[:] = new_entries
        return removed_content


# 全局记忆实例
_memory_instance: Optional[PersistentMemory] = None


def get_persistent_memory(memory_dir: Path = None) -> PersistentMemory:
    """获取持久化记忆"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = PersistentMemory(memory_dir)
    return _memory_instance
