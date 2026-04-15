"""文档存储实现 - SQLite"""

import sqlite3
import json
import os
import threading
from typing import Dict, Any, List, Optional


class SQLiteDocumentStore:
    """SQLite文档存储实现"""

    _instances = {}
    _initialized_dbs = set()

    def __new__(cls, db_path: str = "./memory_data/memory.db"):
        abs_path = os.path.abspath(db_path)
        if abs_path not in cls._instances:
            instance = super(SQLiteDocumentStore, cls).__new__(cls)
            cls._instances[abs_path] = instance
        return cls._instances[abs_path]

    def __init__(self, db_path: str = "./memory_data/memory.db"):
        if hasattr(self, '_initialized'):
            return

        self.db_path = db_path
        self.local = threading.local()

        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        abs_path = os.path.abspath(db_path)
        if abs_path not in self._initialized_dbs:
            self._init_database()
            self._initialized_dbs.add(abs_path)

        self._initialized = True

    def _get_connection(self):
        if not hasattr(self.local, 'connection'):
            self.local.connection = sqlite3.connect(self.db_path)
            self.local.connection.row_factory = sqlite3.Row
        return self.local.connection

    def _init_database(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                importance REAL NOT NULL,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories (memory_type)",
            "CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories (timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories (importance)"
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

        # 凭证专用表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                base_url TEXT NOT NULL,
                environment_name TEXT NOT NULL DEFAULT 'default',
                extra_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, environment_name, base_url)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_credentials_user_env
            ON credentials (user_id, environment_name)
        """)

        conn.commit()

    def add_memory(self, memory_id: str, user_id: str, content: str, memory_type: str,
                   timestamp: int, importance: float, properties: Dict[str, Any] = None) -> str:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO memories
            (id, user_id, content, memory_type, timestamp, importance, properties, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (memory_id, user_id, content, memory_type, timestamp, importance,
              json.dumps(properties) if properties else None))

        conn.commit()
        return memory_id

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, user_id, content, memory_type, timestamp, importance, properties, created_at
            FROM memories WHERE id = ?
        """, (memory_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "memory_id": row["id"],
            "user_id": row["user_id"],
            "content": row["content"],
            "memory_type": row["memory_type"],
            "timestamp": row["timestamp"],
            "importance": row["importance"],
            "properties": json.loads(row["properties"]) if row["properties"] else {},
            "created_at": row["created_at"]
        }

    def search_memories(self, user_id: str = None, memory_type: str = None,
                        start_time: int = None, end_time: int = None,
                        importance_threshold: float = None, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()

        where_conditions = []
        params = []

        if user_id:
            where_conditions.append("user_id = ?")
            params.append(user_id)

        if memory_type:
            where_conditions.append("memory_type = ?")
            params.append(memory_type)

        if start_time:
            where_conditions.append("timestamp >= ?")
            params.append(start_time)

        if end_time:
            where_conditions.append("timestamp <= ?")
            params.append(end_time)

        if importance_threshold:
            where_conditions.append("importance >= ?")
            params.append(importance_threshold)

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        cursor.execute(f"""
            SELECT id, user_id, content, memory_type, timestamp, importance, properties, created_at
            FROM memories
            {where_clause}
            ORDER BY importance DESC, timestamp DESC
            LIMIT ?
        """, params + [limit])

        memories = []
        for row in cursor.fetchall():
            memories.append({
                "memory_id": row["id"],
                "user_id": row["user_id"],
                "content": row["content"],
                "memory_type": row["memory_type"],
                "timestamp": row["timestamp"],
                "importance": row["importance"],
                "properties": json.loads(row["properties"]) if row["properties"] else {},
                "created_at": row["created_at"]
            })

        return memories

    def update_memory(self, memory_id: str, content: str = None, importance: float = None,
                      properties: Dict[str, Any] = None) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()

        update_fields = []
        params = []

        if content is not None:
            update_fields.append("content = ?")
            params.append(content)

        if importance is not None:
            update_fields.append("importance = ?")
            params.append(importance)

        if properties is not None:
            update_fields.append("properties = ?")
            params.append(json.dumps(properties))

        if not update_fields:
            return False

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(memory_id)

        cursor.execute(f"""
            UPDATE memories SET {', '.join(update_fields)} WHERE id = ?
        """, params)

        conn.commit()
        return cursor.rowcount > 0

    def delete_memory(self, memory_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        deleted_count = cursor.rowcount

        conn.commit()
        return deleted_count > 0

    def get_database_stats(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM memories")
        stats = {"total_memories": cursor.fetchone()["count"]}

        cursor.execute("""
            SELECT memory_type, COUNT(*) as count
            FROM memories GROUP BY memory_type
        """)
        memory_types = {}
        for row in cursor.fetchall():
            memory_types[row["memory_type"]] = row["count"]
        stats["memory_types"] = memory_types

        stats["store_type"] = "sqlite"
        stats["db_path"] = self.db_path

        return stats

    def close(self):
        if hasattr(self.local, 'connection'):
            self.local.connection.close()
            delattr(self.local, 'connection')

    # ========== 凭证管理方法 ==========

    def save_credential(self, credential_id: str, user_id: str, username: str,
                       password: str, base_url: str, environment_name: str = "default",
                       extra_data: Dict[str, Any] = None) -> str:
        """保存凭证到专用表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO credentials
            (id, user_id, username, password, base_url, environment_name, extra_data, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (credential_id, user_id, username, password, base_url, environment_name,
              json.dumps(extra_data) if extra_data else None))

        conn.commit()
        return credential_id

    def get_credential(self, user_id: str, environment_name: str = "default",
                      base_url: str = None) -> Optional[Dict[str, Any]]:
        """获取凭证"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if base_url:
            cursor.execute("""
                SELECT id, user_id, username, password, base_url, environment_name, extra_data, created_at
                FROM credentials
                WHERE user_id = ? AND environment_name = ? AND base_url = ?
                ORDER BY updated_at DESC
                LIMIT 1
            """, (user_id, environment_name, base_url))
        else:
            cursor.execute("""
                SELECT id, user_id, username, password, base_url, environment_name, extra_data, created_at
                FROM credentials
                WHERE user_id = ? AND environment_name = ?
                ORDER BY updated_at DESC
                LIMIT 1
            """, (user_id, environment_name))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "username": row["username"],
            "password": row["password"],
            "base_url": row["base_url"],
            "environment_name": row["environment_name"],
            "extra_data": json.loads(row["extra_data"]) if row["extra_data"] else {},
            "created_at": row["created_at"]
        }

    def delete_credential(self, credential_id: str) -> bool:
        """删除凭证"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
        deleted_count = cursor.rowcount

        conn.commit()
        return deleted_count > 0

    def list_credentials(self, user_id: str) -> List[Dict[str, Any]]:
        """列出用户的所有凭证（不包含密码）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, user_id, username, base_url, environment_name, extra_data, created_at
            FROM credentials
            WHERE user_id = ?
            ORDER BY updated_at DESC
        """, (user_id,))

        credentials = []
        for row in cursor.fetchall():
            credentials.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "username": row["username"],
                "base_url": row["base_url"],
                "environment_name": row["environment_name"],
                "extra_data": json.loads(row["extra_data"]) if row["extra_data"] else {},
                "created_at": row["created_at"]
            })

        return credentials
