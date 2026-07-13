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
            log_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(operation_logs)"
                ).fetchall()
            }
            if "ip_address" not in log_columns:
                connection.execute("""
                    ALTER TABLE operation_logs
                    ADD COLUMN ip_address TEXT
                """)
            if "user_agent" not in log_columns:
                connection.execute("""
                    ALTER TABLE operation_logs
                    ADD COLUMN user_agent TEXT
                """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    display_name TEXT NOT NULL,
                    permissions_json TEXT NOT NULL DEFAULT '[]',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(accounts)").fetchall()
            }
            if "permissions_json" not in columns:
                connection.execute("""
                    ALTER TABLE accounts
                    ADD COLUMN permissions_json TEXT NOT NULL DEFAULT '[]'
                """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_accounts_role_active
                ON accounts(role, active)
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS packaging_templates (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    base_template TEXT NOT NULL,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    builtin INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_packaging_templates_status
                ON packaging_templates(enabled DESC, is_default DESC, builtin DESC, updated_at DESC)
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
        keyword: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        params: list = []
        clauses: list[str] = []
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        keyword = str(keyword or "").strip().lower()
        if keyword:
            clauses.append("""
                INSTR(LOWER(
                    COALESCE(actor, '') || ' ' || COALESCE(role, '') || ' ' ||
                    COALESCE(action, '') || ' ' || COALESCE(task_id, '') || ' ' ||
                    COALESCE(target_name, '') || ' ' || COALESCE(message, '') || ' ' ||
                    COALESCE(ip_address, '')
                ), ?) > 0
            """)
            params.append(keyword)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        with self._lock, self._connect() as connection:
            rows = connection.execute(f"""
                SELECT id, actor, role, action, task_id, target_name, success,
                       message, ip_address, user_agent, created_at
                FROM operation_logs
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
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

    def count_operation_logs(
        self,
        *,
        actor: str | None = None,
        keyword: str | None = None,
    ) -> int:
        params: list = []
        clauses: list[str] = []
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        keyword = str(keyword or "").strip().lower()
        if keyword:
            clauses.append("""
                INSTR(LOWER(
                    COALESCE(actor, '') || ' ' || COALESCE(role, '') || ' ' ||
                    COALESCE(action, '') || ' ' || COALESCE(task_id, '') || ' ' ||
                    COALESCE(target_name, '') || ' ' || COALESCE(message, '') || ' ' ||
                    COALESCE(ip_address, '')
                ), ?) > 0
            """)
            params.append(keyword)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock, self._connect() as connection:
            row = connection.execute(f"""
                SELECT COUNT(*) AS total
                FROM operation_logs
                {where}
            """, params).fetchone()
        return int(row["total"] or 0)

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
                    username, password_hash, role, display_name, permissions_json,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                account["password_hash"],
                account.get("role") or "user",
                account.get("display_name") or username,
                json.dumps(account.get("permissions") or [], ensure_ascii=False),
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
                    username, password_hash, role, display_name, permissions_json,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                account["password_hash"],
                account.get("role") or "user",
                account.get("display_name") or username,
                json.dumps(account.get("permissions") or [], ensure_ascii=False),
                1 if account.get("active", True) else 0,
                now,
                now,
            ))

    def update_account(self, username: str, updates: dict):
        allowed = {
            "password_hash",
            "role",
            "display_name",
            "permissions_json",
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
                SELECT username, password_hash, role, display_name, permissions_json,
                       active, created_at, updated_at
                FROM accounts
                WHERE username = ?
            """, (username,)).fetchone()
        return self._account_row(row) if row else None

    def list_accounts(self, include_inactive: bool = True) -> list[dict]:
        where = "" if include_inactive else "WHERE active = 1"
        with self._lock, self._connect() as connection:
            rows = connection.execute(f"""
                SELECT username, password_hash, role, display_name, permissions_json,
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
            "permissions": self._decode_permissions(row["permissions_json"]),
            "active": bool(row["active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _decode_permissions(self, raw: str) -> list[str]:
        try:
            value = json.loads(raw or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item]

    def ensure_packaging_templates(self, templates: list[dict]):
        """Seed built-in presets without overwriting user-managed metadata."""
        now = time.time()
        with self._lock, self._connect() as connection:
            for template in templates:
                connection.execute("""
                    INSERT OR IGNORE INTO packaging_templates (
                        id, name, description, base_template, config_json,
                        builtin, enabled, is_default, created_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?)
                """, (
                    template["id"],
                    template["name"],
                    template.get("description") or "",
                    template.get("base_template") or template["id"],
                    json.dumps(template.get("config") or {}, ensure_ascii=False),
                    1 if template.get("is_default") else 0,
                    template.get("created_by") or "system",
                    now,
                    now,
                ))

    def list_packaging_templates(self, include_disabled: bool = True) -> list[dict]:
        where = "" if include_disabled else "WHERE enabled = 1"
        with self._lock, self._connect() as connection:
            rows = connection.execute(f"""
                SELECT id, name, description, base_template, config_json,
                       builtin, enabled, is_default, created_by, created_at, updated_at
                FROM packaging_templates
                {where}
                ORDER BY is_default DESC, builtin DESC, updated_at DESC, name ASC
            """).fetchall()
        return [self._packaging_template_row(row) for row in rows]

    def get_packaging_template(self, template_id: str) -> dict | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("""
                SELECT id, name, description, base_template, config_json,
                       builtin, enabled, is_default, created_by, created_at, updated_at
                FROM packaging_templates
                WHERE id = ?
            """, (template_id,)).fetchone()
        return self._packaging_template_row(row) if row else None

    def create_packaging_template(self, template: dict):
        now = time.time()
        with self._lock, self._connect() as connection:
            if template.get("is_default"):
                connection.execute("UPDATE packaging_templates SET is_default = 0")
            connection.execute("""
                INSERT INTO packaging_templates (
                    id, name, description, base_template, config_json,
                    builtin, enabled, is_default, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template["id"],
                template["name"],
                template.get("description") or "",
                template["base_template"],
                json.dumps(template.get("config") or {}, ensure_ascii=False),
                1 if template.get("builtin") else 0,
                1 if template.get("enabled", True) else 0,
                1 if template.get("is_default") else 0,
                template.get("created_by"),
                now,
                now,
            ))

    def update_packaging_template(self, template_id: str, updates: dict):
        allowed = {"name", "description", "base_template", "config_json", "enabled", "is_default"}
        assignments = []
        params = []
        for key, value in updates.items():
            if key not in allowed:
                continue
            assignments.append(f"{key} = ?")
            if key in {"enabled", "is_default"}:
                value = 1 if value else 0
            params.append(value)
        if not assignments:
            return
        assignments.append("updated_at = ?")
        params.extend([time.time(), template_id])
        with self._lock, self._connect() as connection:
            if updates.get("is_default"):
                connection.execute("UPDATE packaging_templates SET is_default = 0")
                if "enabled" not in updates:
                    assignments.append("enabled = 1")
                    params.insert(-2, 1)
            connection.execute(
                f"UPDATE packaging_templates SET {', '.join(assignments)} WHERE id = ?",
                params,
            )

    def delete_packaging_template(self, template_id: str) -> bool:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT builtin FROM packaging_templates WHERE id = ?", (template_id,)
            ).fetchone()
            if not row or row["builtin"]:
                return False
            connection.execute("DELETE FROM packaging_templates WHERE id = ?", (template_id,))
        return True

    def _packaging_template_row(self, row) -> dict:
        try:
            config = json.loads(row["config_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            config = {}
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "base_template": row["base_template"],
            "config": config if isinstance(config, dict) else {},
            "builtin": bool(row["builtin"]),
            "enabled": bool(row["enabled"]),
            "is_default": bool(row["is_default"]),
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
