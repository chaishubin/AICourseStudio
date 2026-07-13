"""路线 A：教案到课程模型、字幕和持久化结构。"""

import json
from unittest.mock import patch

import pytest

from vidppt.core.course import Course
from vidppt.core.models import ProcessConfig
from vidppt.generation.course_builder import CourseBuilder
from vidppt.ingestion.models import SourceDocument, SourceSection
from vidppt.renderers.subtitles import SubtitleRenderer
from vidppt.utils.subtitle_rules import (
    normalize_subtitle_text,
    subtitle_chunks,
    wrap_subtitle,
)


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
              "design_spec": {
                "theme": "technology",
                "mood": "理性、未来感",
                "density": "medium",
                "visual_language": "网络节点与数据流"
              },
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
    assert course.metadata["design_spec"]["theme"] == "technology"
    assert course.metadata["design_spec"]["visual_language"] == "网络节点与数据流"


def test_llm_builder_adds_subtitle_safe_area_instruction(temp_dir):
    class FakeLLM:
        system_prompt = ""

        def summarize(self, text, **kwargs):
            self.system_prompt = kwargs["system_prompt"]
            return """
            {
              "title": "AI 课程",
              "slides": [{
                "title": "封面",
                "layout": "cover",
                "bullets": [],
                "script": "欢迎学习。"
              }]
            }
            """

    llm = FakeLLM()
    source = SourceDocument(
        title="原始标题",
        source_path=temp_dir / "lesson.docx",
        sections=[SourceSection(title="正文", paragraphs=["内容"])],
    )

    CourseBuilder(llm).build(source, reserve_subtitle_area=True)

    assert "视频会烧录字幕" in llm.system_prompt
    assert "底部约 15%" in llm.system_prompt


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
    assert "第三句" in text
    assert "第三句。" not in text


def test_subtitle_renderer_splits_long_script_into_readable_cues(temp_dir):
    course = Course.from_dict(
        {
            "title": "课程",
            "sections": [
                {
                    "id": "1",
                    "title": "一",
                    "script": (
                        "第一，厘清模型定位——企业不是要造大脑，而是选对工具脑；"
                        "第二，直面知识库建设中最容易被忽视的管理难题；"
                        "第三，说明为什么连接CRM、ERP等系统才是真实价值。"
                    ),
                },
            ],
        }
    )

    output = SubtitleRenderer().render_course(
        [(course.sections[0], 12.0)], temp_dir / "course.srt"
    )
    blocks = output.read_text(encoding="utf-8").strip().split("\n\n")

    assert len(blocks) >= 3
    assert all(len(block.splitlines()[2:]) == 1 for block in blocks)
    assert all(
        len(line.replace(" ", "")) <= 28
        for block in blocks
        for line in block.splitlines()[2:]
    )
    assert not any(
        any(mark in line for mark in "，。；：！？,.?!;:——")
        for block in blocks
        for line in block.splitlines()[2:]
    )


def test_subtitle_renderer_prefers_semantic_breaks(temp_dir):
    course = Course.from_dict(
        {
            "title": "课程",
            "sections": [
                {
                    "id": "1",
                    "title": "一",
                    "script": (
                        "我们先识别业务场景，然后评估数据基础，同时明确责任边界，"
                        "最后形成可执行的智能体建设路线。"
                    ),
                },
            ],
        }
    )

    output = SubtitleRenderer().render_course(
        [(course.sections[0], 8.0)], temp_dir / "course.srt"
    )
    text = output.read_text(encoding="utf-8")

    assert "然后" in text
    assert "同时" in text
    assert all(
        len(line.replace(" ", "")) <= 28
        for block in text.strip().split("\n\n")
        for line in block.splitlines()[2:]
    )
    assert all(
        len(block.splitlines()[2:]) == 1
        for block in text.strip().split("\n\n")
    )


