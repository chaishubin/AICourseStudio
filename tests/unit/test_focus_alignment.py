"""Behavior regressions for automatic semantic focus, including a real course."""

import copy
import json
from pathlib import Path

import pytest

from vidppt.core.cue_timeline import (
    build_cue_timeline,
    page_cues_from_timeline,
    page_focus_from_timeline,
)
from vidppt.utils.focus_guidance import (
    FOCUS_CUES_VERSION,
    build_focus_cues,
    plan_page_focus,
    rebuild_focus_events,
)


@pytest.fixture
def plc_page():
    return json.loads(
        (Path(__file__).parents[1] / "fixtures/focus/plc_languages.json").read_text()
    )


def test_real_course_repairs_concepts_without_changing_audio_boundaries(plc_page):
    before = copy.deepcopy(plc_page)
    cues, report = plan_page_focus(
        plc_page["script"],
        plc_page["focus_targets"],
        plc_page["focus_cues"],
        page_context=plc_page["title"],
    )
    assert [cue["target_id"] for cue in cues] == plc_page["expected_target_ids"]
    assert [(c["text"], c["start"], c["end"], c["timing_source"]) for c in cues] == [
        (c["text"], c["start"], c["end"], c["timing_source"])
        for c in plc_page["focus_cues"]
    ]
    assert plc_page == before
    assert report["automatic_repair_count"] > 0
    assert report["intentional_clear_count"] == 3
    assert report["manual_review_suggestions"] == []
    assert cues[6]["confidence"] != 0.98
    assert cues[6]["confidence_kind"] == "evidence_score"
    assert (
        cues == plan_page_focus(plc_page["script"], plc_page["focus_targets"], cues)[0]
    )


def test_migration_replaces_stale_events_and_is_idempotent(plc_page):
    import web.app as app

    plc_page["focus_events"] = [{"start": 28.64, "end": 33.34, "target_ids": ["p2-a4"]}]
    preview = {"pages": [plc_page]}
    assert app._ensure_preview_focus(preview)
    assert plc_page["focus_cues_version"] == FOCUS_CUES_VERSION
    event = next(e for e in plc_page["focus_events"] if e["start"] == 28.64)
    assert event["target_ids"] == ["p2-a9"]
    assert not app._ensure_preview_focus(preview)
    timeline = build_cue_timeline(
        [{**plc_page, "duration": 56.26, "cues": plc_page["focus_cues"]}]
    )
    assert page_focus_from_timeline(timeline, 2) == [
        {
            **e,
            "page_number": 2,
            "slide_id": "slide-2",
            "page_start": e["start"],
            "page_end": e["end"],
        }
        for e in plc_page["focus_events"]
    ]
    roundtrip = page_cues_from_timeline(timeline, 2)
    assert [
        c["target_id"]
        for c in plan_page_focus(
            plc_page["script"], plc_page["focus_targets"], roundtrip
        )[0]
    ] == plc_page["expected_target_ids"]


def test_subtitle_boundaries_do_not_change_concept(plc_page):
    script = "第三种是逻辑功能块图。"
    for parts in (
        ["第三种是逻辑功能块图。"],
        ["第三种是逻辑", "功能块图。"],
        ["第三种是", "逻辑功能块图。"],
    ):
        raw = [
            {"text": text, "target_id": "p2-a4", "source": "llm", "subtitle_unit": True}
            for text in parts
        ]
        cues, _ = plan_page_focus(script, plc_page["focus_targets"], raw)
        assert [cue["target_id"] for cue in cues] == ["p2-a9"] * len(parts)


def test_explicit_topic_can_revisit_earlier_target(plc_page):
    cues = build_focus_cues(
        "第三种是逻辑功能块图。回到梯形图。再看指令表。", plc_page["focus_targets"]
    )
    assert [cue["target_id"] for cue in cues] == ["p2-a9", "p2-a3", "p2-a6"]


