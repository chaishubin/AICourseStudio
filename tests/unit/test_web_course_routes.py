"""Web 教案上传与课程路线调度测试。"""

import io
import json
from pathlib import Path
from queue import Queue

from PIL import Image


def test_upload_accepts_docx_and_uses_safe_disk_name(monkeypatch, temp_dir):
    import web.app as web_app

    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    client = web_app.app.test_client()
    response = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"docx-content"), "../../教案.docx")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["original_name"] == "../../教案.docx"
    stored = temp_dir / payload["file_path"].split("/")[-1]
    assert stored.parent == temp_dir
    assert stored.suffix == ".docx"
    assert stored.exists()


def test_logo_upload_accepts_image_and_rejects_fake_image(monkeypatch, temp_dir):
    import web.app as web_app

    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    image_bytes = io.BytesIO()
    Image.new("RGBA", (240, 80), (20, 80, 160, 255)).save(image_bytes, "PNG")
    image_bytes.seek(0)
    client = web_app.app.test_client()

    response = client.post(
        "/api/logo-upload",
        data={"logo": (image_bytes, "school.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert Path(response.get_json()["logo_path"]).exists()

    rejected = client.post(
        "/api/logo-upload",
        data={"logo": (io.BytesIO(b"not-an-image"), "fake.png")},
        content_type="multipart/form-data",
    )
    assert rejected.status_code == 400


def test_convert_dispatches_docx_to_course_pipeline(monkeypatch, temp_dir):
    import web.app as web_app

    source = temp_dir / "lesson.docx"
    source.write_bytes(b"placeholder")
    output = temp_dir / "outputs"
    monkeypatch.setattr(web_app, "OUTPUT_FOLDER", output)
    enqueue = []
    monkeypatch.setattr(
        web_app.conversion_queue,
        "enqueue",
        lambda *args, **kwargs: enqueue.append((args, kwargs)),
    )

    client = web_app.app.test_client()
    response = client.post(
        "/api/convert",
        json={
            "file_path": str(source),
            "original_name": "lesson.docx",
            "tts_engine": "volcengine",
            "voice": "zh_female_cancan_mars_bigtts",
            "llm_enabled": True,
            "llm_engine": "qwen",
        },
    )

    assert response.status_code == 200
    assert enqueue
    assert enqueue[0][0][0] is web_app.run_course_generation


def test_preview_can_be_edited_and_continued_once(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "preview-task"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    image = output_dir / "1" / "slide.png"
    image.parent.mkdir()
    image.write_bytes(b"png")
    source = temp_dir / "source.pptx"
    source.write_bytes(b"pptx")

    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "awaiting_confirmation",
            "file_path": str(source),
            "output_dir": str(output_dir),
            "original_name": "source.pptx",
            "media_options": {
                "tts_engine": "edge-tts",
                "tts_voice": "zh-CN-XiaoxiaoNeural",
                "tts_options": {},
                "render_engine": "spire",
            },
        }
    })
    monkeypatch.setattr(web_app, "progress_queues", {})
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")
    enqueued = []
    monkeypatch.setattr(
        web_app.conversion_queue,
        "enqueue",
        lambda *args, **kwargs: enqueued.append((args, kwargs)),
    )
    (output_dir / "preview.json").write_text(json.dumps({
        "task_id": task_id,
        "source_type": "presentation",
        "pages": [{
            "page_number": 1,
            "title": "第一页",
            "image_path": str(image),
            "script": "原讲稿",
            "original_script": "原讲稿",
        }],
    }), encoding="utf-8")

    client = web_app.app.test_client()
    preview_response = client.get(f"/api/course-preview/{task_id}")
    assert preview_response.status_code == 200
    assert preview_response.get_json()["pages"][0]["image_url"].startswith(
        "/api/slide-image"
    )

    save_response = client.patch(
        f"/api/course-preview/{task_id}",
        json={"pages": [{"page_number": 1, "script": "修改后的讲稿"}]},
    )
    assert save_response.status_code == 200
    saved = json.loads((output_dir / "preview.json").read_text(encoding="utf-8"))
    assert saved["pages"][0]["script"] == "修改后的讲稿"

    continue_response = client.post(f"/api/course-continue/{task_id}", json={})
    assert continue_response.status_code == 200
    assert web_app.tasks[task_id]["status"] == "pending"
    assert isinstance(web_app.progress_queues[task_id], Queue)
    assert enqueued[0][0] == (web_app.run_media_generation, task_id)

    duplicate = client.post(f"/api/course-continue/{task_id}", json={})
    assert duplicate.status_code == 409


def test_preview_can_be_cancelled_and_removed_from_state(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "cancel-preview-task"
    state_file = temp_dir / "state.json"
    state_file.write_text(json.dumps([
        {"task_id": task_id, "status": "awaiting_confirmation"},
        {"task_id": "completed-task", "status": "completed"},
    ]), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {"status": "awaiting_confirmation"},
    })
    monkeypatch.setattr(web_app, "progress_queues", {task_id: Queue()})
    monkeypatch.setattr(web_app, "STATE_FILE", state_file)

    response = web_app.app.test_client().post(
        f"/api/course-cancel/{task_id}"
    )

    assert response.status_code == 200
    assert task_id not in web_app.tasks
    assert task_id not in web_app.progress_queues
    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert [item["task_id"] for item in persisted] == ["completed-task"]


def test_completed_task_can_be_physically_deleted(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "completed-delete-task"
    output_root = temp_dir / "outputs"
    output_dir = output_root / task_id
    output_dir.mkdir(parents=True)
    (output_dir / "video.mp4").write_bytes(b"video")
    state_file = output_root / "state.json"
    state_file.write_text(json.dumps([
        {
            "task_id": task_id,
            "status": "completed",
            "output_dir": str(output_dir),
        },
        {"task_id": "keep-task", "status": "completed"},
    ]), encoding="utf-8")
    monkeypatch.setattr(web_app, "OUTPUT_FOLDER", output_root)
    monkeypatch.setattr(web_app, "STATE_FILE", state_file)
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
    assert task_id not in web_app.tasks
    assert task_id not in web_app.progress_queues
    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert [item["task_id"] for item in persisted] == ["keep-task"]


def test_task_delete_rejects_running_and_unsafe_paths(monkeypatch, temp_dir):
    import web.app as web_app

    output_root = temp_dir / "outputs"
    output_root.mkdir()
    outside = temp_dir / "outside"
    outside.mkdir()
    monkeypatch.setattr(web_app, "OUTPUT_FOLDER", output_root)
    monkeypatch.setattr(web_app, "tasks", {
        "running-task": {
            "status": "processing",
            "output_dir": str(output_root / "running-task"),
        },
        "unsafe-task": {
            "status": "error",
            "output_dir": str(outside),
        },
    })
    client = web_app.app.test_client()

    assert client.delete("/api/tasks/running-task").status_code == 409
    assert client.delete("/api/tasks/unsafe-task").status_code == 400
    assert outside.exists()


def test_task_delete_accepts_interrupted_and_awaiting_confirmation(
    monkeypatch,
    temp_dir,
):
    import web.app as web_app

    output_root = temp_dir / "outputs"
    output_root.mkdir()
    state_file = output_root / "state.json"
    task_ids = ("interrupted-task", "preview-task")
    statuses = ("interrupted", "awaiting_confirmation")
    task_map = {}
    for task_id, status in zip(task_ids, statuses):
        output_dir = output_root / task_id
        output_dir.mkdir()
        task_map[task_id] = {
            "status": status,
            "output_dir": str(output_dir),
        }
    state_file.write_text(json.dumps([
        {"task_id": task_id, **task_map[task_id]}
        for task_id in task_ids
    ]), encoding="utf-8")
    monkeypatch.setattr(web_app, "OUTPUT_FOLDER", output_root)
    monkeypatch.setattr(web_app, "STATE_FILE", state_file)
    monkeypatch.setattr(web_app, "tasks", task_map)
    monkeypatch.setattr(web_app, "progress_queues", {})
    monkeypatch.setattr(web_app, "cancellation_events", {})
    client = web_app.app.test_client()

    for task_id in task_ids:
        response = client.delete(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert not (output_root / task_id).exists()

    assert web_app.tasks == {}
    assert json.loads(state_file.read_text(encoding="utf-8")) == []


def test_task_list_includes_source_path_for_preview_retry(monkeypatch, temp_dir):
    import web.app as web_app

    source = temp_dir / "lesson.docx"
    source.write_bytes(b"docx")
    monkeypatch.setattr(web_app, "tasks", {
        "preview-task": {
            "status": "awaiting_confirmation",
            "original_name": "lesson.docx",
            "file_path": str(source),
        },
    })

    response = web_app.app.test_client().get("/api/tasks")

    assert response.status_code == 200
    assert response.get_json()["tasks"][0]["file_path"] == str(source)


def test_media_generation_uses_confirmed_scripts(monkeypatch, temp_dir):
    import moviepy
    import web.app as web_app
    from vidppt.course_pipeline import CoursePipeline
    from vidppt.pipeline import Pipeline
    from vidppt.utils.video_composer import VideoComposer

    task_id = "media-task"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    source = temp_dir / "source.pptx"
    source.write_bytes(b"pptx")
    slide = output_dir / "1" / "slide.png"
    slide.parent.mkdir()
    slide.write_bytes(b"png")
    preview = {
        "task_id": task_id,
        "source_type": "presentation",
        "pages": [{
            "page_number": 1,
            "title": "第一页",
            "image_path": str(slide),
            "script": "用户确认后的讲稿",
            "original_script": "AI 原稿",
        }],
    }
    (output_dir / "preview.json").write_text(
        json.dumps(preview, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "pending",
            "file_path": str(source),
            "output_dir": str(output_dir),
            "original_name": "source.pptx",
            "media_options": {
                "tts_engine": "edge-tts",
                "tts_voice": "zh-CN-XiaoxiaoNeural",
                "tts_options": {},
                "render_engine": "spire",
            },
        }
    })
    monkeypatch.setattr(web_app, "progress_queues", {task_id: Queue()})
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")
    captured_scripts = []

    def fake_audio(self, content, progress):
        for page in content.pages:
            captured_scripts.append(page.text)
            page.audio = output_dir / str(page.page_number) / "audio.mp3"
            page.audio.write_bytes(b"audio")

    class FakeAudioClip:
        duration = 2.0

        def __init__(self, path):
            self.path = path

        def close(self):
            pass

    def fake_compose(
        content, config, output, progress_callback=None, cancel_check=None
    ):
        if progress_callback:
            progress_callback(0.5)
            progress_callback(1.0)
        output.write_bytes(b"base-video")

    def fake_burn(
        video, subtitles, output, config,
        progress_callback=None, cancel_check=None,
    ):
        if progress_callback:
            progress_callback(0.5)
            progress_callback(1.0)
        output.write_bytes(b"final-video")

    monkeypatch.setattr(Pipeline, "_generate_audio", fake_audio)
    monkeypatch.setattr(moviepy, "AudioFileClip", FakeAudioClip)
    monkeypatch.setattr(VideoComposer, "compose", fake_compose)
    monkeypatch.setattr(CoursePipeline, "_burn_subtitles", fake_burn)

    web_app.run_media_generation(task_id)

    assert captured_scripts == ["用户确认后的讲稿"]
    assert web_app.tasks[task_id]["status"] == "completed"
    assert Path(web_app.tasks[task_id]["video_path"]).exists()
    video_progress = [
        event["percentage"]
        for event in list(web_app.progress_queues[task_id].queue)
        if event.get("type") == "progress" and event.get("stage") == "video"
    ]
    assert any(83 < value < 100 for value in video_progress)
    assert video_progress[-1] == 100


def test_stop_requests_cancellation_for_processing_task(monkeypatch, temp_dir):
    import threading
    import web.app as web_app

    task_id = "stop-task"
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "processing",
            "stage": "video",
            "percentage": 90,
            "output_dir": str(temp_dir),
        }
    })
    monkeypatch.setattr(web_app, "progress_queues", {task_id: Queue()})
    monkeypatch.setattr(web_app, "cancellation_events", {
        task_id: threading.Event()
    })
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")

    response = web_app.app.test_client().post(f"/api/stop/{task_id}")

    assert response.status_code == 200
    assert web_app.cancellation_events[task_id].is_set()
    assert web_app.tasks[task_id]["stop_requested"] is True


