"""Web 教案上传与课程路线调度测试。"""

import io
import json
import sys
from pathlib import Path
from queue import Queue
from types import SimpleNamespace

from PIL import Image


def test_render_only_keeps_rendered_status_after_final_progress(monkeypatch, temp_dir):
    import web.app as web_app
    from vidppt.core import registry

    task_id = "render-only-task"
    queue = Queue()
    monkeypatch.setattr(web_app, "tasks", {task_id: {"status": "pending"}})
    monkeypatch.setattr(web_app, "progress_queues", {task_id: queue})
    monkeypatch.setattr(web_app, "save_state", lambda _task_id: None)

    class Processor:
        def render_pages(self, _config):
            return [temp_dir / "1" / "slide.png"]

    monkeypatch.setattr(
        registry.ProcessorRegistry,
        "get_processor",
        lambda _path: Processor,
    )

    web_app.run_render_only(
        task_id,
        str(temp_dir / "source.pptx"),
        temp_dir / task_id,
        "libreoffice",
    )

    assert web_app.tasks[task_id]["status"] == "rendered"
    assert web_app.tasks[task_id]["slide_count"] == 1
    assert any(event.get("type") == "rendered" for event in list(queue.queue))


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


def test_artifact_filename_stem_bounds_long_chinese_names():
    import web.app as web_app

    title = "从匠人到巨匠——工匠成长路径与方法" + "专业技术人员继续教育公需课" * 20
    first = web_app._artifact_filename_stem(title)
    second = web_app._artifact_filename_stem(title)

    assert first == second
    assert len(first.encode("utf-8")) <= 120
    assert first.endswith(web_app.hashlib.sha256(
        web_app._safe_filename_stem(title).encode("utf-8")
    ).hexdigest()[:10])


def test_upload_accepts_epub_and_uses_safe_disk_name(monkeypatch, temp_dir):
    import web.app as web_app

    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    client = web_app.app.test_client()
    response = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"epub-content"), "课程.epub")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["original_name"] == "课程.epub"
    assert Path(payload["file_path"]).suffix == ".epub"


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
            "course_name": "自定义课程名",
            "tts_engine": "volcengine",
            "voice": "zh_female_cancan_mars_bigtts",
            "llm_enabled": True,
            "llm_engine": "qwen",
            "narration_style": "case",
            "target_duration_minutes": 15,
            "quality_mode": "balanced",
            "visual_theme": "technology",
            "burn_subtitles": False,
            "subtitle_y": 940,
            "subtitle_height": 80,
            "subtitle_font_size": 48,
            "subtitle_background_opacity": 0.5,
            "video_width": 1280,
            "video_height": 720,
            "video_fps": 24,
            "video_preset": "ultrafast",
            "video_crf": 28,
            "audio_bitrate": "96k",
        },
    )

    assert response.status_code == 200
    assert enqueue
    assert enqueue[0][0][0] is web_app.run_course_generation
    assert enqueue[0][0][-1] == "technology"
    task_id = response.get_json()["task_id"]
    assert web_app.tasks[task_id]["course_name"] == "自定义课程名"
    assert web_app.tasks[task_id]["strategy"]["burn_subtitles"] is False
    assert web_app.tasks[task_id]["strategy"]["quality_mode"] == "balanced"
    assert web_app.tasks[task_id]["strategy"]["narration_style"] == "case"
    assert web_app.tasks[task_id]["strategy"]["target_duration_minutes"] == 15
    assert web_app.tasks[task_id]["strategy"]["subtitle_y"] == 940
    assert web_app.tasks[task_id]["strategy"]["subtitle_font_size"] == 48
    assert web_app.tasks[task_id]["strategy"]["video_width"] == 1280
    assert web_app.tasks[task_id]["strategy"]["video_preset"] == "ultrafast"
    assert web_app.tasks[task_id]["strategy"]["video_crf"] == 28
    assert web_app.tasks[task_id]["media_options"]["burn_subtitles"] is False
    assert web_app.tasks[task_id]["media_options"]["subtitle_height"] == 80
    assert web_app.tasks[task_id]["media_options"]["video_height"] == 720
    assert web_app.tasks[task_id]["media_options"]["audio_bitrate"] == "96k"
    assert (
        web_app.tasks[task_id]["media_options"]["subtitle_background_opacity"]
        == 0.5
    )


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
    preview_image_url = preview_response.get_json()["pages"][0]["image_url"]
    assert preview_image_url.startswith(
        "/api/slide-image"
    )
    assert "&v=" in preview_image_url
    preview_payload = preview_response.get_json()
    assert preview_payload["duration_estimate"]["total_seconds"] == 4.0
    assert preview_payload["pages"][0]["estimated_seconds"] == 4.0

    image_response = client.get(preview_image_url)
    assert image_response.status_code == 200
    assert image_response.headers["Cache-Control"] == "no-store, max-age=0"

    audio_path = output_dir / "1" / "audio.mp3"
    audio_path.write_bytes(b"page-audio")
    audio_response = client.post(
        f"/api/course-preview/{task_id}/page-audio",
        json={"page_number": 1},
    )
    assert audio_response.status_code == 200
    audio_url = audio_response.get_json()["audio_url"]
    assert audio_url.startswith(f"/api/course-preview/{task_id}/audio/1")
    assert "&v=" in audio_url or "?v=" in audio_url
    playback_response = client.get(audio_url)
    assert playback_response.status_code == 200
    assert playback_response.data == b"page-audio"

    save_response = client.patch(
        f"/api/course-preview/{task_id}",
        json={"pages": [{"page_number": 1, "script": "修改后的讲稿"}]},
    )
    assert save_response.status_code == 200
    saved = json.loads((output_dir / "preview.json").read_text(encoding="utf-8"))
    assert saved["pages"][0]["script"] == "修改后的讲稿"
    assert save_response.get_json()["duration_estimate"]["total_seconds"] == 4.0

    continue_response = client.post(
        f"/api/course-continue/{task_id}",
        json={
            "tts_engine": "edge-tts",
            "voice": "zh-CN-XiaoxiaoNeural",
            "video_width": 1280,
            "video_height": 720,
            "video_preset": "superfast",
            "video_crf": 26,
            "audio_loudness_lufs": -18,
            "packaging_template": "university",
            "packaging_organization": "测试大学",
            "packaging_department": "人工智能学院",
            "packaging_instructor": "王老师",
            "packaging_instructor_title": "教授",
            "packaging_copyright": "测试大学版权所有",
            "packaging_transition_seconds": 0.35,
            "packaging_duration_seconds": 3.5,
            "packaging_outro_text": "下节课见",
            "packaging_apply_to_segments": True,
            "packaging_use_slide_background": True,
            "packaging_enable_motion": True,
            "packaging_enable_music": False,
            "packaging_intro_label": "在线精品课",
            "packaging_intro_title": "课程导入",
            "packaging_intro_subtitle": "从问题到方法",
            "packaging_intro_duration_seconds": 5,
            "packaging_outro_title": "课程小结",
            "packaging_outro_subtitle": "请完成课后练习",
            "packaging_outro_duration_seconds": 6,
            "packaging_accent_color": "#1D4ED8",
            "packaging_primary_color": "#102A43",
            "packaging_text_color": "#F8FAFC",
            "packaging_background_style": "gradient",
            "packaging_logo_position": "top-left",
            "packaging_motion_style": "pan",
            "packaging_music_style": "bright",
            "packaging_intro_content_x": 12,
            "packaging_intro_content_y": 28,
            "packaging_intro_content_width": 62,
            "packaging_outro_content_x": 18,
            "packaging_outro_content_y": 36,
            "packaging_outro_content_width": 58,
            "packaging_intro_logo_position": "custom",
            "packaging_intro_logo_x": 71.5,
            "packaging_intro_logo_y": 14,
        },
    )
    assert continue_response.status_code == 200
    assert web_app.tasks[task_id]["status"] == "pending"
    assert web_app.tasks[task_id]["media_options"]["video_width"] == 1280
    assert web_app.tasks[task_id]["media_options"]["video_preset"] == "superfast"
    assert web_app.tasks[task_id]["media_options"]["audio_loudness_lufs"] == -18
    packaging = web_app.tasks[task_id]["media_options"]["course_packaging"]
    assert packaging["template"] == "university"
    assert packaging["organization"] == "测试大学"
    assert packaging["department"] == "人工智能学院"
    assert packaging["instructor"] == "王老师"
    assert packaging["instructor_title"] == "教授"
    assert packaging["copyright"] == "测试大学版权所有"
    assert packaging["transition_seconds"] == 0.35
    assert packaging["duration_seconds"] == 3.5
    assert packaging["outro_text"] == "下节课见"
    assert packaging["apply_to_segments"] is True
    assert packaging["use_slide_background"] is True
    assert packaging["enable_motion"] is True
    assert packaging["enable_music"] is False
    assert packaging["intro_label"] == "在线精品课"
    assert packaging["intro_title"] == "课程导入"
    assert packaging["intro_subtitle"] == "从问题到方法"
    assert packaging["intro_duration_seconds"] == 5
    assert packaging["outro_title"] == "课程小结"
    assert packaging["outro_subtitle"] == "请完成课后练习"
    assert packaging["outro_duration_seconds"] == 6
    assert packaging["accent_color"] == "#1D4ED8"
    assert packaging["primary_color"] == "#102A43"
    assert packaging["text_color"] == "#F8FAFC"
    assert packaging["background_style"] == "gradient"
    assert packaging["logo_position"] == "top-left"
    assert packaging["motion_style"] == "pan"
    assert packaging["music_style"] == "bright"
    assert packaging["intro_content_x"] == 12
    assert packaging["intro_content_y"] == 28
    assert packaging["intro_content_width"] == 62
    assert packaging["outro_content_x"] == 18
    assert packaging["outro_content_y"] == 36
    assert packaging["outro_content_width"] == 58
    assert packaging["intro_logo_position"] == "custom"
    assert packaging["intro_logo_x"] == 71.5
    assert packaging["intro_logo_y"] == 14
    assert isinstance(web_app.progress_queues[task_id], Queue)
    assert enqueued[0][0] == (web_app.run_media_generation, task_id)

    duplicate = client.post(f"/api/course-continue/{task_id}", json={})
    assert duplicate.status_code == 409