def test_bilingual_aliases_and_whole_token_abbreviations(plc_page):
    for script in (
        "第三种是逻辑功能块图。",
        "这种语言简称FBD。",
        "Function Block Diagram。",
    ):
        cues, _ = plan_page_focus(script, plc_page["focus_targets"])
        assert cues[0]["target_id"] == "p2-a9"
    cues, _ = plan_page_focus(
        "similar。", [{"id": "il", "text": "指令表 (Instruction List，IL)"}]
    )
    assert cues[0]["target_id"] == ""


def test_same_term_at_two_locations_requires_disambiguation():
    cues, report = plan_page_focus(
        "现在介绍核心概念。",
        [
            {"id": "a", "text": "核心概念"},
            {"id": "b", "text": "核心概念"},
        ],
    )
    assert cues[0]["target_id"] == ""
    assert report["anomalies"][0]["resolution"] == "automatic_clear"


def test_page_context_and_cross_page_target_never_supply_evidence(plc_page):
    args = ("答案可能和多数人的直觉相反。", plc_page["focus_targets"])
    cues, _ = plan_page_focus(
        *args, page_context=plc_page["script"], previous_target_id="p2-a4"
    )
    assert all(not cue["target_id"] for cue in cues)


def test_partial_model_output_does_not_drop_narration():
    script = "明确学习目标。检查学习结果。"
    cues = build_focus_cues(
        script,
        [
            {"id": "a", "text": "明确学习目标"},
            {"id": "b", "text": "检查学习结果"},
        ],
        [{"text": "明确学习目标", "target_id": "a"}],
    )
    assert [cue["target_id"] for cue in cues] == ["a", "b"]


def test_paraphrase_annotation_survives_replanning_and_timeline_roundtrip():
    script = "我们先看一个真实场景。"
    targets = [{"id": "case", "text": "实践案例"}]
    cues, _ = plan_page_focus(
        script, targets, [{"text": script, "source": "llm", "target_id": "case"}]
    )
    assert cues[0]["target_id"] == "case"
    assert cues[0]["model_target_id"] == "case"
    assert plan_page_focus(script, targets, cues)[0] == cues
    timed = [{**cues[0], "start": 0, "end": 2, "subtitle_unit": True}]
    timeline = build_cue_timeline(
        [{"page_number": 1, "script": script, "duration": 2, "cues": timed}]
    )
    assert (
        plan_page_focus(script, targets, page_cues_from_timeline(timeline, 1))[0][0][
            "target_id"
        ]
        == "case"
    )


def test_manual_focus_is_preserved_without_requiring_manual_intervention(plc_page):
    raw = [{"text": "第三种是逻辑功能块图。", "target_id": "p2-a4", "manual": True}]
    cues, _ = plan_page_focus(raw[0]["text"], plc_page["focus_targets"], raw)
    assert cues[0]["target_id"] == "p2-a4"
    assert cues[0]["mapping_source"] == "manual"


def test_manual_intervals_overlay_automatic_events_and_clear_gaps():
    cues = [{"text": "介绍", "target_id": "a", "start": 0, "end": 6}]
    manual = [
        {"start": 1, "end": 2, "target_ids": ["b"], "manual": True},
        {"start": 3, "end": 4, "target_ids": [], "manual": True},
    ]
    events = rebuild_focus_events(cues, manual)
    assert [(e["start"], e["end"], e["target_ids"]) for e in events] == [
        (0, 1, ["a"]),
        (1, 2, ["b"]),
        (2, 3, ["a"]),
        (3, 4, []),
        (4, 6, ["a"]),
    ]
    assert rebuild_focus_events([{"text": "未知时间"}]) is None


def test_invalid_target_keeps_subtitle_timing_but_repairs_mapping():
    raw = [
        {
            "text": "明确学习目标。",
            "target_id": "deleted",
            "subtitle_unit": True,
            "start": 2,
            "end": 3,
            "timing_source": "segment_audio",
        }
    ]
    cues, _ = plan_page_focus(
        raw[0]["text"], [{"id": "a", "text": "明确学习目标"}], raw
    )
    assert cues[0]["target_id"] == "a"
    assert (cues[0]["start"], cues[0]["end"]) == (2, 3)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1])