def test_stage_event_carries_non_regressing_percentage(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "stage-progress"
    queue = Queue()
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {"status": "processing", "percentage": 50}
    })
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")
    tracker = web_app.WebProgressTracker(task_id, queue)

    tracker.set_stage("render", "生成 PPT")

    event = list(queue.queue)[0]
    assert event["type"] == "stage"
    assert event["percentage"] == 50
    assert web_app.tasks[task_id]["percentage"] == 50


def test_media_failure_rolls_back_and_keeps_preview(monkeypatch, temp_dir):
    import web.app as web_app
    from vidppt.pipeline import Pipeline

    task_id = "rollback-media"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    source = temp_dir / "source.pptx"
    source.write_bytes(b"pptx")
    slide = output_dir / "1" / "slide.png"
    slide.parent.mkdir()
    slide.write_bytes(b"png")
    (output_dir / "preview.json").write_text(json.dumps({
        "task_id": task_id,
        "source_type": "presentation",
        "pages": [{
            "page_number": 1,
            "title": "第一页",
            "image_path": str(slide),
            "script": "需要配音",
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "pending",
            "file_path": str(source),
            "output_dir": str(output_dir),
            "preview_path": str(output_dir / "preview.json"),
            "media_options": {
                "tts_engine": "edge-tts",
                "tts_voice": "zh-CN-XiaoxiaoNeural",
                "tts_options": {},
                "render_engine": "spire",
            },
        }
    })
    queue = Queue()
    monkeypatch.setattr(web_app, "progress_queues", {task_id: queue})
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")
    monkeypatch.setattr(Pipeline, "_generate_audio", lambda self, content, progress: None)

    web_app.run_media_generation(task_id)

    assert web_app.tasks[task_id]["status"] == "awaiting_confirmation"
    assert web_app.tasks[task_id]["failed_stage"] == "配音生成"
    assert (output_dir / "preview.json").exists()
    assert any(event["type"] == "rollback" for event in list(queue.queue))


def test_editing_script_removes_only_changed_page_audio(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "edit-audio"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    for page_number in (1, 2):
        page_dir = output_dir / str(page_number)
        page_dir.mkdir()
        (page_dir / "audio.mp3").write_bytes(b"audio")
    (output_dir / "preview.json").write_text(json.dumps({
        "pages": [
            {"page_number": 1, "script": "旧讲稿一"},
            {"page_number": 2, "script": "旧讲稿二"},
        ]
    }), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {"output_dir": str(output_dir)}
    })

    web_app._update_preview_scripts(task_id, [
        {"page_number": 1, "script": "新讲稿一"},
        {"page_number": 2, "script": "旧讲稿二"},
    ])

    assert not (output_dir / "1" / "audio.mp3").exists()
    assert (output_dir / "2" / "audio.mp3").exists()


def test_index_contains_editable_course_preview():
    import web.app as web_app

    response = web_app.app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert 'id="course-preview-module"' in html
    assert 'id="cancel-course-btn"' in html
    assert 'id="save-scripts-btn"' in html
    assert 'id="continue-course-btn"' in html
    assert 'id="refinement-level"' in html
    assert 'id="custom-voice"' in html
    assert 'id="ppt-footer-text"' in html


def test_voice_catalog_is_filtered_by_engine():
    import web.app as web_app

    response = web_app.app.test_client().get("/api/voices?engine=volcengine")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["engine"] == "volcengine"
    assert payload["count"] == len(payload["voices"])
    assert payload["count"] > 20
    assert all("id" in voice and "name" in voice for voice in payload["voices"])


def test_voice_preview_generates_and_reuses_cached_audio(monkeypatch, temp_dir):
    import web.app as web_app

    preview_folder = temp_dir / "voice-previews"
    preview_folder.mkdir()
    generated = []

    def fake_synthesize(engine, voice, output_path):
        generated.append((engine, voice))
        output_path.write_bytes(b"preview-audio")

    monkeypatch.setattr(web_app, "VOICE_PREVIEW_FOLDER", preview_folder)
    monkeypatch.setattr(web_app, "_synthesize_voice_preview", fake_synthesize)
    client = web_app.app.test_client()
    payload = {
        "engine": "volcengine",
        "voice": "zh_female_cancan_mars_bigtts",
    }

    first = client.post("/api/voice-preview", json=payload)
    second = client.post("/api/voice-preview", json=payload)

    assert first.status_code == 200
    assert first.data == b"preview-audio"
    assert second.status_code == 200
    assert generated == [
        ("volcengine", "zh_female_cancan_mars_bigtts"),
    ]