def test_review_presentation_can_be_downloaded_and_replaced(monkeypatch, temp_dir):
    import web.app as web_app
    from vidppt.processors.ppt_processor import PPTProcessor

    task_id = "edit-presentation-task"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    source = temp_dir / "source.pptx"
    from pptx import Presentation
    deck = Presentation()
    deck.slides.add_slide(deck.slide_layouts[6])
    deck.save(str(source))
    original_bytes = source.read_bytes()
    old_image = output_dir / "1" / "slide.png"
    old_image.parent.mkdir()
    old_image.write_bytes(b"old")
    new_image = output_dir / "1" / "edited.png"
    new_image.write_bytes(b"new")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "awaiting_confirmation",
            "file_path": str(source),
            "output_dir": str(output_dir),
            "original_name": "课程.pptx",
            "media_options": {"render_engine": "spire"},
        }
    })
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")
    (output_dir / "preview.json").write_text(json.dumps({
        "task_id": task_id,
        "source_type": "presentation",
        "presentation_path": str(source),
        "pages": [{
            "page_number": 1,
            "title": "旧标题",
            "image_path": str(old_image),
            "script": "保留讲稿",
            "original_script": "原讲稿",
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(
        PPTProcessor,
        "process",
        lambda self, config: SimpleNamespace(pages=[
            SimpleNamespace(
                page_number=1,
                text="修改后的标题",
                slide_image=new_image,
            )
        ]),
    )

    client = web_app.app.test_client()
    download = client.get(f"/api/course-presentation/{task_id}")
    assert download.status_code == 200
    assert download.data == original_bytes

    upload = client.post(
        f"/api/course-presentation/{task_id}",
        data={"presentation": (io.BytesIO(original_bytes), "edited.pptx")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 200
    payload = upload.get_json()
    assert payload["pages"][0]["script"] == "保留讲稿"
    assert payload["pages"][0]["title"] == "修改后的标题"
    assert "&v=" in payload["pages"][0]["image_url"]
    assert (output_dir / "reviewed.pptx").read_bytes() == original_bytes


def test_course_review_runs_and_persists_result(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "review-task"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    preview_path = output_dir / "preview.json"
    preview_path.write_text(json.dumps({
        "task_id": task_id,
        "source_type": "lesson_plan",
        "pages": [
            {
                "page_number": 1,
                "title": "导入",
                "image_path": str(output_dir / "1.png"),
                "script": "第一页讲稿",
            },
            {
                "page_number": 2,
                "title": "总结",
                "image_path": str(output_dir / "2.png"),
                "script": "第二页讲稿",
            },
        ],
    }, ensure_ascii=False), encoding="utf-8")

    class FakeReviewer:
        def review(self, preview, mode):
            assert mode == "sample"
            assert len(preview["pages"]) == 2
            return {
                "status": "warning",
                "mode": mode,
                "provider": "deepseek",
                "model": "fake-model",
                "summary": "需要优化承接",
                "findings": [{
                    "page_number": 2,
                    "level": "warning",
                    "category": "衔接",
                    "message": "转场略硬",
                    "suggestion": "增加承上启下句",
                    "replacement_script": "下面我们进入总结环节。第二页讲稿",
                }],
                "reviewed_pages": [1, 2],
                "estimated_cost_cny": 0.01,
            }

    monkeypatch.setattr(web_app, "CourseReviewer", FakeReviewer)
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "awaiting_confirmation",
            "output_dir": str(output_dir),
            "original_name": "lesson.docx",
            "strategy": {"quality_mode": "balanced"},
        },
    })
    client = web_app.app.test_client()

    response = client.post(f"/api/course-review/{task_id}", json={"mode": "sample"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ai_review"]["status"] == "warning"
    assert payload["ai_review"]["provider"] == "deepseek"
    assert payload["ai_review"]["findings"][0]["replacement_script"].startswith("下面")
    saved = json.loads(preview_path.read_text(encoding="utf-8"))
    assert saved["ai_review"]["findings"][0]["page_number"] == 2


def test_course_review_get_returns_existing_result(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "review-get-task"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    review = {"status": "passed", "mode": "full", "findings": []}
    (output_dir / "preview.json").write_text(json.dumps({
        "task_id": task_id,
        "pages": [],
        "ai_review": review,
    }), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "awaiting_confirmation",
            "output_dir": str(output_dir),
            "strategy": {"quality_mode": "premium"},
        },
    })

    response = web_app.app.test_client().get(f"/api/course-review/{task_id}")

    assert response.status_code == 200
    assert response.get_json()["quality_mode"] == "premium"
    assert response.get_json()["ai_review"] == review


def test_course_review_incomplete_response_persists_failure(monkeypatch, temp_dir):
    import web.app as web_app
    from vidppt.review.course_reviewer import CourseReviewer

    class IncompleteEngine:
        def summarize(self, prompt, **kwargs):
            assert json.loads(prompt)["pages"][0]["script"] == "实际课程讲稿"
            return json.dumps({
                "status": "warning", "summary": "未提供课程页面内容，无法进行实际质检。",
                "findings": [],
            }, ensure_ascii=False)

    task_id = "incomplete-review"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    preview_path = output_dir / "preview.json"
    preview_path.write_text(json.dumps({
        "pages": [{"page_number": 1, "script": "实际课程讲稿"}],
        "ai_review": {"status": "passed", "reviewed_pages": [1]},
    }), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {task_id: {
        "status": "awaiting_confirmation", "output_dir": str(output_dir),
    }})
    monkeypatch.setattr(web_app, "CourseReviewer", lambda: CourseReviewer(engine=IncompleteEngine()))

    response = web_app.app.test_client().post(
        f"/api/course-review/{task_id}", json={"mode": "full"},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "未确认完成" in payload["error"]
    review = payload["ai_review"]
    assert review["review_completed"] is False
    assert review["status"] == "failed"
    assert review["reviewed_pages"] == []
    assert json.loads(preview_path.read_text(encoding="utf-8"))["ai_review"] == review
    assert web_app.tasks[task_id]["ai_review"] == review


def test_artifact_downloads_use_original_upload_name(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "named-download-task"
    artifacts = {}
    for extension in (".mp4", ".srt", ".pptx", ".json"):
        path = temp_dir / f"internal-uuid{extension}"
        path.write_bytes(extension.encode())
        artifacts[extension] = path
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "original_name": "../../课程设计.docx",
            "video_path": str(artifacts[".mp4"]),
            "subtitles_path": str(artifacts[".srt"]),
            "presentation_path": str(artifacts[".pptx"]),
            "course_json_path": str(artifacts[".json"]),
        }
    })
    client = web_app.app.test_client()

    for extension, path in artifacts.items():
        response = client.get(
            "/api/download",
            query_string={"task_id": task_id, "path": str(path)},
        )
        assert response.status_code == 200
        disposition = response.headers["Content-Disposition"]
        assert f"filename*=UTF-8''%E8%AF%BE%E7%A8%8B%E8%AE%BE%E8%AE%A1{extension}" in disposition


def test_video_download_prefers_course_name(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "course-name-download-task"
    video = temp_dir / "internal-uuid.mp4"
    video.write_bytes(b".mp4")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "original_name": "../../上传文件.pptx",
            "course_name": "第一讲：课程导入",
            "video_path": str(video),
        }
    })
    client = web_app.app.test_client()

    response = client.get(
        "/api/download",
        query_string={"task_id": task_id, "path": str(video)},
    )

    assert response.status_code == 200
    disposition = response.headers["Content-Disposition"]
    assert "filename*=UTF-8''%E7%AC%AC%E4%B8%80%E8%AE%B2_%E8%AF%BE%E7%A8%8B%E5%AF%BC%E5%85%A5.mp4" in disposition


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


def test_task_delete_rejects_running_and_ignores_unsafe_recorded_path(
    monkeypatch,
    temp_dir,
):
    import web.app as web_app

    output_root = temp_dir / "outputs"
    output_root.mkdir()
    state_file = output_root / "state.json"
    state_file.write_text(json.dumps([]), encoding="utf-8")
    outside = temp_dir / "outside"
    outside.mkdir()
    monkeypatch.setattr(web_app, "OUTPUT_FOLDER", output_root)
    monkeypatch.setattr(web_app, "STATE_FILE", state_file)
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
    assert client.delete("/api/tasks/unsafe-task").status_code == 200
    assert outside.exists()
    assert "unsafe-task" not in web_app.tasks


def test_task_delete_accepts_terminal_non_video_statuses(
    monkeypatch,
    temp_dir,
):
    import web.app as web_app

    output_root = temp_dir / "outputs"
    output_root.mkdir()
    state_file = output_root / "state.json"
    task_ids = ("interrupted-task", "preview-task", "rendered-task")
    statuses = ("interrupted", "awaiting_confirmation", "rendered")
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


def test_retry_video_reuses_audio_and_enqueues_media(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "retry-video-task"
    output_dir = temp_dir / "outputs" / task_id
    audio_dir = output_dir / "1"
    audio_dir.mkdir(parents=True)
    audio_path = audio_dir / "audio.mp3"
    audio_path.write_bytes(b"audio")
    (output_dir / "old.mp4").write_bytes(b"video")
    (output_dir / "old.srt").write_text("subtitle", encoding="utf-8")
    preview_path = output_dir / "preview.json"
    preview_path.write_text(json.dumps({
        "task_id": task_id,
        "pages": [{"page_number": 1, "script": "讲稿", "image_path": "slide.png"}],
    }), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "completed",
            "output_dir": str(output_dir),
            "preview_path": str(preview_path),
        }
    })
    monkeypatch.setattr(web_app, "progress_queues", {})
    enqueued = []
    monkeypatch.setattr(
        web_app.conversion_queue,
        "enqueue",
        lambda func, *args: enqueued.append((func, args)),
    )

    response = web_app.app.test_client().post(
        f"/api/tasks/{task_id}/retry",
        json={"stage": "video"},
    )

    assert response.status_code == 200
    assert audio_path.exists()
    assert (output_dir / "old.mp4").exists()
    assert (output_dir / "old.srt").exists()
    assert web_app.tasks[task_id]["status"] == "queued"
    assert enqueued == [(web_app.run_media_generation, (task_id,))]


def test_retry_single_page_tts_only_removes_selected_audio(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "retry-page-task"
    output_dir = temp_dir / "outputs" / task_id
    for page_number in (1, 2):
        page_dir = output_dir / str(page_number)
        page_dir.mkdir(parents=True)
        (page_dir / "audio.mp3").write_bytes(b"audio")
    preview_path = output_dir / "preview.json"
    preview_path.write_text(json.dumps({
        "task_id": task_id,
        "pages": [{"page_number": 1, "script": "讲稿", "image_path": "slide.png"}],
    }), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "awaiting_confirmation",
            "output_dir": str(output_dir),
            "preview_path": str(preview_path),
        }
    })
    monkeypatch.setattr(web_app, "progress_queues", {})
    monkeypatch.setattr(web_app.conversion_queue, "enqueue", lambda *args: None)

    response = web_app.app.test_client().post(
        f"/api/tasks/{task_id}/retry",
        json={"stage": "page_tts", "page_number": 2},
    )

    assert response.status_code == 200
    assert (output_dir / "1" / "audio.mp3").exists()
    assert not (output_dir / "2" / "audio.mp3").exists()


def test_resume_queued_video_retry_uses_media_checkpoint(monkeypatch, temp_dir):
    import web.app as web_app

    source = temp_dir / "lesson.docx"
    source.write_bytes(b"docx")
    output_dir = temp_dir / "outputs" / "resume-video-task"
    output_dir.mkdir(parents=True)
    preview_path = output_dir / "preview.json"
    preview_path.write_text(json.dumps({"pages": []}), encoding="utf-8")
    task_id = "resume-video-task"
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "queued",
            "file_path": str(source),
            "output_dir": str(output_dir),
            "preview_path": str(preview_path),
            "retry_stage": "video",
        },
    })
    monkeypatch.setattr(web_app, "progress_queues", {})
    enqueued = []
    monkeypatch.setattr(
        web_app.conversion_queue,
        "enqueue",
        lambda func, *args: enqueued.append((func, args)),
    )

    web_app.resume_queued_tasks()

    assert enqueued == [(web_app.run_media_generation, (task_id,))]


