from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from vidppt.utils.focus_guidance import (
    FOCUS_CUES_VERSION,
    build_focus_cues,
    extract_presentation_focus_targets,
    focus_timeline,
    normalize_focus_targets,
    normalize_focus_cues,
    plan_page_focus,
    validate_focus_events,
)
from vidppt.utils.video_composer import VideoComposer


def test_extract_targets_and_match_narration(tmp_path: Path):
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    title = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(7), Inches(0.7))
    title.text = "人工智能课程"
    first = slide.shapes.add_textbox(Inches(0.8), Inches(2), Inches(5), Inches(0.8))
    first.text = "明确学习目标"
    second = slide.shapes.add_textbox(Inches(6.5), Inches(2), Inches(5), Inches(0.8))
    second.text = "检查学习结果"
    layout_label = slide.shapes.add_textbox(Inches(0.8), Inches(5), Inches(2), Inches(0.5))
    layout_label.text = "封面页"
    path = tmp_path / "focus.pptx"
    presentation.save(path)

    targets = extract_presentation_focus_targets(path)[0]
    cues = build_focus_cues("首先明确学习目标。随后检查学习结果。", targets)

    assert len(targets) == 3
    assert all(target["id"].startswith("p1-a") for target in targets)
    assert len(cues) == 2
    assert cues[0]["target_id"] != cues[1]["target_id"]
    assert next(item for item in targets if item["id"] == cues[0]["target_id"])["text"] == "明确学习目标"
    assert next(item for item in targets if item["id"] == cues[1]["target_id"])["text"] == "检查学习结果"
    assert all(item["text"] != "封面页" for item in targets)


def test_normalize_focus_cues_preserves_valid_manual_target():
    targets = [
        {"id": "first", "text": "目标", "role": "content"},
        {"id": "second", "text": "结果", "role": "content"},
    ]
    cues = normalize_focus_cues(
        [{"text": "现在讲目标", "target_id": "second", "manual": True}],
        "现在讲目标。",
        targets,
    )

    assert cues[0]["text"] == "现在讲目标"
    assert cues[0]["target_id"] == "second"
    assert cues[0]["manual"] is True


def test_normalize_focus_cues_preserves_llm_annotation_when_script_is_unchanged():
    targets = [{"id": "case", "text": "实践案例", "role": "content"}]
    raw = [{
        "text": "我们先看一个真实场景",
        "target_id": "case",
        "weight": 10,
        "source": "llm",
    }]

    cues = normalize_focus_cues(raw, "我们先看一个真实场景。", targets)

    assert cues == raw


def test_low_similarity_narration_uses_transcript_without_wrong_box():
    targets = [
        {"id": "summary", "text": "课程介绍与学习目标", "role": "content"},
    ]

    cues = build_focus_cues("答案可能和多数人的直觉相反。", targets)

    assert cues[0]["target_id"] == ""
    assert cues[0]["confidence"] < 0.34


def test_llm_focus_annotation_is_preferred_over_similarity_matching():
    targets = [
        {"id": "first", "text": "学习目标", "role": "content"},
        {"id": "second", "text": "实践案例", "role": "content"},
    ]

    cues = build_focus_cues(
        "我们先看一个真实场景。",
        targets,
        [{"text": "我们先看一个真实场景", "target_text": "实践案例"}],
    )

    assert cues == [{
        "text": "我们先看一个真实场景",
        "target_id": "second",
        "anchor_id": "second",
        "weight": 10,
        "source": "llm",
        "confidence": 1.0,
    }]