def test_subtitle_punctuation_normalizes_chinese_course_text():
    text = normalize_subtitle_text(
        "先看CRM,ERP等系统...然后回答:效率提升了吗?确实提升了!"
    )

    assert text == "先看CRM ERP等系统 然后回答 效率提升了吗 确实提升了"


def test_subtitle_punctuation_preserves_decimals_and_adds_terminal_stop():
    text = normalize_subtitle_text("模型版本是3.14,相比2.0更稳定")

    assert text == "模型版本是3 14 相比2 0更稳定"


def test_subtitle_punctuation_normalizes_single_quotes_as_outer_double_quotes():
    text = normalize_subtitle_text(
        "'学习闭环'不是口号,而是\"输入'练习'反馈\"的过程"
    )

    assert text == "学习闭环 不是口号 而是 输入 练习 反馈 的过程"


def test_subtitle_punctuation_preserves_ascii_apostrophes_in_words():
    text = normalize_subtitle_text("这类AI's应用需要关注用户反馈")

    assert text == "这类AI s应用需要关注用户反馈"


def test_subtitle_punctuation_preserves_book_title_marks():
    text = normalize_subtitle_text("推荐阅读《人工智能导论》,再完成练习。")

    assert text == "推荐阅读《人工智能导论》 再完成练习"


def test_subtitle_punctuation_accepts_unmatched_closing_quote():
    text = normalize_subtitle_text("上一段已经开始的内容”。下一句。")

    assert text == "上一段已经开始的内容 下一句"


def test_subtitle_chunks_accept_quote_spanning_semantic_phrases():
    chunks = subtitle_chunks("“第一句话。第二句话”。后续内容。")

    assert "第一句话" in " ".join(chunks)
    assert "第二句话" in " ".join(chunks)
    assert "后续内容" in " ".join(chunks)


def test_subtitle_chunks_use_normalized_punctuation_for_breaks():
    chunks = subtitle_chunks("第一,明确目标;第二,检查结果?第三,复盘改进")

    assert "第一 明确目标" in chunks[0]
    assert "检查结果" in " ".join(chunks)
    assert not any(any(mark in chunk for mark in "，。；：！？,.?!;:") for chunk in chunks)


def test_subtitle_wrapping_preserves_trailing_text_after_soft_break():
    script = (
        "这是一个很长的字幕内容，用来验证如果超过两行十四个字以后，"
        "后面的几个字会不会被截断。"
    )
    rendered = "".join(
        wrap_subtitle(chunk).replace(" ", "")
        for chunk in subtitle_chunks(script)
    )

    assert rendered == normalize_subtitle_text(script).replace(" ", "")
    assert all("\n" not in wrap_subtitle(chunk) for chunk in subtitle_chunks(script))


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
    subtitles.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "今天我们要回答一个更关键的问题：企业该从哪里开始？\n",
        encoding="utf-8",
    )

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
    assert "subtitles=filename='course.burn.ass'" in command[command.index("-vf") + 1]
    subtitle_filter = command[command.index("-vf") + 1]
    assert "drawbox=x=96:y=900:w=1728:h=110" in subtitle_filter
    assert "color=0x111111@0.55" in subtitle_filter
    ass_text = (temp_dir / "course.burn.ass").read_text(encoding="utf-8")
    assert "PlayResX: 1920" in ass_text
    assert "PlayResY: 1080" in ass_text
    assert "WrapStyle: 2" in ass_text
    assert "Style: Default,Noto Sans CJK SC,38,&H00FFFFFF" in ass_text
    assert ",96,96,106,1" in ass_text
    assert "Dialogue: 0,0:00:00.00,0:00:02.00,Default" in ass_text
    assert "今天我们要回答一个更关键的问题 企业该从哪里开始" in ass_text
    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-preset") + 1] == "veryfast"
    assert command[command.index("-crf") + 1] == "21"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[command.index("-g") + 1] == "48"
    assert command[command.index("-movflags") + 1] == "+faststart"
    assert run.call_args.kwargs["cwd"] == temp_dir