def test_invalid_geometry_cannot_win_explicit_term(bad):
    targets = [
        {
            "id": "a",
            "text": "明确学习目标",
            "x": bad,
            "y": 0,
            "width": 0.2,
            "height": 0.1,
        }
    ]
    cues, _ = plan_page_focus("明确学习目标。", targets)
    assert not cues[0]["target_id"]


def test_column_headings_are_concepts_even_when_top_position_is_labeled_title():
    targets = [
        {
            "id": "sfc",
            "text": "顺序功能图 (Sequential Function Chart，SFC)",
            "role": "title",
            "x": 0.05,
            "y": 0.13,
            "width": 0.4,
            "height": 0.1,
        },
        {
            "id": "st",
            "text": "结构文本 (Structured Text，ST)",
            "role": "title",
            "x": 0.52,
            "y": 0.13,
            "width": 0.4,
            "height": 0.1,
        },
        {
            "id": "steps",
            "text": "包含步、动作和转换三个要素，用于顺序控制",
            "x": 0.05,
            "y": 0.28,
            "width": 0.4,
            "height": 0.15,
        },
        {
            "id": "text",
            "text": "采用高级语言的语法，执行复杂运算",
            "x": 0.52,
            "y": 0.28,
            "width": 0.4,
            "height": 0.15,
        },
    ]
    script = "接下来我们继续看顺序功能图。核心由步、动作和转换三个要素构成。另一种是结构文本。"
    cues, _ = plan_page_focus(script, targets)
    assert [cue["target_id"] for cue in cues] == ["sfc", "steps", "st"]
    assert cues[0]["knowledge_point_id"] == cues[1]["knowledge_point_id"] == "sfc"


def test_confidence_merge_does_not_hide_weak_continuation():
    from vidppt.core.cue_timeline import focus_events_from_cues

    events = focus_events_from_cues(
        [
            {"start": 0, "end": 1, "target_id": "a", "confidence": 0.96},
            {"start": 1, "end": 2, "target_id": "a", "confidence": 0.44},
        ]
    )
    assert events[0]["confidence"] == 0.44


def test_export_cached_audio_realigns_focus_without_calling_tts(
    plc_page, tmp_path, monkeypatch
):
    import web.app as app
    from vidppt.core.models import DocumentContent, PageContent, ProcessConfig

    config = ProcessConfig(
        input_path=tmp_path / "lesson.pptx", output_dir=tmp_path, skip_existing=True
    )
    audio = tmp_path / "2/audio.mp3"
    audio.parent.mkdir()
    audio.write_bytes(b"existing encoded audio")
    page = PageContent(
        page_number=2,
        text=plc_page["script"],
        metadata={
            **plc_page,
            "audio_signature": app._focus_audio_signature(plc_page["script"], config),
        },
    )

    def unexpected_tts(*args, **kwargs):
        raise AssertionError("focus repair must reuse audio")

    monkeypatch.setattr(app.Pipeline, "_generate_audio", unexpected_tts)
    app._generate_audio_with_focus_segments(DocumentContent(pages=[page]), config)
    assert page.audio == audio
    assert audio.read_bytes() == b"existing encoded audio"
    assert [c["target_id"] for c in page.metadata["focus_cues"]] == plc_page[
        "expected_target_ids"
    ]
    event = next(e for e in page.metadata["focus_events"] if e["start"] == 28.64)
    assert event["target_ids"] == ["p2-a9"]