def test_task_list_includes_source_path_for_preview_retry(monkeypatch, temp_dir):
    import web.app as web_app

    source = temp_dir / "lesson.docx"
    source.write_bytes(b"docx")
    video = temp_dir / "outputs" / "lesson-video.mp4"
    video.parent.mkdir()
    video.write_bytes(b"mp4")
    monkeypatch.setattr(web_app, "tasks", {
        "preview-task": {
            "status": "awaiting_confirmation",
            "original_name": "lesson.docx",
            "file_path": str(source),
            "video_path": str(video),
        },
    })

    response = web_app.app.test_client().get("/api/tasks")

    assert response.status_code == 200
    task = response.get_json()["tasks"][0]
    assert task["file_path"] == str(source)
    assert task["source_file_exists"] is True
    assert task["video_name"] == "lesson-video.mp4"


def test_source_file_can_be_downloaded_and_previewed(monkeypatch, temp_dir):
    import web.app as web_app

    upload_dir = temp_dir / "uploads"
    upload_dir.mkdir()
    source = upload_dir / "uuid-lesson.pdf"
    source.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", upload_dir)
    monkeypatch.setattr(web_app, "tasks", {
        "source-task": {
            "status": "completed",
            "original_name": "../../课程资料.pdf",
            "file_path": str(source),
        },
    })
    client = web_app.app.test_client()

    download = client.get("/api/tasks/source-task/source-file")
    preview = client.get(
        "/api/tasks/source-task/source-file",
        query_string={"mode": "preview"},
    )

    assert download.status_code == 200
    assert download.data == b"%PDF-1.4"
    assert "filename*=UTF-8''%E8%AF%BE%E7%A8%8B%E8%B5%84%E6%96%99.pdf" in (
        download.headers["Content-Disposition"]
    )
    assert preview.status_code == 200
    assert "attachment" not in preview.headers.get("Content-Disposition", "")


def test_source_file_rejects_paths_outside_upload_folder(monkeypatch, temp_dir):
    import web.app as web_app

    upload_dir = temp_dir / "uploads"
    upload_dir.mkdir()
    outside = temp_dir / "outside.pdf"
    outside.write_bytes(b"secret")
    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", upload_dir)
    monkeypatch.setattr(web_app, "tasks", {
        "unsafe-source-task": {
            "status": "completed",
            "original_name": "outside.pdf",
            "file_path": str(outside),
        },
    })

    response = web_app.app.test_client().get(
        "/api/tasks/unsafe-source-task/source-file"
    )

    assert response.status_code == 404