def test_course_packaging_renders_course_template_images(temp_dir):
    from PIL import Image

    from vidppt.utils.course_packaging import _render_packaging_image

    config = ProcessConfig(
        input_path=temp_dir / "source.pptx",
        output_dir=temp_dir,
        video_width=960,
        video_height=540,
    )
    options = {
        "template": "university",
        "organization": "测试大学",
        "instructor": "王老师",
        "outro_text": "感谢观看",
        "use_slide_background": False,
    }

    intro = temp_dir / "intro.png"
    _render_packaging_image(
        intro,
        config,
        options,
        kind="intro",
        course_title="人工智能导论",
        segment_title="第一讲 课程导入",
        logo_path=None,
        background_path=None,
    )

    with Image.open(intro) as rendered:
        assert rendered.size == (960, 540)
        assert len(rendered.getcolors(maxcolors=1_000_000)) > 1


def test_university_title_card_uses_open_brand_rail_instead_of_closed_frame(temp_dir):
    from PIL import Image

    from vidppt.utils.course_packaging import _render_packaging_image

    config = ProcessConfig(
        input_path=temp_dir / "source.pptx",
        output_dir=temp_dir,
        video_width=960,
        video_height=540,
    )
    output = temp_dir / "modern-university.png"
    _render_packaging_image(
        output,
        config,
        {
            "template": "university",
            "accent_color": "#22C55E",
            "background_style": "solid",
            "use_slide_background": False,
            "intro_label": "在线开放课程",
            "intro_title": "人工智能赋能教学创新",
            "organization": "测试大学",
            "department": "人工智能学院",
            "instructor": "王老师",
        },
        kind="intro",
        course_title="人工智能导论",
        segment_title="",
        logo_path=None,
        background_path=None,
    )

    with Image.open(output).convert("RGB") as rendered:
        rail = rendered.getpixel((103, 270))
        former_top_border = rendered.getpixel((480, 92))
        assert rail[1] > rail[0] * 2
        assert former_top_border != rail
        assert former_top_border[2] > former_top_border[1] > former_top_border[0]


def test_course_packaging_keeps_legacy_academic_template(temp_dir):
    from PIL import Image

    from vidppt.utils.course_packaging import _render_packaging_image

    config = ProcessConfig(
        input_path=temp_dir / "source.pptx",
        output_dir=temp_dir,
        video_width=960,
        video_height=540,
    )
    options = {
        "template": "academic",
        "organization": "测试大学",
        "instructor": "王老师",
        "outro_text": "感谢观看",
        "use_slide_background": False,
    }

    intro = temp_dir / "academic.png"
    _render_packaging_image(
        intro,
        config,
        options,
        kind="intro",
        course_title="人工智能导论",
        segment_title="",
        logo_path=None,
        background_path=None,
    )

    with Image.open(intro) as rendered:
        assert rendered.size == (960, 540)
        assert len(rendered.getcolors(maxcolors=1_000_000)) > 1


def test_course_packaging_renders_credits_template_images(temp_dir):
    from PIL import Image

    from vidppt.utils.course_packaging import _render_packaging_image

    config = ProcessConfig(
        input_path=temp_dir / "source.pptx",
        output_dir=temp_dir,
        video_width=960,
        video_height=540,
    )
    options = {
        "template": "credits",
        "organization": "测试大学",
        "outro_text": "参考资料请见课程平台",
        "use_slide_background": False,
    }

    outro = temp_dir / "outro.png"
    _render_packaging_image(
        outro,
        config,
        options,
        kind="outro",
        course_title="人工智能导论",
        segment_title="",
        logo_path=None,
        background_path=None,
    )

    with Image.open(outro) as rendered:
        assert rendered.size == (960, 540)
        assert len(rendered.getcolors(maxcolors=1_000_000)) > 1


