"""长时记忆：研究历史与用户偏好的持久化存储。

后端可插拔：默认 SQLite（开箱即用），配置 DATABASE_URL 时使用 PostgreSQL。
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from loguru import logger


class LongTermMemory(ABC):
    """长时记忆抽象。"""

    @abstractmethod
    def save_session(self, research_id: str, question: str, summary: str, metadata: dict[str, Any]) -> None: ...

    @abstractmethod
    def get_history(self, user_key: str, limit: int = 10) -> list[dict[str, Any]]: ...

    @abstractmethod
    def save_preference(self, user_key: str, key: str, value: str) -> None: ...


class SQLiteLongTermMemory(LongTermMemory):
    """基于 SQLite 的长时记忆（默认后端）。"""

    def __init__(self, db_path: str = "data/deepresearch.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_history (
                id TEXT PRIMARY KEY,
                user_key TEXT,
                question TEXT,
                summary TEXT,
                metadata TEXT,
                created_at REAL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_key TEXT,
                pref_key TEXT,
                pref_value TEXT,
                updated_at REAL,
                PRIMARY KEY (user_key, pref_key)
            )
            """
        )
        self._conn.commit()

    def save_session(self, research_id: str, question: str, summary: str, metadata: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO research_history VALUES (?,?,?,?,?,?)",
            (
                research_id,
                metadata.get("user_key", "default"),
                question,
                summary,
                json.dumps(metadata, ensure_ascii=False),
                time.time(),
            ),
        )
        self._conn.commit()

    def get_history(self, user_key: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT question, summary, created_at FROM research_history "
            "WHERE user_key=? ORDER BY created_at DESC LIMIT ?",
            (user_key, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def save_preference(self, user_key: str, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO user_preferences VALUES (?,?,?,?)",
            (user_key, key, value, time.time()),
        )
        self._conn.commit()


class PostgresLongTermMemory(LongTermMemory):
    """基于 PostgreSQL 的长时记忆（可选后端）。"""

    def __init__(self, database_url: str) -> None:
        import psycopg

        self._conn = psycopg.connect(database_url)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS research_history (
                    id TEXT PRIMARY KEY,
                    user_key TEXT,
                    question TEXT,
                    summary TEXT,
                    metadata JSONB,
                    created_at DOUBLE PRECISION
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_key TEXT,
                    pref_key TEXT,
                    pref_value TEXT,
                    updated_at DOUBLE PRECISION,
                    PRIMARY KEY (user_key, pref_key)
                )
                """
            )
        self._conn.commit()

    def save_session(self, research_id: str, question: str, summary: str, metadata: dict[str, Any]) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO research_history VALUES (%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET summary=EXCLUDED.summary, metadata=EXCLUDED.metadata",
                (research_id, metadata.get("user_key", "default"), question, summary,
                 json.dumps(metadata, ensure_ascii=False), time.time()),
            )
        self._conn.commit()

    def get_history(self, user_key: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT question, summary, created_at FROM research_history "
                "WHERE user_key=%s ORDER BY created_at DESC LIMIT %s",
                (user_key, limit),
            )
            rows = cur.fetchall()
        return [{"question": r[0], "summary": r[1], "created_at": r[2]} for r in rows]

    def save_preference(self, user_key: str, key: str, value: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_preferences VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (user_key, pref_key) DO UPDATE SET pref_value=EXCLUDED.pref_value",
                (user_key, key, value, time.time()),
            )
        self._conn.commit()


def build_long_term_memory(backend: str = "sqlite", database_url: str = "", sqlite_path: str = "data/deepresearch.db") -> LongTermMemory:
    """构建长时记忆（可插拔）。"""
    if backend == "postgres" and database_url:
        logger.info("使用 PostgreSQL 长时记忆")
        return PostgresLongTermMemory(database_url)
    logger.info("使用 SQLite 长时记忆: {}", sqlite_path)
    return SQLiteLongTermMemory(sqlite_path)