def test_media_generation_uses_confirmed_scripts(monkeypatch, temp_dir):
    import moviepy
    import web.app as web_app
    from vidppt.course_pipeline import CoursePipeline
    from vidppt.pipeline import Pipeline
    import vidppt.utils.course_packaging as course_packaging
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
                "course_packaging": {
                    "enable_intro": True,
                    "enable_outro": True,
                    "template": "academic",
                    "duration_seconds": 4,
                    "organization": "测试大学",
                    "instructor": "",
                    "outro_text": "感谢观看",
                    "apply_to_segments": False,
                    "use_slide_background": True,
                    "enable_motion": True,
                    "enable_music": True,
                },
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

    packaged = []

    def fake_package(
        source_video, output_video, config, options, *,
        course_title, segment_title="", logo_path=None,
        intro_background_path=None, mid_background_path=None, outro_background_path=None,
        segment_durations=None,
        cancel_check=None,
    ):
        packaged.append({
            "source_video": source_video,
            "output_video": output_video,
            "options": options,
            "course_title": course_title,
            "segment_title": segment_title,
            "intro_background_path": intro_background_path,
            "mid_background_path": mid_background_path,
            "outro_background_path": outro_background_path,
            "segment_durations": segment_durations,
        })

    def fake_segmented_audio(content, config, *, cancel_check=None):
        fake_audio(None, content, None)
        for page in content.pages:
            page.metadata["focus_cues"] = [{
                "text": page.text, "start": 0.0, "end": 2.0,
                "subtitle_unit": True, "timing_source": "segment_audio",
            }]

    monkeypatch.setattr(web_app, "_generate_audio_with_focus_segments", fake_segmented_audio)
    monkeypatch.setattr(moviepy, "AudioFileClip", FakeAudioClip)
    monkeypatch.setattr(VideoComposer, "compose", fake_compose)
    monkeypatch.setattr(CoursePipeline, "_burn_subtitles", fake_burn)
    monkeypatch.setattr(course_packaging, "package_course_video", fake_package)

    web_app.run_media_generation(task_id)

    assert captured_scripts == ["用户确认后的讲稿"]
    assert len(packaged) == 1
    assert packaged[0]["course_title"] == "source"
    assert packaged[0]["options"]["template"] == "academic"
    assert packaged[0]["intro_background_path"] == slide
    assert packaged[0]["outro_background_path"] == slide
    assert web_app.tasks[task_id]["status"] == "completed"
    assert Path(web_app.tasks[task_id]["video_path"]).exists()
    saved_preview = json.loads((output_dir / "preview.json").read_text(encoding="utf-8"))
    assert saved_preview["pages"][0]["duration"] == 2.0
    assert saved_preview["duration_estimate"]["total_seconds"] == 2.0
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


def test_stop_queued_media_task_rolls_back_to_preview(monkeypatch, temp_dir):
    import threading
    import web.app as web_app

    task_id = "queued-media-task"
    preview_path = temp_dir / "preview.json"
    preview_path.write_text("{}", encoding="utf-8")
    queue = Queue()
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "queued",
            "stage": "queue",
            "percentage": 50,
            "preview_path": str(preview_path),
            "output_dir": str(temp_dir),
        }
    })
    monkeypatch.setattr(web_app, "progress_queues", {task_id: queue})
    monkeypatch.setattr(web_app, "cancellation_events", {
        task_id: threading.Event()
    })
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")

    response = web_app.app.test_client().post(f"/api/stop/{task_id}")

    assert response.status_code == 200
    assert web_app.cancellation_events[task_id].is_set()
    assert web_app.tasks[task_id]["status"] == "awaiting_confirmation"
    assert web_app.tasks[task_id]["stage"] == "preview"
    assert web_app.tasks[task_id]["stop_requested"] is False
    assert list(queue.queue)[0]["type"] == "rollback"


def test_queue_skips_stale_run_after_retry(monkeypatch):
    import web.app as web_app

    task_id = "queued-stale-run"
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "queued",
            "queue_run_id": "new-run",
        }
    })
    monkeypatch.setattr(web_app, "cancellation_events", {})

    assert web_app.conversion_queue._should_skip(task_id, "old-run") is True
    assert web_app.conversion_queue._should_skip(task_id, "new-run") is False


def test_queue_capacity_ready_returns_true(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "queue-ready"
    monkeypatch.setattr(web_app, "OUTPUT_FOLDER", temp_dir)
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "queued",
            "queue_run_id": "run",
        }
    })
    monkeypatch.setattr(web_app, "cancellation_events", {})
    monkeypatch.setitem(
        sys.modules,
        "psutil",
        SimpleNamespace(
            cpu_percent=lambda interval=0: 0,
            virtual_memory=lambda: SimpleNamespace(percent=0),
            disk_usage=lambda path: SimpleNamespace(free=1024 ** 4),
        ),
    )

    assert web_app.conversion_queue._wait_for_capacity(task_id, "run") is True


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
    assert event["stage_percentage"] == 0
    assert web_app.tasks[task_id]["percentage"] == 50

    tracker.update("video", 37, 100, "正在编码视频 37%")
    progress_event = list(queue.queue)[1]
    assert progress_event["stage_percentage"] == 37
    assert web_app.tasks[task_id]["stage_percentage"] == 37


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
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {"output_dir": str(output_dir)}
    })

    web_app._update_preview_scripts(task_id, [
        {"page_number": 1, "script": "新讲稿一"},
        {"page_number": 2, "script": "旧讲稿二"},
    ])

    assert not (output_dir / "1" / "audio.mp3").exists()
    assert (output_dir / "2" / "audio.mp3").exists()


def test_course_segment_recommendation_and_apply(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "segment-task"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    preview_path = output_dir / "preview.json"
    preview_path.write_text(json.dumps({
        "pages": [
            {"page_number": 1, "title": "绪论", "script": "一" * 260},
            {"page_number": 2, "title": "绪论", "script": "二" * 260},
            {"page_number": 3, "title": "实操", "script": "三" * 260},
        ]
    }), encoding="utf-8")
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "awaiting_confirmation",
            "output_dir": str(output_dir),
        }
    })
    client = web_app.app.test_client()

    recommendation = client.post(
        f"/api/course-segments/{task_id}/recommend",
        json={"target_minutes": 1, "priority": "duration"},
    )
    assert recommendation.status_code == 200
    assert recommendation.get_json()["segments"][0]["start_page"] == 1

    response = client.post(
        f"/api/course-segments/{task_id}",
        json={
            "segments": [
                {"title": "第一课", "start_page": 1, "end_page": 2},
                {"title": "第二课", "start_page": 3, "end_page": 3},
            ]
        },
    )
    payload = response.get_json()
    saved_preview = json.loads(preview_path.read_text(encoding="utf-8"))

    assert response.status_code == 200
    assert payload["segments"][0]["title"] == "第一课"
    assert payload["segments"][0]["estimated_seconds"] == 123.8
    assert saved_preview["lesson_segments"][1]["start_page"] == 3
    assert saved_preview["lesson_segments"][1]["estimated_minutes"] == 1.0
    assert saved_preview["pages"][0]["lesson_segment"]["end_page"] == 2
    assert web_app.tasks[task_id]["lesson_segments"][0]["title"] == "第一课"


def test_course_segment_apply_rejects_gaps(monkeypatch, temp_dir):
    import web.app as web_app

    task_id = "segment-gap-task"
    output_dir = temp_dir / task_id
    output_dir.mkdir()
    (output_dir / "preview.json").write_text(json.dumps({
        "pages": [
            {"page_number": 1, "script": "第一页"},
            {"page_number": 2, "script": "第二页"},
        ]
    }), encoding="utf-8")
    monkeypatch.setattr(web_app, "STATE_FILE", temp_dir / "state.json")
    monkeypatch.setattr(web_app, "tasks", {
        task_id: {
            "status": "awaiting_confirmation",
            "output_dir": str(output_dir),
        }
    })

    response = web_app.app.test_client().post(
        f"/api/course-segments/{task_id}",
        json={"segments": [{"title": "只覆盖第一页", "start_page": 1, "end_page": 1}]},
    )

    assert response.status_code == 400
    assert "覆盖全部页面" in response.get_json()["error"]