def test_course_packaging_uses_local_video_as_animated_background(temp_dir, monkeypatch):
    from unittest.mock import Mock

    from vidppt.utils import course_packaging

    video = temp_dir / "campus.mp4"
    video.write_bytes(b"video")
    output = temp_dir / "intro.mp4"
    config = ProcessConfig(
        input_path=temp_dir / "source.pptx",
        output_dir=temp_dir,
        video_width=960,
        video_height=540,
    )
    run = Mock()
    monkeypatch.setattr(course_packaging.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        course_packaging,
        "_render_packaging_image",
        lambda path, *args, **kwargs: path.write_bytes(b"png"),
    )
    monkeypatch.setattr(course_packaging.subprocess, "run", run)

    course_packaging._render_packaging_clip(
        output,
        config,
        {
            "intro_video_path": str(video),
            "enable_music": False,
            "enable_motion": False,
            "use_slide_background": False,
        },
        kind="intro",
        course_title="人工智能导论",
        segment_title="",
        logo_path=None,
        background_path=None,
    )

    command = run.call_args.args[0]
    assert str(video) in command
    filter_complex = command[command.index("-filter_complex") + 1]
    assert "[bg][foreground]overlay=shortest=1" in filter_complex
    assert "colorchannelmixer=aa=0.82" not in filter_complex
    assert command[command.index("-t", command.index("-ac")) + 1] == "4.00"


def test_course_packaging_video_uses_transparent_visual_overlay(temp_dir):
    from PIL import Image

    from vidppt.utils.course_packaging import _render_packaging_image

    config = ProcessConfig(
        input_path=temp_dir / "source.pptx",
        output_dir=temp_dir,
        video_width=960,
        video_height=540,
    )
    overlay = temp_dir / "overlay.png"

    _render_packaging_image(
        overlay,
        config,
        {
            "template": "academic",
            "primary_color": "#12324A",
            "_transparent_background": True,
        },
        kind="intro",
        course_title="人工智能导论",
        segment_title="",
        logo_path=None,
        background_path=None,
    )

    with Image.open(overlay) as rendered:
        assert rendered.mode == "RGBA"
        alpha = rendered.getchannel("A")
        minimum, maximum = alpha.getextrema()
        assert minimum < 16
        assert maximum == 255
        assert sum(1 for value in alpha.getdata() if value < 128) > 960 * 540 // 2


def test_course_packaging_zoom_filter_keeps_one_output_frame_per_input_frame(temp_dir):
    from vidppt.utils.course_packaging import _video_filter

    config = ProcessConfig(
        input_path=temp_dir / "source.pptx",
        output_dir=temp_dir,
        video_width=960,
        video_height=540,
        video_fps=24,
    )

    video_filter = _video_filter(config, 4.0, True, "zoom")

    assert "d=1" in video_filter
    assert "d=96" not in video_filter
    assert "on/96" in video_filter


def test_course_packaging_stages_title_and_identity_reveals(temp_dir):
    from vidppt.utils.course_packaging import _soundmark_filter, _staged_video_filter

    config = ProcessConfig(
        input_path=temp_dir / "source.pptx",
        output_dir=temp_dir,
        video_width=960,
        video_height=540,
        video_fps=24,
    )

    video_filter = _staged_video_filter(
        config,
        4.0,
        "zoom",
        use_video_background=True,
        title_input=2,
        meta_input=3,
    )
    audio_filter = _soundmark_filter(4, 4.0, 4)

    assert "[2:v]format=rgba,fade=t=in" in video_filter
    assert "[3:v]format=rgba,fade=t=in" in video_filter
    assert "overlay=x='-24+24*" in video_filter
    assert "loudnorm=I=-24" in audio_filter
    assert "[stinger]" in audio_filter