def test_new_audio_rechecks_whole_sentence_annotation_after_subtitle_split(
    plc_page, tmp_path, monkeypatch
):
    import web.app as app
    from vidppt.core.models import DocumentContent, PageContent, ProcessConfig

    script = "第三种是逻辑功能块图，它采用与、或、非等数字逻辑门电路的图形符号来组织逻辑，既清晰又便于模块化设计。"
    page = PageContent(
        page_number=2,
        text=script,
        metadata={
            "focus_targets": plc_page["focus_targets"],
            "focus_cues": [{"text": script, "source": "llm", "target_id": "p2-a10"}],
        },
    )

    def capture_tts(*args, **kwargs):
        cues = page.metadata["focus_cues"]
        assert len(cues) > 1
        assert cues[0]["target_id"] == "p2-a9"
        assert any(c["target_id"] == "p2-a10" for c in cues[1:])
        assert "".join(c["text"] for c in cues) == script
        raise RuntimeError("verified TTS input")

    monkeypatch.setattr(app.Pipeline, "_generate_audio", capture_tts)
    config = ProcessConfig(input_path=tmp_path / "lesson.pptx", output_dir=tmp_path)
    with pytest.raises(RuntimeError, match="verified TTS input"):
        app._generate_audio_with_focus_segments(DocumentContent(pages=[page]), config)


def test_autosave_cannot_restore_old_automatic_focus_track(
    plc_page, monkeypatch, tmp_path
):
    import web.app as app

    plc_page["focus_events"] = [
        {
            "start": 28.64,
            "end": 33.34,
            "target_ids": ["p2-a4"],
            "mapping_source": "automatic",
        }
    ]
    path = tmp_path / "preview.json"
    path.write_text(json.dumps({"pages": [plc_page]}))
    monkeypatch.setattr(app, "tasks", {"focus": {"output_dir": str(tmp_path)}})
    updated = app._update_preview_scripts(
        "focus",
        [
            {
                "page_number": 2,
                "script": plc_page["script"],
                "focus_events": plc_page["focus_events"],
            }
        ],
    )
    event = next(e for e in updated["pages"][0]["focus_events"] if e["start"] == 28.64)
    assert event["target_ids"] == ["p2-a9"]


def test_explicit_manual_clear_survives_cached_audio_repair(
    plc_page, monkeypatch, tmp_path
):
    import web.app as app

    path = tmp_path / "preview.json"
    path.write_text(json.dumps({"pages": [plc_page]}))
    monkeypatch.setattr(app, "tasks", {"focus": {"output_dir": str(tmp_path)}})
    updated = app._update_preview_scripts(
        "focus", [{"page_number": 2, "script": plc_page["script"], "focus_events": []}]
    )
    page = updated["pages"][0]
    assert page["focus_events"] == []
    assert page["focus_events_manual_clear"]
    app._refresh_automatic_focus_events(page)
    assert page["focus_events"] == []


def test_transition_to_absent_topic_cannot_inherit_model_annotation():
    targets = [{"id": "old", "text": "基本逻辑指令"}]
    script = "接下来，我们将继续深入——认识另一组边沿检测指令：MEP和MEF。"
    cues, _ = plan_page_focus(
        script,
        targets,
        [
            {"text": script, "target_id": "old", "source": "llm"},
        ],
    )
    assert all(not cue["target_id"] for cue in cues)


def test_comparison_can_highlight_multiple_explicit_concepts():
    targets = [
        {"id": "ld", "text": "梯形图 (Ladder Diagram，LD)"},
        {"id": "il", "text": "指令表 (Instruction List，IL)"},
    ]
    cues, _ = plan_page_focus("比较梯形图和指令表的区别。", targets)
    assert cues[0]["target_ids"] == ["ld", "il"]
    events = rebuild_focus_events([{**cues[0], "start": 0, "end": 2}])
    assert events[0]["target_ids"] == ["il", "ld"]


@pytest.mark.parametrize(
    "binding", [{"anchor_id": "case", "action": "switch"}, {"target_text": "实践案例"}]
)
def test_fresh_generation_annotations_are_resolved_before_planning(binding):
    import web.app as app

    script, raw = app._parse_page_focus_response(
        json.dumps(
            {
                "script": "我们先看一个真实场景。",
                "focus_cues": [{"text": "我们先看一个真实场景。", **binding}],
            }
        )
    )
    plans = app._plan_focus_pages(
        [(script, [{"id": "case", "text": "实践案例"}], raw, script)]
    )
    cue = plans[0]["cues"][0]
    assert cue["target_id"] == "case"
    assert cue["model_target_id"] == "case"


