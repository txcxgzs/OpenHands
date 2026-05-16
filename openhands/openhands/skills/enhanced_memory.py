"""
Enhanced Memory System - 带容量管理的记忆系统
参考 Hermes Agent 的 Memory 设计
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import json
import hashlib
import logging
import re

logger = logging.getLogger(__name__)

MEMORY_LIMIT = 2200
USER_MEMORY_LIMIT = 1375
ENTRY_SEPARATOR = "§"


@dataclass
class MemoryEntry:
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_string(self) -> str:
        return f"[{self.timestamp.isoformat()}] {self.content}"
    
    @classmethod
    def from_string(cls, s: str) -> "MemoryEntry":
        match = re.match(r'\[(.*?)\] (.*)', s, re.DOTALL)
        if match:
            return cls(
                content=match.group(2),
                timestamp=datetime.fromisoformat(match.group(1)),
            )
        return cls(content=s)


class EnhancedMemoryStore:
    """
    增强版记忆存储 - 带容量管理
    参考 Hermes Agent 的 Memory 系统
    
    特性:
    1. 定量限制 - 强制信息压缩
    2. 超限处理 - 让模型自己整理
    3. 冻结快照 - 支持 Prefix Cache
    4. 分类存储 - Agent记忆 vs 用户画像
    """
    
    def __init__(
        self,
        memory_dir: Optional[Path] = None,
        memory_limit: int = MEMORY_LIMIT,
        user_memory_limit: int = USER_MEMORY_LIMIT,
    ):
        self.memory_dir = memory_dir or Path.home() / ".openhands" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.memory_limit = memory_limit
        self.user_memory_limit = user_memory_limit
        
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.user_file = self.memory_dir / "USER.md"
        
        self._memory_entries: List[MemoryEntry] = []
        self._user_entries: List[MemoryEntry] = []
        
        self._snapshot: Dict[str, str] = {}
        
        self._load_from_disk()
        self._capture_snapshot()
    
    def _load_from_disk(self):
        self._memory_entries = self._read_file(self.memory_file)
        self._user_entries = self._read_file(self.user_file)
    
    def _read_file(self, file_path: Path) -> List[MemoryEntry]:
        if not file_path.exists():
            return []
        
        content = file_path.read_text(encoding="utf-8")
        entries = []
        
        for part in content.split(ENTRY_SEPARATOR):
            part = part.strip()
            if part:
                entries.append(MemoryEntry.from_string(part))
        
        return entries
    
    def _write_file(self, file_path: Path, entries: List[MemoryEntry]):
        content = ENTRY_SEPARATOR.join(e.to_string() for e in entries)
        file_path.write_text(content, encoding="utf-8")
    
    def _capture_snapshot(self):
        self._snapshot = {
            "memory": self._render_block("memory", self._memory_entries),
            "user": self._render_block("user", self._user_entries),
        }
    
    def _render_block(self, block_type: str, entries: List[MemoryEntry]) -> str:
        if not entries:
            return ""
        
        lines = [f"## {block_type.title()}"]
        for entry in entries:
            lines.append(f"- {entry.content}")
        return "\n".join(lines)
    
    def _char_count(self, target: str = "memory") -> int:
        entries = self._memory_entries if target == "memory" else self._user_entries
        return sum(len(e.content) for e in entries)
    
    def get_snapshot(self) -> Dict[str, str]:
        return self._snapshot.copy()
    
    def get_system_prompt_block(self) -> str:
        parts = []
        
        if self._snapshot["memory"]:
            parts.append(self._snapshot["memory"])
        
        if self._snapshot["user"]:
            parts.append(self._snapshot["user"])
        
        return "\n\n".join(parts) if parts else ""
    
    def add(
        self,
        content: str,
        target: str = "memory",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        limit = self.memory_limit if target == "memory" else self.user_memory_limit
        entries = self._memory_entries if target == "memory" else self._user_entries
        file_path = self.memory_file if target == "memory" else self.user_file
        
        current_count = self._char_count(target)
        new_total = current_count + len(content)
        
        if new_total > limit:
            return {
                "success": False,
                "error": (
                    f"Memory at {current_count:,}/{limit:,} chars. "
                    f"Adding this entry ({len(content)} chars) would exceed the limit. "
                    f"Replace or remove existing entries first."
                ),
                "current_entries": [e.content for e in entries],
                "usage": f"{current_count:,}/{limit:,}",
            }
        
        entry = MemoryEntry(content=content, metadata=metadata or {})
        entries.append(entry)
        self._write_file(file_path, entries)
        
        return {
            "success": True,
            "id": hashlib.sha256(content.encode()).hexdigest()[:16],
            "usage": f"{self._char_count(target):,}/{limit:,}",
        }
    
    def replace(
        self,
        old_content: str,
        new_content: str,
        target: str = "memory",
    ) -> Dict[str, Any]:
        entries = self._memory_entries if target == "memory" else self._user_entries
        file_path = self.memory_file if target == "memory" else self.user_file
        limit = self.memory_limit if target == "memory" else self.user_memory_limit
        
        for i, entry in enumerate(entries):
            if old_content in entry.content:
                current_count = self._char_count(target)
                diff = len(new_content) - len(old_content)
                
                if current_count + diff > limit:
                    return {
                        "success": False,
                        "error": f"Replace would exceed memory limit",
                        "usage": f"{current_count:,}/{limit:,}",
                    }
                
                entries[i] = MemoryEntry(
                    content=new_content,
                    timestamp=datetime.now(),
                    metadata=entry.metadata,
                )
                self._write_file(file_path, entries)
                return {"success": True}
        
        return {"success": False, "error": "Content not found"}
    
    def remove(self, content: str, target: str = "memory") -> Dict[str, Any]:
        entries = self._memory_entries if target == "memory" else self._user_entries
        file_path = self.memory_file if target == "memory" else self.user_file
        
        original_len = len(entries)
        entries[:] = [e for e in entries if content not in e.content]
        
        if len(entries) == original_len:
            return {"success": False, "error": "Content not found"}
        
        self._write_file(file_path, entries)
        return {"success": True}
    
    def search(
        self,
        query: str,
        target: Optional[str] = None,
        limit: int = 5,
    ) -> List[Tuple[MemoryEntry, float]]:
        results = []
        query_lower = query.lower()
        
        entries_to_search = []
        if target is None or target == "memory":
            entries_to_search.extend(self._memory_entries)
        if target is None or target == "user":
            entries_to_search.extend(self._user_entries)
        
        for entry in entries_to_search:
            if query_lower in entry.content.lower():
                relevance = entry.content.lower().count(query_lower)
                results.append((entry, relevance))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def list_all(self, target: Optional[str] = None) -> List[MemoryEntry]:
        if target == "memory":
            return self._memory_entries.copy()
        elif target == "user":
            return self._user_entries.copy()
        else:
            return self._memory_entries + self._user_entries
    
    def clear(self, target: Optional[str] = None):
        if target == "memory" or target is None:
            self._memory_entries.clear()
            self._write_file(self.memory_file, self._memory_entries)
        if target == "user" or target is None:
            self._user_entries.clear()
            self._write_file(self.user_file, self._user_entries)
    
    def get_usage(self) -> Dict[str, Dict[str, Any]]:
        return {
            "memory": {
                "chars": self._char_count("memory"),
                "limit": self.memory_limit,
                "entries": len(self._memory_entries),
            },
            "user": {
                "chars": self._char_count("user"),
                "limit": self.user_memory_limit,
                "entries": len(self._user_entries),
            },
        }
    
    def compress(self, target: str = "memory") -> Dict[str, Any]:
        entries = self._memory_entries if target == "memory" else self._user_entries
        file_path = self.memory_file if target == "memory" else self.user_file
        
        if len(entries) <= 1:
            return {"success": True, "message": "Nothing to compress"}
        
        unique_contents = {}
        for entry in entries:
            key = entry.content.lower().strip()
            if key not in unique_contents:
                unique_contents[key] = entry
        
        new_entries = list(unique_contents.values())
        
        if len(new_entries) < len(entries):
            if target == "memory":
                self._memory_entries = new_entries
            else:
                self._user_entries = new_entries
            
            self._write_file(file_path, new_entries)
            
            return {
                "success": True,
                "removed": len(entries) - len(new_entries),
                "remaining": len(new_entries),
            }
        
        return {"success": True, "message": "No duplicates found"}


MEMORY_GUIDANCE = """
You have persistent memory across sessions. Save durable facts using the memory tool: 
user preferences, environment details, tool quirks, and stable conventions.

Prioritize what reduces future user steering — the most valuable memory is one 
that prevents the user from having to correct or remind you again.

Write memories as declarative facts, not instructions to yourself:
- 'User prefers concise responses' ✓ — 'Always respond concisely' ✗
- 'Project uses pytest with xdist' ✓ — 'Run tests with pytest -n 4' ✗

If you've discovered a new way to do something, save it as a skill, not a memory.
"""