def test_course_packaging_soft_transition_keeps_timeline_length(temp_dir, monkeypatch):
    from vidppt.utils import course_packaging

    first = temp_dir / "intro.mp4"
    second = temp_dir / "course.mp4"
    first.write_bytes(b"intro")
    second.write_bytes(b"course")
    config = ProcessConfig(input_path=temp_dir / "source.pptx", output_dir=temp_dir)
    commands = []

    class FinishedProcess:
        returncode = 0

        def poll(self):
            return 0

    monkeypatch.setattr(course_packaging, "_ensure_audio_stream", lambda _f, clip, _d, _c: clip)
    monkeypatch.setattr(course_packaging, "_probe_media_duration", lambda _path: 4.0)
    monkeypatch.setattr(
        course_packaging.subprocess,
        "Popen",
        lambda command, **_kwargs: commands.append(command) or FinishedProcess(),
    )

    course_packaging._concat_with_ffmpeg(
        "/usr/bin/ffmpeg",
        [first, second],
        temp_dir / "output.mp4",
        config,
        transition_seconds=0.35,
    )

    filter_complex = commands[0][commands[0].index("-filter_complex") + 1]
    assert "fade=t=out:st=3.650:d=0.350" in filter_complex
    assert "fade=t=in:st=0:d=0.350" in filter_complex
    assert "concat=n=2:v=1:a=1" in filter_complex
    assert "xfade" not in filter_complex


def test_course_packaging_inserts_mid_clip_between_lesson_segments(temp_dir, monkeypatch):
    from vidppt.utils import course_packaging

    source = temp_dir / "course.mp4"
    output = temp_dir / "packaged.mp4"
    source.write_bytes(b"course")
    config = ProcessConfig(input_path=temp_dir / "source.pptx", output_dir=temp_dir)
    extracted = []
    concatenated = []

    monkeypatch.setattr(course_packaging.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        course_packaging,
        "_render_packaging_clip",
        lambda path, *_args, **_kwargs: path.write_bytes(b"mid"),
    )

    def extract(_ffmpeg, _source, path, _config, *, start, duration):
        extracted.append((start, duration))
        path.write_bytes(b"segment")

    def concat(_ffmpeg, clips, path, _config, _cancel_check, **_kwargs):
        concatenated.extend(item.name for item in clips)
        path.write_bytes(b"packaged")

    monkeypatch.setattr(course_packaging, "_extract_video_range", extract)
    monkeypatch.setattr(course_packaging, "_concat_with_ffmpeg", concat)

    course_packaging.package_course_video(
        source,
        output,
        config,
        {"enable_mid": True, "enable_intro": False, "enable_outro": False},
        course_title="人工智能导论",
        segment_durations=[12.0, 18.0, 9.0],
    )

    assert extracted == [(0.0, 12.0), (12.0, 18.0), (30.0, None)]
    assert concatenated == [
        "segment_001.mp4", "mid.mp4", "segment_002.mp4", "mid.mp4", "segment_003.mp4"
    ]
    assert output.read_bytes() == b"packaged"


def test_course_packaging_shifts_external_subtitles_for_intro_and_mid(temp_dir):
    from vidppt.utils.course_packaging import shift_srt_for_packaging

    subtitles = temp_dir / "course.srt"
    subtitles.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\n第一段\n\n"
        "2\n00:00:10,000 --> 00:00:11,000\n第二段\n\n"
        "3\n00:00:30,000 --> 00:00:31,000\n第三段\n",
        encoding="utf-8",
    )

    shift_srt_for_packaging(
        subtitles,
        intro_seconds=4,
        segment_durations=[10, 20, 8],
        mid_seconds=2.5,
    )

    shifted = subtitles.read_text(encoding="utf-8")
    assert "00:00:04,000 --> 00:00:05,000" in shifted
    assert "00:00:16,500 --> 00:00:17,500" in shifted
    assert "00:00:39,000 --> 00:00:40,000" in shifted


