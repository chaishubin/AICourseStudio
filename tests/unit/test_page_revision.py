import json
from types import SimpleNamespace

import pytest

from vidppt.generation.page_revision import PageRevisionError, PageScriptReviser


def test_revision_uses_source_feedback_and_neighbours():
    calls = []

    def summarize(prompt, **kwargs):
        calls.append((json.loads(prompt), kwargs))
        return '```json\n{"script":"正确的新讲稿"}\n```'

    reviser = PageScriptReviser(engine=SimpleNamespace(summarize=summarize))
    result = reviser.revise(
        {"page_number": 2, "title": "PLC", "script": "误解的讲稿"},
        "PLC 是可编程逻辑控制器", "PLC 原文",
        {"title": "前页", "script": "前页讲解"},
        {"title": "后页", "script": "后页讲解"},
    )
    assert result == "正确的新讲稿"
    payload, options = calls[0]
    assert payload["source_text"] == "PLC 原文"
    assert payload["teacher_feedback"] == "PLC 是可编程逻辑控制器"
    assert payload["current_script"] == "误解的讲稿"
    assert payload["previous_page"]["script"] == "前页讲解"
    assert payload["next_page"]["script"] == "后页讲解"
    assert options["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("raw", ["无效响应", "[]", "null", '{}',
                                   '{"script":" "}', '{"script":123}'])
def test_revision_rejects_unusable_model_output(raw):
    reviser = PageScriptReviser(engine=SimpleNamespace(summarize=lambda *a, **k: raw))
    with pytest.raises(PageRevisionError, match="当前讲稿已保留"):
        reviser.revise({"page_number": 1}, "纠正", "原文")


@pytest.fixture
def draft(monkeypatch, tmp_path):
    import web.app as web_app

    preview = {"source_type": "presentation", "pages": [
        {"page_number": 1, "title": "前页", "script": "前页讲稿"},
        {"page_number": 2, "title": "PLC", "script": "原讲稿", "reviewed": True,
         "source_text": "PLC 原始内容", "focus_cues": [{"text": "原讲稿"}]},
        {"page_number": 3, "title": "后页", "script": "后页讲稿"},
    ]}
    path = tmp_path / "preview.json"
    path.write_text(json.dumps(preview, ensure_ascii=False), encoding="utf-8")
    task = {"status": "awaiting_confirmation", "output_dir": str(tmp_path),
            "strategy": {"llm_engine": "qwen"}}
    monkeypatch.setattr(web_app, "tasks", {"revision-task": task})
    monkeypatch.setattr(web_app.PageScriptReviser, "revise", lambda *a, **k: "新讲稿")
    return web_app, path, task


def request_revision(web_app, **overrides):
    return web_app.app.test_client().post(
        "/api/course-preview/revision-task/revise-page",
        json={"page_number": 2, "feedback": "纠正概念", "script": "原讲稿", **overrides},
    )


def test_generate_preserves_saved_draft_until_applied(draft, monkeypatch):
    web_app, path, task = draft
    before = path.read_bytes()
    seen = []

    def revise(self, page, feedback, source, previous, following):
        seen.append((page, feedback, source, previous, following))
        return "新讲稿"

    monkeypatch.setattr(web_app.PageScriptReviser, "revise", revise)
    result = request_revision(web_app)
    assert result.status_code == 200
    assert result.json["script"] == "新讲稿"
    assert result.json["base_script"] == "原讲稿"
    assert path.read_bytes() == before
    assert seen[0][2] == "PLC 原始内容"
    assert seen[0][3]["page_number"] == 1
    assert seen[0][4]["page_number"] == 3


@pytest.mark.parametrize("override", [
    {"feedback": " "}, {"feedback": "字" * 2001}, {"feedback": []},
    {"page_number": True}, {"page_number": "2"}, {"page_number": 0}, {"script": None},
])
def test_invalid_revision_input_does_not_change_draft(draft, override):
    web_app, path, _ = draft
    before = path.read_bytes()
    assert request_revision(web_app, **override).status_code == 400
    assert path.read_bytes() == before


def test_revision_requires_editable_existing_page(draft):
    web_app, _, task = draft
    assert request_revision(web_app, page_number=99).status_code == 404
    assert request_revision(web_app, script="未保存的讲稿").status_code == 409
    task["status"] = "processing"
    assert request_revision(web_app).status_code == 409


def test_revision_rejects_concurrent_changes(draft, monkeypatch):
    web_app, path, _ = draft

    def revise(*args, **kwargs):
        preview = json.loads(path.read_text())
        preview["pages"][1]["script"] = "另一个窗口的编辑"
        path.write_text(json.dumps(preview), encoding="utf-8")
        return "新讲稿"

    monkeypatch.setattr(web_app.PageScriptReviser, "revise", revise)
    assert request_revision(web_app).status_code == 409
    assert json.loads(path.read_text())["pages"][1]["script"] == "另一个窗口的编辑"


def test_revision_failure_keeps_draft(draft, monkeypatch):
    web_app, path, _ = draft
    before = path.read_bytes()

    def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(web_app.PageScriptReviser, "revise", fail)
    result = request_revision(web_app)
    assert result.status_code == 502
    assert "当前讲稿已保留" in result.json["error"]
    assert path.read_bytes() == before


def test_apply_revision_updates_only_selected_page_and_invalidates_its_audio(draft):
    web_app, path, _ = draft
    preview = json.loads(path.read_text())
    preview['ai_review'] = {'status': 'passed', 'findings': []}
    path.write_text(json.dumps(preview), encoding='utf-8')
    for number in (1, 2, 3):
        folder = path.parent / str(number)
        folder.mkdir()
        (folder / 'audio.mp3').write_bytes(b'cached audio')
    result = request_revision(web_app)
    response = web_app.app.test_client().patch(
        '/api/course-preview/revision-task', json={'pages': [{
            'page_number': 2, 'script': result.json['script'], 'reviewed': False,
        }]},
    )
    assert response.status_code == 200
    assert response.json['changed_pages'] == [2]
    saved = json.loads(path.read_text())
    assert saved['pages'][1]['script'] == '新讲稿'
    assert saved['pages'][1]['source_text'] == 'PLC 原始内容'
    assert saved['pages'][1]['reviewed'] is False
    assert saved['pages'][0]['script'] == '前页讲稿'
    assert saved['pages'][2]['script'] == '后页讲稿'
    assert saved['ai_review']['stale'] is True
    assert not (path.parent / '2' / 'audio.mp3').exists()
    assert (path.parent / '1' / 'audio.mp3').exists()
    assert (path.parent / '3' / 'audio.mp3').exists()


def test_legacy_draft_reads_ppt_source_instead_of_generated_script(draft, tmp_path):
    from pptx import Presentation

    web_app, path, task = draft
    presentation = Presentation()
    for title in ["前页", "PLC 原始定义"]:
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = title
    ppt = tmp_path / "source.pptx"
    presentation.save(ppt)
    task["file_path"] = str(ppt)
    preview = json.loads(path.read_text())
    page = preview["pages"][1]
    page.pop("source_text")
    source = web_app._page_revision_source(task, preview, page)
    assert "PLC 原始定义" in source
    assert "原讲稿" not in source


def test_revision_route_enforces_manage_permission(draft, monkeypatch):
    web_app, _, _ = draft
    checked = []

    def denied(task_id, manage=False):
        checked.append(manage)
        return None, (web_app.jsonify({"error": "无权操作"}), 403)

    monkeypatch.setattr(web_app, "require_task_access", denied)
    assert request_revision(web_app).status_code == 403
    assert checked == [True]
