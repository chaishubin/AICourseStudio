"""路线 A：教案到课程模型、字幕和持久化结构。"""

import json
from unittest.mock import patch

import pytest

from vidppt.core.course import Course
from vidppt.core.models import ProcessConfig
from vidppt.generation.course_builder import CourseBuilder
from vidppt.ingestion.models import SourceDocument, SourceSection
from vidppt.renderers.subtitles import SubtitleRenderer


def test_draft_builder_creates_editable_slides(temp_dir):
    source = SourceDocument(
        title="测试课程",
        source_path=temp_dir / "lesson.docx",
        sections=[
            SourceSection(
                title="第一章",
                paragraphs=["理解核心概念；掌握基本方法；完成课堂练习"],
            )
        ],
    )

    course = CourseBuilder().build(source)

    assert course.source_type == "lesson_plan"
    assert course.sections[0].layout == "cover"
    assert course.sections[1].title == "第一章"
    assert course.sections[1].bullets == [
        "理解核心概念",
        "掌握基本方法",
        "完成课堂练习",
    ]
    assert course.sections[1].script


def test_llm_builder_accepts_json_code_fence(temp_dir):
    class FakeLLM:
        def summarize(self, text, **kwargs):
            return """```json
            {
              "title": "AI 课程",
              "audience": "初学者",
              "learning_objectives": ["理解概念"],
              "slides": [{
                "title": "封面",
                "layout": "cover",
                "bullets": [],
                "script": "欢迎学习。",
                "notes": "开场"
              }]
            }
            ```"""

    source = SourceDocument(
        title="原始标题",
        source_path=temp_dir / "lesson.docx",
        sections=[SourceSection(title="正文", paragraphs=["内容"])],
    )

    course = CourseBuilder(FakeLLM()).build(source)

    assert course.title == "AI 课程"
    assert course.audience == "初学者"
    assert course.sections[0].script == "欢迎学习。"


def test_course_new_fields_round_trip():
    payload = {
        "title": "课程",
        "audience": "教师",
        "learning_objectives": ["会使用"],
        "sections": [
            {
                "id": "slide-1",
                "title": "开始",
                "bullets": ["要点"],
                "layout": "cover",
                "notes": "备注",
                "section_title": "导入",
                "script": "讲稿",
            }
        ],
    }

    restored = Course.from_dict(json.loads(json.dumps(Course.from_dict(payload).to_dict())))

    assert restored.audience == "教师"
    assert restored.learning_objectives == ["会使用"]
    assert restored.sections[0].bullets == ["要点"]
    assert restored.sections[0].notes == "备注"


def test_subtitle_renderer_builds_course_timeline(temp_dir):
    course = Course.from_dict(
        {
            "title": "课程",
            "sections": [
                {"id": "1", "title": "一", "script": "第一句。第二句。"},
                {"id": "2", "title": "二", "script": "第三句。"},
            ],
        }
    )

    output = SubtitleRenderer().render_course(
        [(course.sections[0], 4.0), (course.sections[1], 2.0)],
        temp_dir / "course.srt",
    )
    text = output.read_text(encoding="utf-8")

    assert "00:00:00,000" in text
    assert "00:00:04,000 --> 00:00:06,000" in text
    assert "第三句。" in text


def test_course_pipeline_rejects_video_without_tts(temp_dir):
    from vidppt.core.models import ProcessConfig
    from vidppt.course_pipeline import CoursePipeline

    source = temp_dir / "lesson.docx"
    source.write_bytes(b"placeholder")
    config = ProcessConfig(
        input_path=source,
        output_dir=temp_dir / "out",
        enable_tts=False,
        enable_video=True,
    )

    with pytest.raises(ValueError, match="不能关闭 TTS"):
        CoursePipeline().run(source, config.output_dir, media_config=config)


def test_course_pipeline_burns_subtitles_into_video(temp_dir):
    from vidppt.course_pipeline import CoursePipeline

    video = temp_dir / "base.mp4"
    subtitles = temp_dir / "course.srt"
    output = temp_dir / "course.mp4"

    with (
        patch("vidppt.course_pipeline.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("vidppt.course_pipeline.subprocess.run") as run,
    ):
        CoursePipeline._burn_subtitles(
            video,
            subtitles,
            output,
            ProcessConfig(input_path=video, output_dir=temp_dir),
        )

    command = run.call_args.args[0]
    assert "-vf" in command
    assert "subtitles=filename='course.srt'" in command[command.index("-vf") + 1]
    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-preset") + 1] == "veryfast"
    assert command[command.index("-crf") + 1] == "21"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[command.index("-g") + 1] == "48"
    assert command[command.index("-movflags") + 1] == "+faststart"
    assert run.call_args.kwargs["cwd"] == temp_dir


def test_docx_pipeline_outputs_course_json_and_editable_pptx(temp_dir):
    from docx import Document
    from pptx import Presentation

    from vidppt.course_pipeline import CoursePipeline

    source = temp_dir / "lesson.docx"
    document = Document()
    document.add_heading("Shell 脚本入门", 0)
    document.add_heading("变量", 1)
    document.add_paragraph("理解变量定义；掌握变量引用")
    document.save(source)

    result = CoursePipeline().run(source, temp_dir / "out")

    assert result.course_json.exists()
    assert result.presentation.exists()
    payload = json.loads(result.course_json.read_text(encoding="utf-8"))
    assert payload["title"] == "Shell 脚本入门"
    assert payload["sections"][1]["bullets"] == ["理解变量定义", "掌握变量引用"]

    presentation = Presentation(result.presentation)
    assert len(presentation.slides) == 2
    assert presentation.slides[1].shapes.title.text == "变量"
    assert "理解变量定义" in presentation.slides[1].placeholders[1].text
    assert "理解变量定义" in presentation.slides[1].notes_slide.notes_text_frame.text