def test_course_pipeline_scales_subtitle_design_units_for_video_resolution(temp_dir):
    from vidppt.course_pipeline import CoursePipeline

    config = ProcessConfig(
        input_path=temp_dir / "source.pptx",
        output_dir=temp_dir,
        video_width=1280,
        video_height=720,
        subtitle_x=96,
        subtitle_y=900,
        subtitle_width=1728,
        subtitle_height=110,
        subtitle_font_size=46,
        subtitle_outline_width=3,
    )

    subtitle_filter = CoursePipeline._subtitle_filter("course.burn.ass", config)
    layout = CoursePipeline._subtitle_layout(config)

    assert "drawbox=x=64:y=600:w=1152:h=73" in subtitle_filter
    assert "subtitles=filename='course.burn.ass'" in subtitle_filter
    assert layout["font_size"] == 29
    assert layout["outline_width"] == 1.16
    assert layout["margin_r"] == 64
    assert layout["margin_v"] == 69


def test_moviepy_progress_uses_video_frames_not_audio_chunks():
    from vidppt.utils.video_composer import _MoviePyProgressLogger

    reported = []
    progress = _MoviePyProgressLogger.create(reported.append, None)
    progress.bars["chunk"] = {"total": 10}
    progress.bars_callback("chunk", "index", 10)
    assert reported == []

    progress.bars["frame_index"] = {"total": 200}
    progress.bars_callback("frame_index", "index", 50)
    assert reported == [0.25]


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

    result = CoursePipeline(footer_text="匠心课堂").run(source, temp_dir / "out")

    assert result.course_json.exists()
    assert result.presentation.exists()
    payload = json.loads(result.course_json.read_text(encoding="utf-8"))
    assert payload["title"] == "Shell 脚本入门"
    assert payload["metadata"]["footer_text"] == "匠心课堂"
    assert payload["sections"][1]["bullets"] == ["理解变量定义", "掌握变量引用"]

    presentation = Presentation(result.presentation)
    assert len(presentation.slides) == 2
    slide_text = "\n".join(
        shape.text for shape in presentation.slides[1].shapes if hasattr(shape, "text")
    )
    assert "变量" in slide_text
    assert "理解变量定义" in slide_text
    assert "匠心课堂" in slide_text
    assert "理解变量定义" in presentation.slides[1].notes_slide.notes_text_frame.text


def test_course_pipeline_places_logo_without_cropping(temp_dir):
    from docx import Document
    from PIL import Image
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from vidppt.course_pipeline import CoursePipeline

    source = temp_dir / "lesson.docx"
    document = Document()
    document.add_heading("学校课程", 0)
    document.add_heading("课程内容", 1)
    document.add_paragraph("知识点一；知识点二")
    document.save(source)
    logo = temp_dir / "school.png"
    Image.new("RGBA", (400, 100), (20, 80, 160, 255)).save(logo)

    result = CoursePipeline(logo_path=logo).run(source, temp_dir / "out-logo")
    payload = json.loads(result.course_json.read_text(encoding="utf-8"))
    assert payload["metadata"]["logo_path"] == str(logo)

    presentation = Presentation(result.presentation)
    for slide in presentation.slides:
        pictures = [
            shape for shape in slide.shapes
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
        ]
        assert pictures
        logo_shape = pictures[-1]
        assert abs((logo_shape.width / logo_shape.height) - 4.0) < 0.05
        assert logo_shape.width <= 1.35 * 914400
        assert logo_shape.height <= 0.72 * 914400


def test_course_pipeline_generates_illustrations_before_pptx(temp_dir):
    from docx import Document
    from vidppt.course_pipeline import CoursePipeline

    source = temp_dir / "lesson.docx"
    document = Document()
    document.add_heading("智能制造", 0)
    document.add_heading("精密加工", 1)
    document.add_paragraph("理解加工精度；掌握质量控制")
    document.save(source)

    class FakeIllustrations:
        def generate_for_course(self, course, output_dir, max_images):
            assert max_images == 2
            course.sections[0].metadata["illustration_path"] = "cover.png"
            return []

    result = CoursePipeline(
        illustration_generator=FakeIllustrations(),
        max_illustrations=2,
    ).run(source, temp_dir / "out")
    payload = json.loads(result.course_json.read_text(encoding="utf-8"))

    assert payload["metadata"]["visual_theme"] == "industry"
    assert payload["metadata"]["visual_style"] == "technical"
    assert payload["sections"][0]["metadata"]["illustration_path"] == "cover.png"


