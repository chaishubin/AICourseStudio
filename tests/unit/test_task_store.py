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
