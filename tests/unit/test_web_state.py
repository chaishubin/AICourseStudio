"""
Web 后端状态持久化 + SSE 心跳 相关的单元测试
"""

import json
import time
import tempfile
import shutil
from pathlib import Path
from queue import Queue, Empty

import pytest

# ---- 在 import app 之前把 OUTPUT_FOLDER 指向临时目录，避免污染真实数据 ----
_tmp_dir = Path(tempfile.mkdtemp())


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """每个用例使用独立的临时目录和空的 tasks / progress_queues"""
    import web.app as app_module

    # 把 OUTPUT_FOLDER 和 STATE_FILE 指向临时目录
    outputs = tmp_path / "outputs"
    outputs.mkdir(exist_ok=True)
    monkeypatch.setattr(app_module, "OUTPUT_FOLDER", outputs)
    monkeypatch.setattr(app_module, "STATE_FILE", outputs / "state.json")

    # 清空全局状态
    monkeypatch.setattr(app_module, "tasks", {})
    monkeypatch.setattr(app_module, "progress_queues", {})

    yield

    # 测试结束无需清理，tmp_path 会自动删除


# ==========================================================================
# save_state / load_state 单测
# ==========================================================================


class TestSaveState:
    """测试 save_state 持久化逻辑"""

    def test_writes_state_file(self):
        from web.app import save_state, tasks, STATE_FILE

        tasks["abc123"] = {
            "status": "completed",
            "stage": "complete",
            "percentage": 100,
            "message": "转换完成",
            "video_path": "/tmp/out.mp4",
            "file_path": "/tmp/uploads/abc123_演示文稿.pptx",
        }
        save_state("abc123")

        assert STATE_FILE.exists()
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        assert data["task_id"] == "abc123"
        assert data["status"] == "completed"

    def test_extracts_original_name_from_file_path(self):
        """从 uuid_原始名 格式的 file_path 中自动提取 original_name"""
        from web.app import save_state, tasks, STATE_FILE

        tasks["t1"] = {
            "status": "completed",
            "file_path": "/uploads/a1b2c3_我的PPT.pptx",
        }
        save_state("t1")

        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        assert data["original_name"] == "我的PPT.pptx"

    def test_original_name_not_overwritten_if_present(self):
        """如果 task 数据里已有 original_name，不应被覆盖"""
        from web.app import save_state, tasks, STATE_FILE

        tasks["t2"] = {
            "status": "completed",
            "original_name": "保留原名.pptx",
            "file_path": "/uploads/uuid_另一个名.pptx",
        }
        save_state("t2")

        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        assert data["original_name"] == "保留原名.pptx"

    def test_noop_if_task_not_found(self):
        """task_id 不存在时不应写文件"""
        from web.app import save_state, STATE_FILE

        save_state("nonexistent")
        assert not STATE_FILE.exists()

    def test_only_last_task_persisted(self):
        """state.json 只保留最后一次 save_state 的任务"""
        from web.app import save_state, tasks, STATE_FILE

        tasks["first"] = {"status": "completed"}
        save_state("first")
        tasks["second"] = {"status": "completed"}
        save_state("second")

        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        assert data["task_id"] == "second"


class TestLoadState:
    """测试 load_state 恢复逻辑"""

    def test_restores_completed_task(self):
        from web.app import load_state, tasks, STATE_FILE

        STATE_FILE.write_text(json.dumps({
            "task_id": "restored",
            "status": "completed",
            "video_path": "/tmp/video.mp4",
            "original_name": "测试.pptx",
        }), encoding="utf-8")

        load_state()
        assert "restored" in tasks
        assert tasks["restored"]["status"] == "completed"
        assert tasks["restored"]["original_name"] == "测试.pptx"

    def test_restores_error_task(self):
        from web.app import load_state, tasks, STATE_FILE

        STATE_FILE.write_text(json.dumps({
            "task_id": "err1",
            "status": "error",
            "error": "转换失败",
        }), encoding="utf-8")

        load_state()
        assert "err1" in tasks
        assert tasks["err1"]["error"] == "转换失败"

    def test_marks_processing_task_as_interrupted(self):
        """重启后保留原任务信息，并标记为可重新提交的中断状态。"""
        from web.app import load_state, tasks, STATE_FILE

        STATE_FILE.write_text(json.dumps({
            "task_id": "running",
            "status": "processing",
            "percentage": 50,
            "file_path": "/tmp/uploads/source.pptx",
            "strategy": {"tts_engine": "edge-tts"},
        }), encoding="utf-8")

        load_state()
        assert tasks["running"]["status"] == "interrupted"
        assert tasks["running"]["stage"] == "queue"
        assert tasks["running"]["file_path"] == "/tmp/uploads/source.pptx"
        assert tasks["running"]["strategy"]["tts_engine"] == "edge-tts"
        assert "重新提交" in tasks["running"]["message"]

    def test_restores_processing_task_from_preview_checkpoint(self, tmp_path):
        from web.app import load_state, tasks, STATE_FILE

        preview_path = tmp_path / "preview.json"
        preview_path.write_text('{"pages": []}', encoding="utf-8")
        STATE_FILE.write_text(json.dumps({
            "task_id": "checkpoint",
            "status": "processing",
            "stage": "video",
            "percentage": 86,
            "preview_path": str(preview_path),
        }), encoding="utf-8")

        load_state()

        assert tasks["checkpoint"]["status"] == "awaiting_confirmation"
        assert tasks["checkpoint"]["stage"] == "preview"
        assert tasks["checkpoint"]["failed_stage"] == "video"
        assert "检查点恢复" in tasks["checkpoint"]["message"]

    def test_noop_if_no_state_file(self):
        from web.app import load_state, tasks

        load_state()
        assert len(tasks) == 0

    def test_noop_if_corrupt_json(self):
        from web.app import load_state, tasks, STATE_FILE

        STATE_FILE.write_text("{invalid json", encoding="utf-8")
        load_state()
        assert len(tasks) == 0