def test_page_planner_records_evidence_and_safely_clears_ambiguous_match():
    targets = [
        {"id": "a", "text": "方法一", "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1},
        {"id": "b", "text": "方法二", "x": 0.6, "y": 0.2, "width": 0.3, "height": 0.1},
    ]
    cues, report = plan_page_focus("这里我们继续分析这个问题。", targets, page_context="方法一 方法二")

    assert cues[0]["target_id"] == ""
    assert cues[0]["decision"] == "no_focus"
    assert cues[0]["evidence"]
    assert report["cue_count"] == 1
    assert report["degraded_count"] == 1
    assert report["manual_review_suggestions"] == []
    assert report["anomalies"][0]["resolution"] == "automatic_clear"


def test_event_validator_drops_invalid_geometry_target_and_time():
    targets = [
        {"id": "good", "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
        {"id": "offscreen", "x": 0.9, "y": 0.1, "width": 0.3, "height": 0.2},
    ]
    events = [
        {"start": 0, "end": 1, "target_ids": ["good"]},
        {"start": 1, "end": 2, "target_ids": ["offscreen"]},
        {"start": 2, "end": 5, "target_ids": ["missing"]},
    ]

    result = validate_focus_events(events, targets, 3)

    assert [event["target_ids"] for event in result] == [["good"], []]


def test_normalize_focus_targets_removes_layout_labels_and_sorts_visually():
    targets = [
        {"id": "second", "text": "第二项", "x": 0.1, "y": 0.6},
        {"id": "label", "text": "封面页", "x": 0.1, "y": 0.2},
        {"id": "first", "text": "第一项", "x": 0.1, "y": 0.4},
    ]

    normalized = normalize_focus_targets(targets)

    assert [target["id"] for target in normalized] == ["first", "second"]


def test_normalize_focus_cues_recomputes_old_automatic_choices():
    targets = [
        {"id": "wrong", "text": "课程介绍", "role": "content"},
        {"id": "right", "text": "检查学习结果", "role": "content"},
    ]

    cues = normalize_focus_cues(
        [{"text": "检查学习结果", "target_id": "wrong"}],
        "随后检查学习结果。",
        targets,
    )

    assert cues[0]["target_id"] == "right"


def test_focus_timeline_uses_real_page_duration_and_weights():
    timeline = focus_timeline(
        [
            {"text": "短", "target_id": "first", "weight": 1},
            {"text": "较长内容", "target_id": "second", "weight": 3},
        ],
        8.0,
    )

    assert timeline[0]["start"] == 0
    assert timeline[0]["end"] == 2
    assert timeline[1]["start"] == 2
    assert timeline[1]["end"] == 8


def test_focus_timeline_preserves_unfocused_time_gaps():
    timeline = focus_timeline(
        [
            {"text": "聚焦", "target_id": "first", "weight": 1},
            {"text": "整页", "target_id": "", "weight": 1},
            {"text": "再次聚焦", "target_id": "second", "weight": 2},
        ],
        8.0,
    )

    assert [(cue["start"], cue["end"]) for cue in timeline] == [
        (0, 2), (2, 4), (4, 8),
    ]


def test_focus_timeline_prefers_real_segment_audio_timestamps():
    timeline = focus_timeline(
        [
            {"text": "第一段", "target_id": "first", "start": 0, "end": 1.7},
            {"text": "第二段", "target_id": "second", "start": 1.7, "end": 5.2},
        ],
        5.2,
    )

    assert [(cue["start"], cue["end"]) for cue in timeline] == [
        (0.0, 1.7), (1.7, 5.2),
    ]


def test_existing_preview_focus_cues_are_migrated():
    import web.app as web_app

    preview = {"pages": [{
        "page_number": 1,
        "script": "答案可能和多数人的直觉相反。",
        "focus_targets": [
            {"id": "summary", "text": "课程介绍与学习目标", "role": "content"},
        ],
        "focus_cues": [
            {"text": "答案可能和多数人的直觉相反", "target_id": "summary"},
        ],
    }]}

    changed = web_app._ensure_preview_focus(preview)

    assert changed is True
    assert preview["pages"][0]["focus_cues_version"] == FOCUS_CUES_VERSION
    assert preview["pages"][0]["focus_cues"][0]["target_id"] == ""


def test_video_focus_layers_follow_cue_timeline():
    layers = VideoComposer._focus_layers(
        [{
            "id": "point",
            "x": 0.1,
            "y": 0.2,
            "width": 0.4,
            "height": 0.1,
        }],
        [{"text": "讲解", "target_id": "point", "weight": 1}],
        duration=3.5,
        image_width=1920,
        image_height=1080,
        image_left=0,
        image_top=0,
    )
    try:
        assert len(layers) == 1
        assert all(layer.start == 0 for layer in layers)
        assert all(layer.duration == 3.5 for layer in layers)
    finally:
        for layer in layers:
            layer.close()


def test_video_focus_layers_support_spotlight_and_underline_styles():
    targets = [{
        "id": "point",
        "x": 0.2,
        "y": 0.2,
        "width": 0.4,
        "height": 0.2,
    }]
    cues = [{"text": "讲解", "target_id": "point", "weight": 1}]
    generated = []
    try:
        spotlight = VideoComposer._focus_layers(
            targets, cues, 2, 1280, 720, 0, 0, "spotlight"
        )
        underline = VideoComposer._focus_layers(
            targets, cues, 2, 1280, 720, 0, 0, "underline"
        )
        generated.extend(spotlight + underline)
        assert len(spotlight) == 5
        assert len(underline) == 1
    finally:
        for layer in generated:
            layer.close()


def test_llm_can_continue_and_clear_focus_without_losing_narration():
    from vidppt.utils.focus_guidance import build_focus_cues

    targets = [{"id": "a", "text": "核心概念", "role": "content"}]
    cues = build_focus_cues("核心概念说明过渡", targets, annotated_cues=[
        {"text": "核心概念", "action": "switch", "anchor_id": "a"},
        {"text": "说明", "action": "continue", "anchor_id": ""},
        {"text": "过渡", "action": "clear", "anchor_id": ""},
    ])
    assert [cue["target_id"] for cue in cues] == ["a", "a", ""]
    assert "".join(cue["text"] for cue in cues) == "核心概念说明过渡"


def test_spotlight_multiple_targets_share_one_clear_region():
    from vidppt.utils.video_composer import VideoComposer

    targets = [
        {"id": "a", "x": 0.1, "y": 0.2, "width": 0.1, "height": 0.2},
        {"id": "b", "x": 0.7, "y": 0.2, "width": 0.1, "height": 0.2},
    ]
    layers = VideoComposer._focus_layers(
        targets, [{"start": 0, "end": 1, "target_ids": ["a", "b"]}],
        1, 1000, 500, 0, 0, "spotlight",
    )
    # One shared shade leaves both targets visible instead of each shade
    # darkening the other target.
    assert len(layers) == 5
    for layer in layers:
        layer.close()


def test_exported_video_applies_page_visibility_without_mutating_saved_events(tmp_path, monkeypatch):
    from PIL import Image
    from vidppt.core.models import ProcessConfig
    image_path = tmp_path / 'slide.png'
    Image.new('RGB', (160, 90), 'white').save(image_path)
    config = ProcessConfig(input_path=image_path, output_dir=tmp_path, video_width=160, video_height=90)
    events = [
        {'start': 0, 'end': 1, 'target_ids': ['a']},
        {'start': 1, 'end': 2, 'target_ids': ['b'], 'manual': True},
    ]
    captured = []
    monkeypatch.setattr(VideoComposer, '_focus_layers', lambda targets, track, *args: captured.append(track) or [])
    for mode, expected in [('off', []), ('manual', [events[1]]), ('auto', events)]:
        clip = VideoComposer._image_clip(image_path, 2, config, metadata={
            'focus_mode': mode, 'focus_events': events, 'focus_targets': []
        })
        try:
            assert captured[-1] == expected
            assert len(events) == 2
        finally:
            clip.close()
