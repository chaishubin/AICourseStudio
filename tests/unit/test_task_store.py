"""SQLite task queue persistence tests."""

import json
from queue import Queue

from web.task_store import TaskStore


def test_task_store_round_trips_strategy_and_queue_order(temp_dir):
    store = TaskStore(temp_dir / "tasks.db")
    store.upsert("first", {
        "status": "queued",
        "batch_id": "batch-1",
        "strategy": {"refinement_level": "strong"},
    })
    store.upsert("second", {
        "status": "queued",
        "batch_id": "batch-1",
        "strategy": {"refinement_level": "light"},
    })

    jobs = store.load_recent()

    assert [job["task_id"] for job in jobs] == ["first", "second"]
    assert jobs[0]["strategy"]["refinement_level"] == "strong"
    assert jobs[0]["queue_order"] < jobs[1]["queue_order"]


def test_task_store_updates_without_changing_queue_order(temp_dir):
    store = TaskStore(temp_dir / "tasks.db")
    store.upsert("task", {"status": "queued", "strategy": {}})
    original_order = store.load_recent()[0]["queue_order"]

    store.upsert("task", {"status": "processing", "strategy": {}})

    restored = store.load_recent()[0]
    assert restored["status"] == "processing"
    assert restored["queue_order"] == original_order


def test_task_store_records_operation_logs(temp_dir):
    store = TaskStore(temp_dir / "tasks.db")

    store.add_operation_log({
        "actor": "teacher",
        "role": "user",
        "action": "create_task",
        "task_id": "task-1",
        "target_name": "lesson.pptx",
    })
    store.add_operation_log({
        "actor": "admin",
        "role": "super_admin",
        "action": "delete_task",
        "task_id": "task-2",
        "target_name": "other.pptx",
    })

    teacher_logs = store.list_operation_logs(actor="teacher")
    all_logs = store.list_operation_logs()

    assert len(teacher_logs) == 1
    assert teacher_logs[0]["actor"] == "teacher"
    assert teacher_logs[0]["action"] == "create_task"
    assert len(all_logs) == 2


def test_task_store_paginates_operation_logs(temp_dir):
    store = TaskStore(temp_dir / "tasks.db")
    for index in range(5):
        store.add_operation_log({
            "actor": "teacher" if index < 4 else "other",
            "action": f"action-{index}",
            "created_at": 1000 + index,
        })

    logs = store.list_operation_logs(actor="teacher", limit=2, offset=2)

    assert store.count_operation_logs(actor="teacher") == 4
    assert [log["action"] for log in logs] == ["action-1", "action-0"]


def test_task_store_filters_operation_logs_before_pagination(temp_dir):
    store = TaskStore(temp_dir / "tasks.db")
    for index in range(5):
        store.add_operation_log({
            "actor": "teacher",
            "action": "preview_task" if index < 3 else "login",
            "ip_address": f"203.0.113.{index}",
            "created_at": 1000 + index,
        })

    logs = store.list_operation_logs(keyword="PREVIEW", limit=2, offset=1)

    assert store.count_operation_logs(keyword="preview") == 3
    assert [log["ip_address"] for log in logs] == ["203.0.113.1", "203.0.113.0"]


def test_task_store_migrates_operation_log_ip_columns(temp_dir):
    db_path = temp_dir / "legacy.db"
    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                action TEXT NOT NULL,
                task_id TEXT,
                target_name TEXT,
                success INTEGER NOT NULL DEFAULT 1,
                message TEXT,
                created_at REAL NOT NULL
            )
        """)

    store = TaskStore(db_path)
    store.add_operation_log({
        "actor": "teacher",
        "role": "user",
        "action": "login",
        "ip_address": "203.0.113.8",
        "user_agent": "pytest",
    })

    logs = store.list_operation_logs(actor="teacher")

    assert logs[0]["ip_address"] == "203.0.113.8"
    assert logs[0]["user_agent"] == "pytest"


def test_task_store_manages_accounts(temp_dir):
    store = TaskStore(temp_dir / "tasks.db")
    store.create_account({
        "username": "teacher",
        "password_hash": "hash",
        "role": "user",
        "display_name": "Teacher",
        "permissions": ["view_all_tasks"],
        "active": True,
    })

    account = store.get_account("teacher")
    assert account["display_name"] == "Teacher"
    assert account["active"] is True
    assert account["permissions"] == ["view_all_tasks"]

    store.update_account("teacher", {
        "display_name": "Teacher A",
        "role": "super_admin",
        "permissions_json": '["manage_accounts"]',
        "active": False,
    })

    updated = store.get_account("teacher")
    assert updated["display_name"] == "Teacher A"
    assert updated["role"] == "super_admin"
    assert updated["permissions"] == ["manage_accounts"]
    assert updated["active"] is False
    assert store.list_accounts()[0]["username"] == "teacher"


def test_delete_route_removes_database_record_and_files(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "sqlite-delete-task"
    output_root = temp_dir / "outputs"
    output_dir = output_root / task_id
    output_dir.mkdir(parents=True)
    (output_dir / "video.mp4").write_bytes(b"video")
    state_file = output_root / "state.json"
    state_file.write_text(json.dumps([{
        "task_id": task_id,
        "status": "completed",
        "output_dir": str(output_dir),
    }]), encoding="utf-8")
    store = TaskStore(output_root / "tasks.db")
    store.upsert(task_id, {
        "status": "completed",
        "output_dir": str(output_dir),
    })
    monkeypatch.setattr(web_app, "OUTPUT_FOLDER", output_root)
    monkeypatch.setattr(web_app, "STATE_FILE", state_file)
    monkeypatch.setattr(web_app, "task_store", store)
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "completed",
            "output_dir": str(output_dir),
        },
    })
    monkeypatch.setattr(web_app, "progress_queues", {task_id: Queue()})
    monkeypatch.setattr(web_app, "cancellation_events", {})

    response = web_app.app.test_client().delete(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    assert not output_dir.exists()
    assert store.load_recent() == []
    assert json.loads(state_file.read_text(encoding="utf-8")) == []
    assert task_id not in web_app.tasks
