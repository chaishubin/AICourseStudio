from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from vidppt.utils.focus_guidance import (
    build_focus_cues,
    extract_presentation_focus_targets,
    focus_timeline,
    normalize_focus_cues,
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
    path = tmp_path / "focus.pptx"
    presentation.save(path)

    targets = extract_presentation_focus_targets(path)[0]
    cues = build_focus_cues("首先明确学习目标。随后检查学习结果。", targets)

    assert len(targets) == 3
    assert len(cues) == 2
    assert cues[0]["target_id"] != cues[1]["target_id"]
    assert next(item for item in targets if item["id"] == cues[0]["target_id"])["text"] == "明确学习目标"
    assert next(item for item in targets if item["id"] == cues[1]["target_id"])["text"] == "检查学习结果"


def test_normalize_focus_cues_preserves_valid_manual_target():
    targets = [
        {"id": "first", "text": "目标", "role": "content"},
        {"id": "second", "text": "结果", "role": "content"},
    ]
    cues = normalize_focus_cues(
        [{"text": "旧文本", "target_id": "second"}],
        "现在讲目标。",
        targets,
    )

    assert cues[0]["text"] == "现在讲目标"
    assert cues[0]["target_id"] == "second"


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
        assert len(layers) == 5
        assert all(layer.start == 0 for layer in layers)
        assert all(layer.duration == 3.5 for layer in layers)
    finally:
        for layer in layers:
            layer.close()