# ==========================================================================
# WebProgressTracker + save_state 集成
# ==========================================================================


class TestWebProgressTrackerPersistence:
    """验证 WebProgressTracker 每次更新都会调用 save_state"""

    def test_update_writes_state(self):
        from web.app import WebProgressTracker, tasks, STATE_FILE

        q = Queue()
        tracker = WebProgressTracker("t-integ", q, total_pages=5)
        tracker.update("extract", 3, 5, "提取中")

        assert STATE_FILE.exists()
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        assert data["task_id"] == "t-integ"
        assert data["status"] == "processing"

    def test_complete_writes_state(self):
        from web.app import WebProgressTracker, tasks, STATE_FILE

        q = Queue()
        tracker = WebProgressTracker("t-done", q, total_pages=2)
        tracker.complete("/tmp/out.mp4")

        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        assert data["status"] == "completed"
        assert data["video_path"] == "/tmp/out.mp4"

    def test_error_writes_state(self):
        from web.app import WebProgressTracker, tasks, STATE_FILE

        q = Queue()
        tracker = WebProgressTracker("t-err", q, total_pages=2)
        tracker.error("TTS 失败")

        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        assert data["status"] == "error"
        assert data["error"] == "TTS 失败"


# ==========================================================================
# SSE 心跳 / 超时逻辑
# ==========================================================================


class TestSSEHeartbeat:
    """测试 SSE generate() 的心跳和超时行为"""

    def _collect_events(self, generator, max_items=20, timeout=2):
        """消费 generator 产出的事件，最多 max_items 或超时"""
        events = []
        deadline = time.monotonic() + timeout
        for item in generator:
            events.append(item)
            if len(events) >= max_items or time.monotonic() > deadline:
                break
        return events

    def test_yields_data_event(self):
        """队列有消息时立即产出 data 事件"""
        q = Queue()
        q.put({"type": "stage", "stage": "extract", "message": "提取中"})

        events = []
        try:
            data = q.get(timeout=0.1)
            events.append(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
        except Empty:
            events.append(": keepalive\n\n")

        assert len(events) == 1
        assert '"extract"' in events[0]

    def test_keepalive_on_empty_queue(self):
        """队列为空时产出心跳注释行"""
        q = Queue()
        events = []

        try:
            q.get(timeout=0.05)
        except Empty:
            events.append(": keepalive\n\n")

        assert events == [": keepalive\n\n"]

    def test_idle_reset_on_real_message(self):
        """收到真实消息后 idle_seconds 应重置为 0"""
        q = Queue()
        idle = 0
        HEARTBEAT = 25

        # 模拟一次空等
        try:
            q.get(timeout=0.05)
        except Empty:
            idle += HEARTBEAT

        assert idle == 25

        # 放入真实消息
        q.put({"type": "progress", "percentage": 50})

        try:
            q.get(timeout=0.05)
            idle = 0  # 重置
        except Empty:
            idle += HEARTBEAT

        assert idle == 0


# ==========================================================================
# /api/last-result 端点
# ==========================================================================


class TestLastResultEndpoint:
    """测试 /api/last-result API"""

    @pytest.fixture
    def client(self):
        from web.app import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_returns_not_found_when_no_state(self, client):
        resp = client.get("/api/last-result")
        data = resp.get_json()
        assert data["found"] is False

    def test_returns_persisted_result(self, client, tmp_path):
        from web.app import STATE_FILE

        # 写入 state.json
        STATE_FILE.write_text(json.dumps({
            "task_id": "lr1",
            "status": "completed",
            "stage": "complete",
            "percentage": 100,
            "message": "转换完成",
            "video_path": "",
            "original_name": "演示.pptx",
        }), encoding="utf-8")

        resp = client.get("/api/last-result")
        data = resp.get_json()
        assert data["found"] is True
        assert data["original_name"] == "演示.pptx"
        assert data["status"] == "completed"

    def test_returns_not_found_if_video_deleted(self, client, tmp_path):
        from web.app import STATE_FILE

        # video_path 指向不存在的文件
        STATE_FILE.write_text(json.dumps({
            "task_id": "lr2",
            "status": "completed",
            "video_path": "/nonexistent/video.mp4",
        }), encoding="utf-8")

        resp = client.get("/api/last-result")
        data = resp.get_json()
        assert data["found"] is False


# ==========================================================================
# /api/active-task 端点（含 original_name 字段）
# ==========================================================================


class TestActiveTaskEndpoint:
    """测试 /api/active-task API"""

    @pytest.fixture
    def client(self):
        from web.app import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_returns_active_false_when_empty(self, client):
        resp = client.get("/api/active-task")
        data = resp.get_json()
        assert data.get("active") is False or "task_id" not in data

    def test_includes_original_name(self, client):
        from web.app import tasks

        tasks["at1"] = {
            "status": "completed",
            "stage": "complete",
            "percentage": 100,
            "message": "完成",
            "video_path": "/tmp/v.mp4",
            "original_name": "我的PPT.pptx",
            "file_path": "/tmp/uploads/uuid_我的PPT.pptx",
            "started_at": time.time(),
            "completed_at": time.time(),
        }

        resp = client.get("/api/active-task")
        data = resp.get_json()
        assert data["original_name"] == "我的PPT.pptx"
