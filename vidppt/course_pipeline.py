"""Word/PDF 教案到 Course JSON 与可编辑 PPTX 的路线 A 流水线。"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .core.course import Course
from .core.interfaces import LLMEngine
from .core.models import ProcessConfig
from .generation import CourseBuilder
from .ingestion import read_source_document
from .renderers import PPTXRenderer, SubtitleRenderer


@dataclass
class CoursePipelineResult:
    course: Course
    course_json: Path
    presentation: Path
    subtitles: Optional[Path] = None
    video: Optional[Path] = None


class CoursePipeline:
    def __init__(self, llm_engine: Optional[LLMEngine] = None):
        self.builder = CourseBuilder(llm_engine)
        self.pptx_renderer = PPTXRenderer()
        self.subtitle_renderer = SubtitleRenderer()

    def run(
        self,
        input_path: Path,
        output_dir: Path,
        media_config: Optional[ProcessConfig] = None,
    ) -> CoursePipelineResult:
        input_path, output_dir = Path(input_path), Path(output_dir)
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        if media_config and media_config.enable_video and not media_config.enable_tts:
            raise ValueError("教案生成视频时不能关闭 TTS；如只需 PPT，请同时使用 --no-tts --no-video")

        document = read_source_document(input_path)
        course = self.builder.build(document)
        output_dir.mkdir(parents=True, exist_ok=True)

        course_json = output_dir / "course.json"
        course_json.write_text(
            json.dumps(course.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        presentation = self.pptx_renderer.render(
            course, output_dir / f"{input_path.stem}.pptx"
        )
        result = CoursePipelineResult(course, course_json, presentation)
        if media_config and (media_config.enable_tts or media_config.enable_video):
            result.subtitles, result.video = self._render_media(
                course, presentation, output_dir, media_config
            )
            course_json.write_text(
                json.dumps(course.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return result

    def _render_media(
        self,
        course: Course,
        presentation: Path,
        output_dir: Path,
        config: ProcessConfig,
    ) -> tuple[Optional[Path], Optional[Path]]:
        """复用稳定的 PPT 渲染/TTS/视频组件，避免复制第二套实现。"""
        from moviepy import AudioFileClip

        from .pipeline import Pipeline
        from .processors.ppt_processor import PPTProcessor
        from .utils.progress import ProgressTracker, ProcessStage
        from .utils.video_composer import VideoComposer

        media_config = ProcessConfig(
            **{
                **config.__dict__,
                "input_path": presentation,
                "output_dir": output_dir,
                "save_intermediate": True,
                "skip_existing": False,
            }
        )
        processor = PPTProcessor()
        content = processor.process(media_config)
        if len(content.pages) != len(course.sections):
            raise RuntimeError(
                f"生成 PPT 页数与课程模型不一致: "
                f"{len(content.pages)} != {len(course.sections)}"
            )
        for page, course_page in zip(content.pages, course.sections):
            page.text = course_page.script or course_page.title

        progress = ProgressTracker(total_pages=len(content.pages))
        pipeline = Pipeline(media_config)
        if media_config.enable_tts:
            pipeline._generate_audio(content, progress)

        timed_pages = []
        for page, course_page in zip(content.pages, course.sections):
            if page.text.strip() and (not page.audio or not page.audio.exists()):
                raise RuntimeError(f"第 {page.page_number} 页配音生成失败")
            if page.audio and page.audio.exists():
                audio = AudioFileClip(str(page.audio))
                duration = audio.duration
                audio.close()
            else:
                duration = 3.0
            course_page.audio = page.audio
            course_page.duration = duration
            timed_pages.append((course_page, duration))

        subtitles = self.subtitle_renderer.render_course(
            timed_pages, output_dir / f"{presentation.stem}.srt"
        )
        if not media_config.enable_video:
            return subtitles, None

        progress.start_stage(ProcessStage.VIDEO)
        silent_video = output_dir / f"{presentation.stem}.base.mp4"
        VideoComposer.compose(content, media_config, silent_video)
        if not silent_video.exists():
            raise RuntimeError("视频合成未产生输出文件")

        final_video = output_dir / f"{presentation.stem}.mp4"
        self._burn_subtitles(silent_video, subtitles, final_video, media_config)
        silent_video.unlink(missing_ok=True)
        progress.complete_stage(ProcessStage.VIDEO)
        return subtitles, final_video

    @staticmethod
    def _burn_subtitles(
        video: Path,
        subtitles: Path,
        output: Path,
        config: ProcessConfig,
    ) -> None:
        """将字幕烧录进画面，确保浏览器和播放器无需开启字幕轨即可显示。"""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("烧录字幕需要 ffmpeg，但当前环境未找到该命令")
        subtitle_name = subtitles.name.replace("\\", r"\\").replace("'", r"\'")
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(video),
                "-vf",
                (
                    f"subtitles=filename='{subtitle_name}':"
                    "force_style='FontName=Noto Sans CJK SC,"
                    "FontSize=18,Outline=2,Shadow=1,MarginV=28'"
                ),
                "-c:v",
                config.video_codec,
                "-preset",
                config.video_preset,
                "-crf",
                str(config.video_crf),
                "-profile:v",
                config.video_profile,
                "-pix_fmt",
                config.video_pixel_format,
                "-g",
                str(config.video_fps * config.video_gop_seconds),
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
            capture_output=True,
            cwd=subtitles.parent,
        )
