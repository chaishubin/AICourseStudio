"""Web 教案上传与课程路线调度测试。"""

import io
import json
from pathlib import Path
from queue import Queue


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

    def fake_compose(content, config, output):
        output.write_bytes(b"base-video")

    def fake_burn(video, subtitles, output):
        output.write_bytes(b"final-video")

    monkeypatch.setattr(Pipeline, "_generate_audio", fake_audio)
    monkeypatch.setattr(moviepy, "AudioFileClip", FakeAudioClip)
    monkeypatch.setattr(VideoComposer, "compose", fake_compose)
    monkeypatch.setattr(CoursePipeline, "_burn_subtitles", fake_burn)

    web_app.run_media_generation(task_id)

    assert captured_scripts == ["用户确认后的讲稿"]
    assert web_app.tasks[task_id]["status"] == "completed"
    assert Path(web_app.tasks[task_id]["video_path"]).exists()


def test_index_contains_editable_course_preview():
    import web.app as web_app

    response = web_app.app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert 'id="course-preview-module"' in html
    assert 'id="save-scripts-btn"' in html
    assert 'id="continue-course-btn"' in html