def test_index_contains_editable_course_preview():
    import web.app as web_app

    response = web_app.app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert 'id="course-preview-module"' in html
    assert 'id="cancel-course-btn"' in html
    assert 'id="save-scripts-btn"' in html
    assert 'id="continue-course-btn"' in html
    assert 'id="refinement-level"' in html
    assert 'id="quality-mode"' in html
    assert 'id="ai-review-panel"' in html
    assert 'id="ai-review-fix-all-btn"' in html
    assert 'AI 抽检' in html
    assert 'id="custom-voice"' in html
    assert 'id="ppt-footer-text"' in html
    assert 'id="visual-theme"' in html
    assert 'id="smart-cut-recommend-btn"' in html
    assert 'id="smart-cut-apply-btn"' in html
    assert 'id="packaging-template"' in html
    assert 'id="packaging-manage-btn"' in html
    assert 'href="/course-packaging"' in html
    assert 'id="packaging-manager-overlay"' not in html
    assert 'id="packaging-intro-preview"' not in html
    assert 'id="packaging-accent-color"' not in html
    assert 'id="packaging-use-slide-background"' in html
    assert 'id="packaging-enable-motion"' in html
    assert 'id="packaging-enable-music"' in html
    assert 'id="packaging-layout-reset"' not in html
    assert 'id="course-duration-estimate"' in html
    assert '预计完整视频总时长' in html
    assert '约 -- 分 -- 秒' in html
    assert '可跳过切课直接继续生成完整视频' in html
    assert 'id="subtitle-preset"' in html
    assert '标准底部单行' in html
    assert '顶部字幕' in html
    assert 'Noto Serif CJK SC' in html
    assert '文泉驿微米黑' in html
    assert '霞鹜文楷' in html
    assert '微软雅黑' not in html
    assert '苹方' not in html
    assert 'SimHei' not in html
    assert 'id="course-preview-play-btn"' not in html
    assert 'id="subtitle-position-preview"' not in html
    assert 'id="asset-management-module"' not in html
    assert 'id="operation-log-module"' not in html
    assert 'id="asset-table-body"' not in html
    assert 'id="operation-log-body"' not in html
    assert 'href="/data-management"' in html
    assert 'href="/operation-logs-page"' in html
    assert '这里是字幕位置' not in html
    assert '在每页 PPT 上检查字幕，并让声音讲到哪里、画面就提示到哪里' in html
    assert 'id="focus-highlight"' in html
    assert 'id="focus-highlight-style"' in html
    assert '聚光突出' in html
    assert '下划线提示' in html


def test_focus_highlight_style_validation():
    import web.app as web_app

    assert web_app._focus_highlight_style({}) == "outline"
    assert web_app._focus_highlight_style({"focus_highlight_style": "spotlight"}) == "spotlight"
    try:
        web_app._focus_highlight_style({"focus_highlight_style": "blink"})
    except ValueError as exc:
        assert "不支持的讲解焦点标注方式" in str(exc)
    else:
        raise AssertionError("invalid focus style should be rejected")


def test_segmented_focus_audio_persists_real_cue_timeline(monkeypatch, temp_dir):
    import moviepy
    import web.app as web_app
    from vidppt.core.models import DocumentContent, PageContent, ProcessConfig

    class FakePipeline:
        def __init__(self, config):
            self.config = config

        def _generate_audio(self, content, progress):
            for page in content.pages:
                path = self.config.output_dir / str(page.page_number) / "audio.mp3"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"segment")
                page.audio = path

    class FakeAudioClip:
        def __init__(self, path):
            self.duration = 1.25 if "/1/" in path else 2.5
            self.effects = []

        def with_effects(self, effects):
            self.effects = effects
            return self

        def close(self):
            pass

    class FakeCombined:
        write_kwargs = None

        def write_audiofile(self, path, **kwargs):
            self.write_kwargs = kwargs
            Path(path).write_bytes(b"combined")

        def close(self):
            pass

    monkeypatch.setattr(web_app, "Pipeline", FakePipeline)
    monkeypatch.setattr(moviepy, "AudioFileClip", FakeAudioClip)
    combined = FakeCombined()
    captured_clips = []

    def fake_concatenate(clips):
        captured_clips.extend(clips)
        return combined

    monkeypatch.setattr(moviepy, "concatenate_audioclips", fake_concatenate)

    cues = [
        {"text": "先介绍学习目标", "target_id": "p1-a2"},
        {"text": "再说明实践案例", "target_id": "p1-a3"},
    ]
    page = PageContent(
        page_number=1,
        text="先介绍学习目标。再说明实践案例。",
        metadata={"focus_cues": cues},
    )
    config = ProcessConfig(
        input_path=temp_dir / "lesson.pptx",
        output_dir=temp_dir,
        save_intermediate=True,
    )

    web_app._generate_audio_with_focus_segments(
        DocumentContent(pages=[page]), config
    )

    assert page.audio == temp_dir / "1" / "audio.mp3"
    assert page.audio.read_bytes() == b"combined"
    assert [(cue["start"], cue["end"]) for cue in cues] == [
        (0.0, 1.25), (1.25, 3.75),
    ]
    assert all(cue["timing_source"] == "segment_audio" for cue in cues)
    assert all(len(clip.effects) == 2 for clip in captured_clips)
    assert combined.write_kwargs["fps"] == config.audio_sample_rate
    assert combined.write_kwargs["bitrate"] == config.audio_bitrate


def test_course_packaging_preview_image_endpoint():
    import web.app as web_app

    response = web_app.app.test_client().get(
        "/api/course-packaging-preview-image",
        query_string={
            "kind": "outro",
            "packaging_template": "credits",
            "packaging_organization": "测试大学",
            "packaging_outro_text": "感谢观看",
            "packaging_intro_label": "在线精品课",
            "packaging_intro_title": "课程导入",
            "packaging_intro_subtitle": "从问题到方法",
            "packaging_outro_title": "课程总结",
            "packaging_outro_subtitle": "请完成课后练习",
            "packaging_accent_color": "#1D4ED8",
            "packaging_background_style": "gradient",
            "packaging_logo_position": "none",
        },
    )

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data.startswith(b"\x89PNG")


def test_course_packaging_preview_image_uses_uploaded_school_logo(monkeypatch, temp_dir):
    import web.app as web_app
    import vidppt.utils.course_packaging as course_packaging
    from PIL import Image

    logo = temp_dir / "logo_preview.png"
    Image.new("RGBA", (120, 40), "#1D4ED8").save(logo)
    render_kwargs = {}

    def fake_render(output, *_args, **kwargs):
        render_kwargs.update(kwargs)
        Image.new("RGB", (960, 540), "#FFFFFF").save(output)

    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    monkeypatch.setattr(course_packaging, "_render_packaging_image", fake_render)
    response = web_app.app.test_client().get(
        "/api/course-packaging-preview-image",
        query_string={"kind": "intro", "school_logo_path": str(logo)},
    )

    assert response.status_code == 200
    assert render_kwargs["logo_path"] == logo


def test_course_packaging_preview_video_endpoint(monkeypatch, temp_dir):
    import web.app as web_app
    import vidppt.utils.course_packaging as course_packaging

    render_calls = []

    def fake_render(output, *_args, **kwargs):
        render_calls.append((output, kwargs))
        output.write_bytes(b"fake mp4")

    monkeypatch.setattr(course_packaging, "_render_packaging_clip", fake_render)
    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    logo = temp_dir / "logo_preview.png"
    logo.write_bytes(b"fake png")
    query = {
        "kind": "intro",
        "packaging_enable_motion": "true",
        "school_logo_path": str(logo),
    }
    response = web_app.app.test_client().get(
        "/api/course-packaging-preview-video",
        query_string=query,
    )

    assert response.status_code == 200
    assert response.mimetype == "video/mp4"
    assert response.data == b"fake mp4"

    range_response = web_app.app.test_client().get(
        "/api/course-packaging-preview-video",
        query_string=query,
        headers={"Range": "bytes=0-3"},
    )
    assert range_response.status_code == 206
    assert range_response.data == b"fake"
    assert range_response.headers["Content-Range"] == "bytes 0-3/8"
    assert len(render_calls) == 1
    assert render_calls[0][1]["logo_path"] == logo