@pytest.mark.parametrize('script', [
    '本页介绍梯形图。',
    '欢迎学习梯形图。',
    '接下来我们进入梯形图章节。',
    '请思考一下梯形图。',
    '总结一下，梯形图是本课的重点。',
])
def test_discourse_does_not_highlight_even_when_it_mentions_a_visible_term(script):
    cues, report = plan_page_focus(script, [{'id': 'a', 'text': '梯形图'}])
    assert all(not cue['target_id'] for cue in cues)
    assert report['intentional_clear_count'] > 0


@pytest.mark.parametrize('script', [
    '下面看右侧的梯形图。',
    '因此，梯形图适合表达继电器电路。',
    '例如，梯形图可以用来实现电机启停。',
    '总结一下右侧的梯形图。',
])
def test_local_explanations_keep_focus_despite_discourse_words(script):
    cues, _ = plan_page_focus(script, [{'id': 'a', 'text': '梯形图'}])
    assert any(cue['target_id'] == 'a' for cue in cues)


def test_clear_annotation_and_manual_override_take_precedence_over_term_matching():
    script = '梯形图。'
    targets = [{'id': 'a', 'text': '梯形图'}]
    raw = [{'text': script, 'action': 'clear', 'source': 'llm', 'target_id': 'a'}]
    assert plan_page_focus(script, targets, raw)[0][0]['target_id'] == ''
    raw[0].update(manual=True)
    assert plan_page_focus(script, targets, raw)[0][0]['target_id'] == 'a'


def test_overview_page_suppression_preserves_manual_choices_and_audio_boundaries():
    targets = [{'id': 'a', 'text': '梯形图'}]
    raw = [{'text': '梯形图。', 'start': 1, 'end': 3, 'subtitle_unit': True, 'target_id': 'a'}]
    cue = plan_page_focus('梯形图。', targets, raw, page_context='课程总结')[0][0]
    assert cue['target_id'] == ''
    assert (cue['start'], cue['end']) == (1, 3)
    raw[0]['manual'] = True
    assert plan_page_focus('梯形图。', targets, raw, page_context='课程总结')[0][0]['target_id'] == 'a'


def test_cue_bound_clear_tracks_new_tts_times_without_masking_neighboring_cues():
    cues = [
        {'text': '不聚焦', 'target_id': '', 'manual': True, 'start': 1, 'end': 2},
        {'text': '讲解', 'target_id': 'a', 'start': 2, 'end': 4},
    ]
    old = [{'start': 1, 'end': 3, 'target_ids': [], 'manual': True, 'binding': 'cue'}]
    events = rebuild_focus_events(cues, old)
    assert [(e['start'], e['end'], e['target_ids']) for e in events] == [(2, 4, ['a'])]


@pytest.mark.parametrize('kind', ['cover', 'section', 'summary', 'ending'])
def test_page_layout_suppresses_automatic_focus_independently_of_title(kind):
    cues, _ = plan_page_focus('梯形图。', [{'id': 'a', 'text': '梯形图'}], page_context='电机控制', page_kind=kind)
    assert cues[0]['target_id'] == ''


def test_repeated_rebuilds_keep_cue_choices_bound_to_regenerated_speech():
    cues = [
        {'text': '第一句', 'target_id': 'a', 'start': 0, 'end': 2},
        {'text': '第二句', 'target_id': 'b', 'start': 2, 'end': 4, 'manual': True},
    ]
    old = rebuild_focus_events(cues)
    assert old[-1]['binding'] == 'cue'
    cues[0]['end'] = 3
    cues[1].update(start=3, end=6)
    refreshed = rebuild_focus_events(cues, old)
    assert [(e['start'], e['end'], e['target_ids']) for e in refreshed] == [
        (0, 3, ['a']), (3, 6, ['b'])
    ]
    assert rebuild_focus_events(cues, refreshed) == refreshed
