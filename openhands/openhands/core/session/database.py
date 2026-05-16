"""
会话持久化系统

Hermes风格的会话管理：
- SQLite会话存储
- 消息历史持久化
- 会话恢复
- 系统提示词缓存
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("./data/sessions/sessions.db")


class SessionDatabase:
    """会话数据库 - SQLite存储"""
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    status TEXT,
                    system_prompt TEXT,
                    metadata TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TEXT,
                    tool_call_id TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session 
                ON messages(session_id)
            """)
            
            conn.commit()
            conn.close()
    
    def create_session(self, session_id: str, title: str = None, metadata: Dict = None) -> bool:
        """创建新会话"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                now = datetime.now().isoformat()
                cursor.execute(
                    """INSERT INTO sessions (session_id, title, created_at, updated_at, status, metadata)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, title or "新会话", now, now, "active", json.dumps(metadata or {}))
                )
                
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"获取会话失败: {e}")
            return None
    
    def update_session(self, session_id: str, **kwargs):
        """更新会话信息"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                updates = []
                values = []
                for key, value in kwargs.items():
                    if key == 'metadata':
                        value = json.dumps(value)
                    updates.append(f"{key} = ?")
                    values.append(value)
                
                updates.append("updated_at = ?")
                values.append(datetime.now().isoformat())
                values.append(session_id)
                
                cursor.execute(
                    f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?",
                    values
                )
                
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"更新会话失败: {e}")
    
    def update_system_prompt(self, session_id: str, system_prompt: str):
        """更新会话的系统提示词（用于缓存）"""
        self.update_session(session_id, system_prompt=system_prompt)
    
    def add_message(self, session_id: str, role: str, content: str, tool_call_id: str = None) -> bool:
        """添加消息到会话"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                now = datetime.now().isoformat()
                cursor.execute(
                    """INSERT INTO messages (session_id, role, content, created_at, tool_call_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (session_id, role, content, now, tool_call_id)
                )
                
                conn.commit()
                conn.close()
                
                # 更新会话时间
                self.update_session(session_id)
                return True
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            return False
    
    def get_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取会话消息"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute(
                    """SELECT role, content, created_at, tool_call_id 
                       FROM messages 
                       WHERE session_id = ?
                       ORDER BY id ASC
                       LIMIT ?""",
                    (session_id, limit)
                )
                
                rows = cursor.fetchall()
                conn.close()
                
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            return []
    
    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出最近的会话"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute(
                    """SELECT session_id, title, created_at, updated_at, status
                       FROM sessions
                       ORDER BY updated_at DESC
                       LIMIT ?""",
                    (limit,)
                )
                
                rows = cursor.fetchall()
                conn.close()
                
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"列出会话失败: {e}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return False


# 全局会话数据库实例
_session_db: Optional[SessionDatabase] = None


def get_session_db() -> SessionDatabase:
    """获取会话数据库实例"""
    global _session_db
    if _session_db is None:
        _session_db = SessionDatabase()
    return _session_db


class SessionManager:
    """会话管理器"""
    
    def __init__(self, db: SessionDatabase = None):
        self._db = db or get_session_db()
    
    def create(self, session_id: str = None, title: str = None) -> str:
        """创建新会话"""
        import uuid
        session_id = session_id or str(uuid.uuid4())
        self._db.create_session(session_id, title)
        return session_id
    
    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        return self._db.get_session(session_id)
    
    def load_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """加载会话消息"""
        return self._db.get_messages(session_id)
    
    def save_message(self, session_id: str, role: str, content: str, tool_call_id: str = None):
        """保存消息"""
        self._db.add_message(session_id, role, content, tool_call_id)
    
    def update_title(self, session_id: str, title: str):
        """更新会话标题"""
        self._db.update_session(session_id, title=title)
    
    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出最近会话"""
        return self._db.list_sessions(limit)
    
    def delete(self, session_id: str) -> bool:
        """删除会话"""
        return self._db.delete_session(session_id)
