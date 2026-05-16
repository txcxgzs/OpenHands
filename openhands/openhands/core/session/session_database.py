"""
完整的SQLite会话持久化系统 - 100%对齐Hermes

功能：
- 会话表管理
- 消息历史持久化
- 系统提示缓存
- 会话元数据
- 批量操作
- 线程安全
"""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

# 默认数据库路径
DEFAULT_DB_PATH = Path("./data/sessions/sessions.db")

# 数据库Schema
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New Session',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    system_prompt TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    summary TEXT,
    goal TEXT
);
"""

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tool_call_id TEXT,
    tool_calls TEXT,
    tool_result_id TEXT,
    thinking_budget_consumed INTEGER DEFAULT 0,
    is_error BOOLEAN DEFAULT 0,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
"""


@dataclass
class SessionRecord:
    """会话记录"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    status: str = "active"
    system_prompt: Optional[str] = None
    metadata: Dict[str, Any] = None
    summary: Optional[str] = None
    goal: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MessageRecord:
    """消息记录"""
    id: Optional[int]
    session_id: str
    role: str
    content: str
    created_at: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[str] = None
    tool_result_id: Optional[str] = None
    thinking_budget_consumed: int = 0
    is_error: bool = False


class SessionDatabase:
    """会话数据库 - SQLite存储，线程安全"""
    
    def __init__(self, db_path: Path = None):
        self._db_path = db_path or DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn_cache = threading.local()
        self._initialized = False
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """获取线程本地连接"""
        if not hasattr(self._conn_cache, 'conn'):
            self._conn_cache.conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn_cache.conn.row_factory = sqlite3.Row
        return self._conn_cache.conn
    
    def _init_db(self):
        """初始化数据库"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(CREATE_SESSIONS_TABLE)
            cursor.execute(CREATE_MESSAGES_TABLE)
            cursor.executescript(CREATE_INDEXES)
            conn.commit()
            self._initialized = True
    
    def create_session(
        self,
        session_id: str,
        title: str = "New Session",
        system_prompt: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """创建新会话"""
        with self._lock:
            try:
                now = datetime.now().isoformat()
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO sessions
                    (session_id, title, created_at, updated_at, status, system_prompt, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    title,
                    now,
                    now,
                    "active",
                    system_prompt,
                    json.dumps(metadata or {})
                ))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to create session: {e}")
                return False
    
    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """获取会话"""
        with self._lock:
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_session(row)
            except Exception as e:
                logger.error(f"Failed to get session: {e}")
                return None
    
    def update_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        system_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
        goal: Optional[str] = None
    ) -> bool:
        """更新会话"""
        with self._lock:
            try:
                updates: List[str] = []
                params: List[Any] = []
                
                if title is not None:
                    updates.append("title = ?")
                    params.append(title)
                if status is not None:
                    updates.append("status = ?")
                    params.append(status)
                if system_prompt is not None:
                    updates.append("system_prompt = ?")
                    params.append(system_prompt)
                if metadata is not None:
                    updates.append("metadata = ?")
                    params.append(json.dumps(metadata))
                if summary is not None:
                    updates.append("summary = ?")
                    params.append(summary)
                if goal is not None:
                    updates.append("goal = ?")
                    params.append(goal)
                
                if updates:
                    updates.append("updated_at = ?")
                    params.append(datetime.now().isoformat())
                    params.append(session_id)
                    
                    conn = self._get_conn()
                    cursor = conn.cursor()
                    cursor.execute(f"""
                        UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?
                    """, tuple(params))
                    conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to update session: {e}")
                return False
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        with self._lock:
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to delete session: {e}")
                return False
    
    def list_sessions(
        self, limit: int = 100, offset: int = 0, status: str = None
    ) -> List[SessionRecord]:
        """列出会话"""
        with self._lock:
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                
                query = "SELECT * FROM sessions"
                params = []
                if status:
                    query += " WHERE status = ?"
                    params.append(status)
                query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                return [self._row_to_session(row) for row in rows]
            except Exception as e:
                logger.error(f"Failed to list sessions: {e}")
                return []
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_call_id: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        tool_result_id: Optional[str] = None,
        thinking_budget_consumed: int = 0,
        is_error: bool = False
    ) -> Optional[int]:
        """添加消息"""
        with self._lock:
            try:
                now = datetime.now().isoformat()
                conn = self._get_conn()
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO messages
                    (session_id, role, content, created_at, tool_call_id, tool_calls,
                     tool_result_id, thinking_budget_consumed, is_error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    role,
                    content,
                    now,
                    tool_call_id,
                    json.dumps(tool_calls) if tool_calls else None,
                    tool_result_id,
                    thinking_budget_consumed,
                    1 if is_error else 0
                ))
                
                conn.commit()
                
                # 更新会话时间
                self.update_session(session_id)
                
                return cursor.lastrowid
            except Exception as e:
                logger.error(f"Failed to add message: {e}")
                return None
    
    def get_messages(
        self, session_id: str, limit: int = 1000, offset: int = 0
    ) -> List[MessageRecord]:
        """获取会话消息"""
        with self._lock:
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE session_id = ?
                    ORDER BY id ASC
                    LIMIT ? OFFSET ?
                """, (session_id, limit, offset))
                rows = cursor.fetchall()
                return [self._row_to_message(row) for row in rows]
            except Exception as e:
                logger.error(f"Failed to get messages: {e}")
                return []
    
    def get_message_count(self, session_id: str) -> int:
        """获取消息数量"""
        with self._lock:
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                return int(row[0]) if row else 0
            except Exception as e:
                logger.error(f"Failed to get message count: {e}")
                return 0
    
    def truncate_messages(
        self, session_id: str, keep_last: int = 100
    ) -> bool:
        """截断消息历史"""
        with self._lock:
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM messages
                    WHERE session_id = ?
                    AND id NOT IN (
                        SELECT id FROM messages
                        WHERE session_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                    )
                """, (session_id, session_id, keep_last))
                
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to truncate messages: {e}")
                return False
    
    def _row_to_session(self, row) -> SessionRecord:
        """行转会话记录"""
        metadata = json.loads(row['metadata']) if row['metadata'] else {}
        return SessionRecord(
            session_id=row['session_id'],
            title=row['title'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            status=row['status'],
            system_prompt=row['system_prompt'],
            metadata=metadata,
            summary=row['summary'],
            goal=row['goal']
        )
    
    def _row_to_message(self, row) -> MessageRecord:
        """行转消息记录"""
        return MessageRecord(
            id=row['id'],
            session_id=row['session_id'],
            role=row['role'],
            content=row['content'],
            created_at=row['created_at'],
            tool_call_id=row['tool_call_id'],
            tool_calls=json.loads(row['tool_calls']) if row['tool_calls'] else None,
            tool_result_id=row['tool_result_id'],
            thinking_budget_consumed=row['thinking_budget_consumed'],
            is_error=bool(row['is_error'])
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            try:
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sessions")
                session_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM messages")
                message_count = cursor.fetchone()[0]
                return {
                    'session_count': session_count,
                    'message_count': message_count,
                    'db_path': str(self._db_path)
                }
            except Exception as e:
                logger.error(f"Failed to get stats: {e}")
                return {}


# 全局实例
_session_db: Optional[SessionDatabase] = None


def get_session_db(db_path: Path = None) -> SessionDatabase:
    """获取会话数据库单例"""
    global _session_db
    if _session_db is None:
        _session_db = SessionDatabase(db_path)
    return _session_db


class SessionManager:
    """会话管理器 - 高层接口"""
    
    def __init__(self, db: SessionDatabase = None):
        self._db = db or get_session_db()
    
    def create(
        self,
        session_id: Optional[str] = None,
        title: str = "New Session",
        system_prompt: Optional[str] = None
    ) -> str:
        """创建会话，返回session_id"""
        import uuid
        if not session_id:
            session_id = str(uuid.uuid4())
        
        success = self._db.create_session(
            session_id=session_id,
            title=title,
            system_prompt=system_prompt
        )
        return session_id if success else None
    
    def load(
        self,
        session_id: str,
        message_limit: int = 1000
    ) -> Optional[Dict[str, Any]]:
        """加载会话"""
        session = self._db.get_session(session_id)
        if not session:
            return None
        
        messages = self._db.get_messages(session_id, limit=message_limit)
        return {
            'session': session,
            'messages': messages
        }
    
    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs
    ) -> Optional[int]:
        """保存消息"""
        return self._db.add_message(
            session_id=session_id,
            role=role,
            content=content,
            **kwargs
        )
    
    def update_title(
        self,
        session_id: str,
        title: str
    ) -> bool:
        """更新标题"""
        return self._db.update_session(session_id, title=title)
    
    def list_recent(
        self, limit: int = 20, status: str = "active"
    ) -> List[SessionRecord]:
        """列出最近会话"""
        return self._db.list_sessions(limit=limit, status=status)
    
    def delete(self, session_id: str) -> bool:
        """删除会话"""
        return self._db.delete_session(session_id)