def test_pptx_theme_selects_distinct_visual_systems():
    from vidppt.core.course import Course, CourseSection
    from vidppt.renderers.pptx_renderer import PPTXRenderer

    samples = {
        "technology": ("人工智能与数据系统", "digital"),
        "culture": ("中国传统文学艺术", "editorial"),
        "nature": ("生态环境与自然保护", "organic"),
        "business": ("企业营销与运营管理", "executive"),
        "health": ("医疗护理与健康管理", "organic"),
        "public": ("公共政策与社会治理", "executive"),
        "finance": ("财务审计与证券投资", "executive"),
    }
    for expected_theme, (title, expected_style) in samples.items():
        course = Course(
            title=title,
            sections=[CourseSection(id="slide-1", title=title, layout="cover")],
        )
        renderer = PPTXRenderer()
        renderer._apply_course_theme(course)
        assert course.metadata["visual_theme"] == expected_theme
        assert course.metadata["visual_style"] == expected_style


def test_manual_theme_overrides_content_and_auto_layouts_vary():
    from vidppt.core.course import Course, CourseSection
    from vidppt.renderers.pptx_renderer import PPTXRenderer

    course = Course(
        title="人工智能系统",
        metadata={"visual_theme": "culture"},
        sections=[
            CourseSection(id="1", title="封面", layout="cover"),
            CourseSection(
                id="2",
                title="系统实施流程",
                bullets=["需求分析", "方案设计", "部署验证"],
            ),
            CourseSection(
                id="3",
                title="架构的四大支柱",
                bullets=["模型", "知识", "系统", "治理"],
            ),
        ],
    )
    renderer = PPTXRenderer()
    renderer._apply_course_theme(course)

    assert course.metadata["visual_theme"] == "culture"
    assert renderer._resolve_layout(course.sections[1], 2) == "process"
    assert renderer._resolve_layout(course.sections[2], 3) == "framework"


def test_pptx_sequence_marker_numbers_are_centered():
    from pptx import Presentation
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches

    from vidppt.core.course import CourseSection
    from vidppt.renderers.pptx_renderer import PPTXRenderer

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    renderer = PPTXRenderer()
    renderer.subtitle_safe_area = None
    renderer.footer_text = "AI COURSE STUDIO"

    renderer._render_sequence(
        slide,
        CourseSection(
            id="process",
            title="实施步骤",
            bullets=["需求分析", "方案设计"],
        ),
        1,
        1,
        "process",
    )

    number_box = next(
        shape for shape in slide.shapes
        if getattr(shape, "has_text_frame", False) and shape.text == "1"
    )
    assert number_box.left == Inches(1.62)
    assert number_box.top == Inches(3.03)
    assert number_box.width == Inches(0.5)
    assert number_box.height == Inches(0.5)
    assert number_box.text_frame.paragraphs[0].alignment == PP_ALIGN.CENTER


def test_pptx_renderer_converts_subtitle_area_to_content_bounds():
    from vidppt.core.course import Course, CourseSection
    from vidppt.renderers.pptx_renderer import PPTXRenderer

    course = Course(
        title="带字幕课程",
        metadata={
            "subtitle_safe_area": {
                "x": 96,
                "y": 900,
                "width": 1728,
                "height": 110,
                "canvas_width": 1920,
                "canvas_height": 1080,
            }
        },
        sections=[CourseSection(id="1", title="正文", bullets=["要点"])],
    )
    renderer = PPTXRenderer()
    renderer.subtitle_safe_area = renderer._subtitle_safe_area(course)

    _, bottom = renderer._content_bounds(2.05, 6.55)

    assert renderer.subtitle_safe_area["y"] == pytest.approx(6.25)
    assert bottom == pytest.approx(6.07)
