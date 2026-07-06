"""SQLite-backed task metadata for the local batch production queue."""

import json
import sqlite3
import threading
import time
from pathlib import Path


class TaskStore:
    """Persist queue state without making the processing pipeline database-aware."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    task_id TEXT PRIMARY KEY,
                    batch_id TEXT,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    queue_order INTEGER NOT NULL,
                    strategy_json TEXT NOT NULL DEFAULT '{}',
                    task_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_queue
                ON jobs(status, priority DESC, queue_order ASC)
            """)

    def upsert(self, task_id: str, task: dict):
        now = time.time()
        strategy = task.get("strategy") or {}
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT queue_order, created_at FROM jobs WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if existing:
                queue_order = existing["queue_order"]
                created_at = existing["created_at"]
            else:
                row = connection.execute(
                    "SELECT COALESCE(MAX(queue_order), 0) + 1 AS next_order FROM jobs"
                ).fetchone()
                queue_order = row["next_order"]
                created_at = now
            connection.execute("""
                INSERT INTO jobs (
                    task_id, batch_id, status, priority, queue_order,
                    strategy_json, task_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    batch_id = excluded.batch_id,
                    status = excluded.status,
                    priority = excluded.priority,
                    strategy_json = excluded.strategy_json,
                    task_json = excluded.task_json,
                    updated_at = excluded.updated_at
            """, (
                task_id,
                task.get("batch_id"),
                task.get("status", "pending"),
                int(task.get("priority", 0)),
                queue_order,
                json.dumps(strategy, ensure_ascii=False),
                json.dumps(task, ensure_ascii=False),
                created_at,
                now,
            ))
        return queue_order

    def load_recent(self, limit: int = 50) -> list[dict]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("""
                SELECT task_id, task_json, queue_order
                FROM jobs
                ORDER BY queue_order DESC
                LIMIT ?
            """, (limit,)).fetchall()
        result = []
        for row in reversed(rows):
            try:
                task = json.loads(row["task_json"])
            except (TypeError, json.JSONDecodeError):
                task = {}
            task["task_id"] = row["task_id"]
            task["queue_order"] = row["queue_order"]
            result.append(task)
        return result

    def delete(self, task_id: str):
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM jobs WHERE task_id = ?", (task_id,))
