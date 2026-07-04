"""Web 教案上传与课程路线调度测试。"""

import io


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