def test_course_packaging_background_asset_can_be_uploaded(monkeypatch, temp_dir):
    import web.app as web_app
    from PIL import Image

    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    payload = io.BytesIO()
    Image.new("RGB", (320, 180), "#123456").save(payload, format="PNG")
    payload.seek(0)

    response = web_app.app.test_client().post(
        "/api/course-packaging-asset-upload",
        data={"kind": "background", "asset": (payload, "background.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    asset_path = Path(response.get_json()["asset_path"])
    assert asset_path.is_file()
    options = web_app._course_packaging_options({
        "packaging_background_path": str(asset_path),
    })["course_packaging"]
    assert options["background_path"] == str(asset_path)


def test_course_packaging_music_library_lists_uploaded_assets(monkeypatch, temp_dir):
    import web.app as web_app

    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    music = temp_dir / "packaging_music_abc__opening-theme.mp3"
    music.write_bytes(b"fake mp3")

    response = web_app.app.test_client().get(
        "/api/course-packaging-assets", query_string={"kind": "music"}
    )

    assert response.status_code == 200
    assets = response.get_json()["assets"]
    assert assets == [{
        "name": "opening-theme",
        "path": str(music),
        "url": f"/api/course-packaging-asset/{music.name}",
    }]


def test_course_packaging_intro_video_can_be_uploaded_and_selected(monkeypatch, temp_dir):
    import web.app as web_app

    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    response = web_app.app.test_client().post(
        "/api/course-packaging-asset-upload",
        data={"kind": "intro_video", "asset": (io.BytesIO(b"video"), "campus.mp4")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    asset_path = Path(response.get_json()["asset_path"])
    options = web_app._course_packaging_options({
        "packaging_intro_video_path": str(asset_path),
    })["course_packaging"]
    assert options["intro_video_path"] == str(asset_path)


def test_course_workspace_exposes_packaging_media_library_controls():
    import web.app as web_app

    html = web_app.app.test_client().get("/").get_data(as_text=True)
    assert '进入包装设计' in html
    assert 'id="packaging-music-library"' not in html
    assert 'id="packaging-intro-video-input"' not in html
    assert '/static/js/main.js?v=52' in html


def test_course_packaging_has_a_separate_design_page():
    import web.app as web_app

    client = web_app.app.test_client()
    html = client.get('/course-packaging').get_data(as_text=True)

    assert '片头片尾设计' in html
    assert 'class="nav-item active" href="/course-packaging"' in html
    assert 'id="packaging-save-btn"' in html
    assert '<video id="packaging-intro-preview" controls' in html
    assert '<video id="packaging-outro-preview" controls' in html
    assert 'id="packaging-intro-tab"' in html
    assert 'id="packaging-mid-tab"' in html
    assert 'id="packaging-outro-tab"' in html
    assert 'id="packaging-intro-panel"' in html
    assert 'data-packaging-presets="intro"' in html
    assert 'data-packaging-preset-status="intro"' in html
    assert 'data-packaging-source="intro"' in html
    assert 'id="packaging-intro-primary-color"' in html
    assert 'id="packaging-intro-text-color"' in html
    assert 'data-packaging-logo="intro"' in html
    assert 'id="packaging-intro-logo-x"' in html
    assert 'id="packaging-save-scope"' in html
    assert 'data-packaging-select="packaging-outro-motion-style"' in html
    assert 'id="packaging-copy-intro-style"' in html
    assert 'id="packaging-show-safe-area"' in html
    assert 'id="enable-mid"' in html
    assert 'id="packaging-mid-preview"' in html
    assert 'id="packaging-mid-video-library"' in html
    assert 'id="packaging-intro-music-library"' in html
    assert 'id="packaging-outro-music-library"' in html
    assert 'packaging-intro-music-style' not in html
    assert '音乐风格' not in html
    assert 'id="packaging-intro-background-input"' in html
    assert 'id="packaging-outro-background-input"' in html
    assert 'id="packaging-intro-video-input"' in html
    assert 'id="packaging-intro-video-library"' in html
    assert 'id="packaging-outro-video-library"' in html
    assert 'id="packaging-department"' in html
    assert 'id="packaging-instructor-title"' in html
    assert 'id="packaging-copyright"' in html
    assert 'id="packaging-transition-seconds"' in html
    assert 'id="upload-area"' not in html
    assert '/static/js/course_packaging.js?v=16' in html


def test_packaging_template_management_crud_and_render_resolution():
    import web.app as web_app

    client = web_app.app.test_client()
    page = client.get('/packaging-templates')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert '包装模板管理' in html
    assert 'id="packaging-templates-grid"' in html
    assert '/static/js/packaging_templates.js?v=2' in html

    builtins = client.get('/api/course-packaging-templates?include_disabled=1')
    assert builtins.status_code == 200
    assert len(builtins.get_json()['templates']) == 5
    assert builtins.get_json()['default_template_id'] == 'academic'

    created = client.post('/api/course-packaging-templates', json={
        'name': '学院蓝金模板',
        'description': '用于人工智能学院课程',
        'base_template': 'university',
        'config': {
            'packaging_intro_accent_color': '#1C64F2',
            'packaging_intro_title': '学院精品课程',
            'unrelated_option': 'ignored',
        },
    })
    assert created.status_code == 201
    template = created.get_json()['template']
    assert template['builtin'] is False
    assert template['config']['packaging_intro_accent_color'] == '#1C64F2'
    assert 'unrelated_option' not in template['config']

    resolved = web_app._course_packaging_options({
        'packaging_template': template['id'],
    })['course_packaging']
    assert resolved['template'] == 'university'
    assert resolved['template_id'] == template['id']
    assert resolved['intro_accent_color'] == '#1C64F2'
    assert resolved['intro_title'] == '学院精品课程'

    made_default = client.patch(
        f"/api/course-packaging-templates/{template['id']}",
        json={'is_default': True},
    )
    assert made_default.status_code == 200
    assert made_default.get_json()['template']['is_default'] is True

    updated_details = client.patch(
        f"/api/course-packaging-templates/{template['id']}",
        json={
            'base_template': 'modern',
            'config': {
                'packaging_intro_title': '更新后的课程片头',
                'packaging_outro_text': '学习完成',
                'packaging_intro_content_x': 14.5,
            },
        },
    )
    assert updated_details.status_code == 200
    updated_template = updated_details.get_json()['template']
    assert updated_template['base_template'] == 'modern'
    assert updated_template['config']['packaging_template'] == 'modern'
    assert updated_template['config']['packaging_intro_title'] == '更新后的课程片头'
    assert updated_template['config']['packaging_outro_text'] == '学习完成'
    assert updated_template['config']['packaging_intro_content_x'] == 14.5

    cannot_delete_builtin = client.delete('/api/course-packaging-templates/academic')
    assert cannot_delete_builtin.status_code == 400
    deleted = client.delete(f"/api/course-packaging-templates/{template['id']}")
    assert deleted.status_code == 200


def test_course_packaging_keeps_intro_and_outro_media_settings_separate(monkeypatch, temp_dir):
    import web.app as web_app

    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    intro_music = temp_dir / "packaging_intro_music_a__intro.mp3"
    outro_music = temp_dir / "packaging_outro_music_b__outro.mp3"
    intro_music.write_bytes(b"intro")
    outro_music.write_bytes(b"outro")

    options = web_app._course_packaging_options({
        "enable_mid": True,
        "packaging_mid_title": "下一章节",
        "packaging_mid_duration_seconds": 2.5,
        "packaging_intro_music_path": str(intro_music),
        "packaging_outro_music_path": str(outro_music),
        "packaging_intro_motion_style": "zoom",
        "packaging_outro_motion_style": "pan",
        "packaging_intro_enable_music": False,
        "packaging_outro_enable_music": True,
    })["course_packaging"]

    assert options["intro_music_path"] == str(intro_music)
    assert options["outro_music_path"] == str(outro_music)
    assert options["intro_motion_style"] == "zoom"
    assert options["outro_motion_style"] == "pan"
    assert options["intro_enable_music"] is False
    assert options["outro_enable_music"] is True
    assert options["enable_mid"] is True
    assert options["mid_title"] == "下一章节"
    assert options["mid_duration_seconds"] == 2.5


def test_packaging_assets_management_page_and_api(monkeypatch, temp_dir):
    import web.app as web_app

    monkeypatch.setattr(web_app, "UPLOAD_FOLDER", temp_dir)
    asset = temp_dir / "packaging_intro_video_abc__campus.mp4"
    asset.write_bytes(b"video data")
    client = web_app.app.test_client()

    html = client.get('/packaging-assets').get_data(as_text=True)
    assert '包装素材管理' in html
    assert 'id="packaging-assets-grid"' in html
    assert 'id="packaging-asset-add-form"' in html
    assert 'id="packaging-asset-add-kind"' in html
    assert 'id="packaging-asset-add-file"' in html
    assert 'id="packaging-asset-add-file" type="file" accept=".mp4,.mov,.m4v,.webm" multiple' in html
    assert '选择多个文件' in html
    assert 'id="packaging-asset-add-submit"' in html
    assert 'value="mid_video">片中视频' in html
    assert 'value="mid_background">片中背景图' in html
    assert 'value="mid_music">片中音乐' in html
    assert '/static/js/packaging_assets.js?v=4' in html
    assert 'href="/course-packaging"' in html

    listed = client.get('/api/course-packaging-assets', query_string={'kind': 'all'})
    assert listed.status_code == 200
    item = listed.get_json()['assets'][0]
    assert item['kind'] == 'intro_video'
    assert item['media_type'] == 'video'
    assert item['filename'] == asset.name

    renamed = client.patch(
        f'/api/course-packaging-asset/{asset.name}', json={'name': '校园片头'}
    )
    assert renamed.status_code == 200
    renamed_name = renamed.get_json()['filename']
    assert '校园片头' in renamed_name
    assert (temp_dir / renamed_name).is_file()

    deleted = client.delete(f'/api/course-packaging-asset/{renamed_name}')
    assert deleted.status_code == 200
    assert not (temp_dir / renamed_name).exists()


def test_management_pages_are_separate_from_course_workspace():
    import web.app as web_app

    client = web_app.app.test_client()
    data_page = client.get("/data-management").get_data(as_text=True)
    logs_page = client.get("/operation-logs-page").get_data(as_text=True)
    debug_page = client.get("/debug").get_data(as_text=True)

    assert 'id="asset-table-body"' in data_page
    assert 'id="operation-log-body"' not in data_page
    assert 'id="upload-area"' not in data_page
    assert 'js/admin_pages.js' in data_page
    assert '/static/css/main.css?v=21' in data_page
    assert '/static/js/admin_pages.js?v=8' in data_page
    assert 'id="operation-log-body"' in logs_page
    assert 'id="operation-log-pagination"' in logs_page
    assert '/static/css/main.css?v=22' in logs_page
    assert '/static/js/admin_pages.js?v=9' in logs_page
    assert 'id="asset-table-body"' not in logs_page
    assert 'id="upload-area"' not in logs_page
    assert 'js/admin_pages.js' in logs_page
    assert 'id="debug-task-body"' in debug_page
    assert 'id="debug-task-detail"' in debug_page
    assert 'id="debug-diagnostics"' in debug_page
    assert 'id="debug-runtime-output"' in debug_page
    assert 'id="debug-server-output"' in debug_page
    assert '下载完整服务器日志' in debug_page
    assert '下载完整日志' in debug_page
    assert 'IP 地址' in debug_page
    assert 'id="upload-area"' not in debug_page
    assert 'js/debug.js' in debug_page
    assert '/static/js/debug.js?v=5' in debug_page
    assert 'id="debug-log-pagination"' in debug_page


def test_accounts_page_is_separate_admin_page():
    import web.app as web_app

    html = web_app.app.test_client().get("/accounts").get_data(as_text=True)

    assert 'id="account-form"' in html
    assert 'id="account-table-body"' in html
    assert 'value="view_all_tasks"' in html
    assert 'value="manage_all_tasks"' in html
    assert 'value="manage_accounts"' in html
    assert 'id="upload-area"' not in html
    assert 'js/admin_pages.js' in html


def test_debug_api_overview_redacts_sensitive_values(monkeypatch):
    import web.app as web_app

    monkeypatch.setattr(web_app, 'tasks', {
        'debug-task': {
            'status': 'completed',
            'original_name': 'course.pptx',
            'owner_username': 'admin',
            'created_at': 1000,
            'strategy': {
                'llm_engine': 'qwen',
                'api_key': 'secret-value',
                'nested': {'access_token': 'token-value'},
            },
        },
    })

    response = web_app.app.test_client().get('/api/debug/overview')
    payload = response.get_json()

    assert response.status_code == 200
    strategy = payload['tasks'][0]['strategy']
    assert strategy['api_key'] == '已隐藏'
    assert strategy['nested']['access_token'] == '已隐藏'
    assert payload['environment']['env_status']


def test_debug_logs_can_filter_by_ip_address():
    import web.app as web_app

    web_app.task_store.add_operation_log({
        "actor": "teacher",
        "role": "user",
        "action": "upload",
        "ip_address": "203.0.113.21",
    })
    web_app.task_store.add_operation_log({
        "actor": "teacher",
        "role": "user",
        "action": "upload",
        "ip_address": "198.51.100.9",
    })

    response = web_app.app.test_client().get("/api/debug/logs?q=203.0.113.21")
    logs = response.get_json()["logs"]

    assert response.status_code == 200
    assert len(logs) == 1
    assert logs[0]["ip_address"] == "203.0.113.21"


def test_debug_logs_support_filtered_pagination(monkeypatch, temp_dir):
    import web.app as web_app
    from web.task_store import TaskStore

    store = TaskStore(temp_dir / "tasks.db")
    for index in range(5):
        store.add_operation_log({
            "actor": "teacher",
            "action": "preview_task" if index < 4 else "login",
            "created_at": 1000 + index,
        })
    monkeypatch.setattr(web_app, "task_store", store)

    response = web_app.app.test_client().get(
        "/api/debug/logs?q=preview&page=2&page_size=2"
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["pagination"] == {
        "page": 2,
        "page_size": 2,
        "total": 4,
        "total_pages": 2,
    }
    assert [log["action"] for log in payload["logs"]] == [
        "preview_task",
        "preview_task",
    ]


def test_debug_runtime_logs_are_filterable_and_redacted(monkeypatch, temp_dir):
    import web.app as web_app

    log_file = temp_dir / 'vidppt-runtime.log'
    log_file.write_text(
        '2026-07-13 10:00:00.000 | INFO     | web.app - task=task-a started\n'
        '2026-07-13 10:00:01.000 | ERROR    | web.app - task=task-b api_key=secret-value failed\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(web_app, '_runtime_log_files', lambda: [log_file])

    response = web_app.app.test_client().get(
        '/api/debug/runtime-logs?task_id=task-b&level=ERROR'
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['matched_count'] == 1
    assert 'task-b' in payload['lines'][0]
    assert 'secret-value' not in payload['lines'][0]
    assert 'api_key=[已隐藏]' in payload['lines'][0]

    downloaded = web_app.app.test_client().get(
        '/api/debug/runtime-logs?task_id=task-b&download=1'
    )
    downloaded_text = downloaded.get_data(as_text=True)
    assert downloaded.status_code == 200
    assert 'attachment; filename="vidppt-runtime-full.log"' in downloaded.headers['Content-Disposition']
    assert 'task-b' in downloaded_text
    assert 'secret-value' not in downloaded_text


def test_debug_server_logs_are_read_only_filterable_and_redacted(monkeypatch, temp_dir):
    import web.app as web_app

    log_file = temp_dir / 'server.log'
    log_file.write_text(
        '===== VidPPT server started =====\n'
        '127.0.0.1 GET /api/tasks 200\n'
        'task=server-task password=unsafe-value\n'
        'Traceback: example failure\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(web_app, '_server_log_files', lambda: [log_file])

    response = web_app.app.test_client().get(
        '/api/debug/server-logs?task_id=server-task'
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['available'] is True
    assert payload['source'] == 'container_stdout_stderr'
    assert payload['matched_count'] == 1
    assert 'unsafe-value' not in payload['lines'][0]
    assert 'password=[已隐藏]' in payload['lines'][0]
    assert response.headers['Cache-Control'] == 'no-store'

    downloaded = web_app.app.test_client().get(
        '/api/debug/server-logs?download=1'
    )
    downloaded_text = downloaded.get_data(as_text=True)
    assert downloaded.status_code == 200
    assert 'filename="vidppt-server-full.log"' in downloaded.headers['Content-Disposition']
    assert 'Traceback: example failure' in downloaded_text
    assert 'unsafe-value' not in downloaded_text


def test_debug_overview_includes_admin_diagnostics(monkeypatch):
    import web.app as web_app

    monkeypatch.setattr(web_app, '_debug_tool_status', lambda: [
        {'name': 'ffmpeg', 'path': '/usr/bin/ffmpeg', 'available': True},
        {'name': 'ffprobe', 'path': '/usr/bin/ffprobe', 'available': True},
        {'name': 'soffice', 'path': '/usr/bin/soffice', 'available': True},
        {'name': 'libreoffice', 'path': None, 'available': False},
    ])
    response = web_app.app.test_client().get('/api/debug/overview')
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['diagnostics']['status'] in {'success', 'info', 'warning', 'error'}
    assert payload['diagnostics']['items'][0]['action']


def test_debug_task_detail_reads_artifacts(monkeypatch, temp_dir):
    import json
    import web.app as web_app

    output_dir = temp_dir / 'debug-task'
    output_dir.mkdir()
    preview = output_dir / 'preview.json'
    course = output_dir / 'course.json'
    video = output_dir / 'video.mp4'
    preview.write_text(json.dumps({'task_id': 'debug-task', 'pages': []}), encoding='utf-8')
    course.write_text(json.dumps({'title': '测试课程'}), encoding='utf-8')
    video.write_bytes(b'video')
    monkeypatch.setattr(web_app, 'tasks', {
        'debug-task': {
            'status': 'completed',
            'original_name': 'course.pptx',
            'owner_username': 'admin',
            'output_dir': str(output_dir),
            'preview_path': str(preview),
            'course_json_path': str(course),
            'video_path': str(video),
        },
    })

    response = web_app.app.test_client().get('/api/debug/tasks/debug-task')
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['paths']['preview_json']['exists'] is True
    assert payload['json_artifacts']['preview_json']['data']['task_id'] == 'debug-task'
    assert payload['json_artifacts']['course_json']['data']['title'] == '测试课程'
    assert [item['name'] for item in payload['output_files']]


def test_subtitle_font_catalog_endpoint(monkeypatch):
    import web.app as web_app

    monkeypatch.setattr(
        web_app,
        "_subtitle_font_catalog",
        lambda: ["Noto Sans CJK SC", "WenQuanYi Micro Hei", "LXGW WenKai"],
    )

    response = web_app.app.test_client().get("/api/subtitle-fonts")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["default"] == "Noto Sans CJK SC"
    assert payload["count"] == 3
    assert "WenQuanYi Micro Hei" in payload["fonts"]
    assert "LXGW WenKai" in payload["fonts"]


def test_subtitle_font_catalog_filters_proprietary_fonts(monkeypatch):
    import web.app as web_app

    monkeypatch.setattr(web_app.shutil, "which", lambda _: "/usr/bin/fc-list")

    class Result:
        stdout = "Noto Sans CJK SC,Microsoft YaHei\nPingFang SC,LXGW WenKai\n"

    monkeypatch.setattr(web_app.subprocess, "run", lambda *args, **kwargs: Result())

    fonts = web_app._subtitle_font_catalog()

    assert "Noto Sans CJK SC" in fonts
    assert "LXGW WenKai" in fonts
    assert "Microsoft YaHei" not in fonts
    assert "PingFang SC" not in fonts


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


def test_script_preview_uses_real_text_and_cache(monkeypatch, temp_dir):
    import web.app as web_app

    preview_folder = temp_dir / "script-previews"
    preview_folder.mkdir()
    generated = []

    def fake_synthesize(engine, voice, text, output_path):
        generated.append((engine, voice, text))
        output_path.write_bytes(b"script-audio")

    monkeypatch.setattr(web_app, "VOICE_PREVIEW_FOLDER", preview_folder)
    monkeypatch.setattr(web_app, "_synthesize_script_preview", fake_synthesize)
    client = web_app.app.test_client()
    payload = {
        "engine": "edge-tts",
        "voice": "zh-CN-XiaoxiaoNeural",
        "text": "这是当前页面的真实讲稿。" * 40,
    }

    first = client.post("/api/script-preview", json=payload)
    second = client.post("/api/script-preview", json=payload)

    assert first.status_code == 200
    assert first.data == b"script-audio"
    assert second.status_code == 200
    assert len(generated) == 1
    assert len(generated[0][2]) == 300


def test_focus_cue_coverage_rejects_stale_english_word_splits():
    from web.app import _focus_cues_cover_script

    script = "英文名称为Programmable Logic Controller，简称PLC。"

    assert _focus_cues_cover_script([
        {"text": "英文名称为Programmable Logic"},
        {"text": "Controller，简称PLC。"},
    ], script)
    assert not _focus_cues_cover_script([
        {"text": "英文名称为Programmable Logic Control"},
        {"text": "ler，简称PLC。"},
    ], script)
    assert not _focus_cues_cover_script([
        {"text": "英文名称为ProgrammableLogicController，简称PLC。"},
    ], script)


def test_segmented_audio_restores_decimal_from_script(monkeypatch, temp_dir):
    import pytest
    import web.app as web_app
    from vidppt.core.models import DocumentContent, PageContent, ProcessConfig

    script = "本节将聚焦3.2位逻辑指令——包括触点、线圈。"
    page = PageContent(page_number=1, text=script, metadata={
        "focus_cues": [{"text": "本节将聚焦3 2位逻辑指令 包括触点 线圈",
                        "target_id": "p1-a5", "subtitle_unit": True}],
        "audio_signature": "old-signature",
    })
    (temp_dir / "1").mkdir()
    (temp_dir / "1" / "audio.mp3").write_bytes(b"old wrong audio")

    def capture_audio(self, content, progress):
        assert ''.join(segment.text for segment in content.pages) == script
        assert content.pages[0].text.startswith("本节将聚焦3.2位")
        assert page.metadata['focus_cues'][0]['target_id'] == 'p1-a5'
        raise RuntimeError("captured corrected TTS input")

    monkeypatch.setattr(web_app.Pipeline, '_generate_audio', capture_audio)
    config = ProcessConfig(input_path=temp_dir / 'lesson.pptx', output_dir=temp_dir,
                           skip_existing=True)
    with pytest.raises(RuntimeError, match="captured corrected TTS input"):
        web_app._generate_audio_with_focus_segments(DocumentContent(pages=[page]), config)


def test_focus_edit_keeps_audio_and_reuses_it_for_export(monkeypatch, temp_dir):
    import web.app as web_app
    from vidppt.core.models import DocumentContent, PageContent, ProcessConfig
    from vidppt.pipeline import Pipeline

    output = temp_dir / "reuse"
    (output / "1").mkdir(parents=True)
    audio = output / "1" / "audio.mp3"
    audio.write_bytes(b"existing audio")
    config = ProcessConfig(input_path=temp_dir / "input.pptx", output_dir=output)
    script = "讲解内容"
    cue = {"text": script, "start": 0.0, "end": 2.0,
           "timing_source": "segment_audio", "subtitle_unit": True}
    signature = web_app._focus_audio_signature(script, config)
    preview = {"pages": [{
        "page_number": 1, "script": script, "focus_cues": [cue],
        "focus_targets": [{"id": "box"}], "audio_signature": signature,
    }]}
    (output / "preview.json").write_text(json.dumps(preview), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {"task": {"output_dir": str(output)}})
    event = {"start": 0.25, "end": 1.75, "target_ids": ["box"],
             "manual": True, "reviewed": True, "mapping_source": "manual"}
    result = web_app._update_preview_scripts("task", [{
        "page_number": 1, "script": script, "focus_events": [event],
    }])
    assert result["pages"][0]["focus_events"] == [event]
    assert audio.read_bytes() == b"existing audio"

    def unexpected_tts(*args, **kwargs):
        raise AssertionError("re-export must reuse the existing audio")

    monkeypatch.setattr(Pipeline, "_generate_audio", unexpected_tts)
    page = PageContent(page_number=1, text=script, metadata=result["pages"][0])
    web_app._generate_audio_with_focus_segments(DocumentContent(pages=[page]), config)
    assert page.audio == audio
    assert page.metadata["focus_events"] == [event]


def test_focus_edit_rejects_out_of_bounds_without_persisting(monkeypatch, temp_dir):
    import pytest
    import web.app as web_app

    preview = {"pages": [{
        "page_number": 1, "script": "讲稿",
        "focus_cues": [{"text": "讲稿", "start": 0, "end": 2,
                        "subtitle_unit": True}],
        "focus_targets": [{"id": "box"}],
    }]}
    preview_path = temp_dir / "preview.json"
    preview_path.write_text(json.dumps(preview), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {"task": {"output_dir": str(temp_dir)}})
    with pytest.raises(ValueError, match="焦点时间或目标无效"):
        web_app._update_preview_scripts("task", [{
            "page_number": 1, "script": "讲稿",
            "focus_events": [{"start": 1, "end": 3, "target_ids": ["box"]}],
        }])
    assert json.loads(preview_path.read_text(encoding="utf-8")) == preview


def test_provider_timing_rejects_stale_or_incomplete_metadata(temp_dir):
    import hashlib
    import web.app as web_app

    audio = temp_dir / "segment.mp3"
    audio.write_bytes(b"audio")
    sidecar = audio.with_suffix(".timing.json")
    payload = {
        "audio_sha256": hashlib.sha256(b"audio").hexdigest(),
        "boundaries": [
            {"text": "你好", "start": 0.12, "end": 0.5},
            {"text": "世界", "start": 0.6, "end": 1.1},
        ],
    }
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    assert web_app._segment_speech_timing(audio, "你好，世界", 1.5) == (0.12, 1.1)
    assert web_app._segment_speech_timing(audio, "你好，世界呀", 1.5) is None
    audio.write_bytes(b"different")
    assert web_app._segment_speech_timing(audio, "你好，世界", 1.5) is None


def test_script_change_preserves_manual_focus_for_review(monkeypatch, temp_dir):
    import web.app as web_app

    event = {"start": 0, "end": 2, "target_ids": ["box"],
             "reviewed": True, "manual": True}
    preview = {"pages": [{"page_number": 1, "script": "原讲稿",
                          "focus_targets": [{"id": "box", "text": "内容"}],
                          "focus_events": [event]}]}
    (temp_dir / "preview.json").write_text(json.dumps(preview), encoding="utf-8")
    monkeypatch.setattr(web_app, "tasks", {"task": {"output_dir": str(temp_dir)}})
    result = web_app._update_preview_scripts("task", [{"page_number": 1, "script": "新讲稿"}])
    saved = result["pages"][0]["focus_events"]
    assert saved == [{**event, "needs_review": True}]
