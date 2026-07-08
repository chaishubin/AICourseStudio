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
            connection.execute("""
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    action TEXT NOT NULL,
                    task_id TEXT,
                    target_name TEXT,
                    success INTEGER NOT NULL DEFAULT 1,
                    message TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at REAL NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation_logs_actor_created
                ON operation_logs(actor, created_at DESC)
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation_logs_created
                ON operation_logs(created_at DESC)
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    display_name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_accounts_role_active
                ON accounts(role, active)
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

    def add_operation_log(self, log: dict):
        with self._lock, self._connect() as connection:
            connection.execute("""
                INSERT INTO operation_logs (
                    actor, role, action, task_id, target_name, success,
                    message, ip_address, user_agent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log.get("actor") or "anonymous",
                log.get("role") or "user",
                log.get("action") or "unknown",
                log.get("task_id"),
                log.get("target_name"),
                1 if log.get("success", True) else 0,
                log.get("message"),
                log.get("ip_address"),
                log.get("user_agent"),
                float(log.get("created_at") or time.time()),
            ))

    def list_operation_logs(
        self,
        *,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        params: list = []
        where = ""
        if actor:
            where = "WHERE actor = ?"
            params.append(actor)
        params.append(limit)
        with self._lock, self._connect() as connection:
            rows = connection.execute(f"""
                SELECT id, actor, role, action, task_id, target_name, success,
                       message, ip_address, user_agent, created_at
                FROM operation_logs
                {where}
                ORDER BY created_at DESC
                LIMIT ?
            """, params).fetchall()
        return [
            {
                "id": row["id"],
                "actor": row["actor"],
                "role": row["role"],
                "action": row["action"],
                "task_id": row["task_id"],
                "target_name": row["target_name"],
                "success": bool(row["success"]),
                "message": row["message"],
                "ip_address": row["ip_address"],
                "user_agent": row["user_agent"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def ensure_account(self, account: dict):
        now = time.time()
        username = str(account.get("username") or "").strip()
        if not username:
            raise ValueError("username is required")
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT username FROM accounts WHERE username = ?",
                (username,),
            ).fetchone()
            if existing:
                return
            connection.execute("""
                INSERT INTO accounts (
                    username, password_hash, role, display_name,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                account["password_hash"],
                account.get("role") or "user",
                account.get("display_name") or username,
                1 if account.get("active", True) else 0,
                now,
                now,
            ))

    def create_account(self, account: dict):
        now = time.time()
        username = str(account.get("username") or "").strip()
        if not username:
            raise ValueError("username is required")
        with self._lock, self._connect() as connection:
            connection.execute("""
                INSERT INTO accounts (
                    username, password_hash, role, display_name,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                account["password_hash"],
                account.get("role") or "user",
                account.get("display_name") or username,
                1 if account.get("active", True) else 0,
                now,
                now,
            ))

    def update_account(self, username: str, updates: dict):
        allowed = {
            "password_hash",
            "role",
            "display_name",
            "active",
        }
        assignments = []
        params = []
        for key, value in updates.items():
            if key not in allowed:
                continue
            assignments.append(f"{key} = ?")
            params.append(1 if key == "active" and value else 0 if key == "active" else value)
        if not assignments:
            return
        assignments.append("updated_at = ?")
        params.append(time.time())
        params.append(username)
        with self._lock, self._connect() as connection:
            connection.execute(
                f"UPDATE accounts SET {', '.join(assignments)} WHERE username = ?",
                params,
            )

    def get_account(self, username: str) -> dict | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("""
                SELECT username, password_hash, role, display_name,
                       active, created_at, updated_at
                FROM accounts
                WHERE username = ?
            """, (username,)).fetchone()
        return self._account_row(row) if row else None

    def list_accounts(self, include_inactive: bool = True) -> list[dict]:
        where = "" if include_inactive else "WHERE active = 1"
        with self._lock, self._connect() as connection:
            rows = connection.execute(f"""
                SELECT username, password_hash, role, display_name,
                       active, created_at, updated_at
                FROM accounts
                {where}
                ORDER BY active DESC, role ASC, username ASC
            """).fetchall()
        return [self._account_row(row) for row in rows]

    def count_active_super_admins(self) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute("""
                SELECT COUNT(*) AS count
                FROM accounts
                WHERE role = 'super_admin' AND active = 1
            """).fetchone()
        return int(row["count"] or 0)

    def _account_row(self, row) -> dict:
        return {
            "username": row["username"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "display_name": row["display_name"],
            "active": bool(row["active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
