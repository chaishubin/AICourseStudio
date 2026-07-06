"""
视频合成工具
"""

from pathlib import Path
from typing import Callable, Optional

from loguru import logger
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)

from ..core.models import DocumentContent, ProcessConfig


class _MoviePyProgressLogger:
    """延迟导入 proglog，并把 MoviePy 帧进度转换为 0..1。"""

    @staticmethod
    def create(
        progress_callback: Optional[Callable[[float], None]],
        cancel_check: Optional[Callable[[], bool]],
    ):
        from proglog import ProgressBarLogger

        class CallbackLogger(ProgressBarLogger):
            def bars_callback(self, bar, attr, value, old_value=None):
                if cancel_check and cancel_check():
                    raise InterruptedError("用户停止了视频生成")
                state = self.bars.get(bar, {})
                total = state.get("total")
                if progress_callback and total and attr == "index":
                    progress_callback(min(1.0, max(0.0, value / total)))

        return CallbackLogger()


class VideoComposer:
    """视频合成器"""

    @staticmethod
    def ffmpeg_params(config: ProcessConfig, normalize_audio: bool = True) -> list[str]:
        """生成适合网页点播的 FFmpeg 输出参数。"""
        params = [
            "-profile:v",
            config.video_profile,
            "-crf",
            str(config.video_crf),
            "-g",
            str(config.video_fps * config.video_gop_seconds),
            "-movflags",
            "+faststart",
            "-c:a",
            config.audio_codec,
            "-b:a",
            config.audio_bitrate,
            "-ar",
            str(config.audio_sample_rate),
            "-ac",
            str(config.audio_channels),
        ]
        if normalize_audio:
            params.extend(
                [
                    "-af",
                    (
                        f"loudnorm=I={config.audio_loudness_lufs}:"
                        "TP=-1.5:LRA=11"
                    ),
                ]
            )
        return params

    @staticmethod
    def _image_clip(
        image_path: Path,
        duration: float,
        config: ProcessConfig,
        audio_clip: AudioFileClip | None = None,
    ):
        """等比缩放课件并置于标准 16:9 画布，避免非标准分辨率或画面拉伸。"""
        image = ImageClip(str(image_path))
        scale = min(
            config.video_width / image.w,
            config.video_height / image.h,
        )
        width = max(2, round(image.w * scale / 2) * 2)
        height = max(2, round(image.h * scale / 2) * 2)
        image = (
            image.resized(new_size=(width, height))
            .with_duration(duration)
            .with_position("center")
        )
        clip = CompositeVideoClip(
            [image],
            size=(config.video_width, config.video_height),
            bg_color=(0, 0, 0),
        ).with_duration(duration)
        if audio_clip is not None:
            clip = clip.with_audio(audio_clip)
        return clip

    @staticmethod
    def compose(
        content: DocumentContent,
        config: ProcessConfig,
        output_path: Path,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        将页面内容合成为视频

        Args:
            content: 文档内容（包含每页的图片、音频路径）
            config: 处理配置
            output_path: 输出视频路径
        """
        clips = []
        output_path.parent.mkdir(parents=True, exist_ok=True)

        for page in content.pages:
            if cancel_check and cancel_check():
                raise InterruptedError("用户停止了视频生成")
            if not page.slide_image or not page.slide_image.exists():
                logger.warning(f"跳过第 {page.page_number} 页：缺少页面图像")
                continue

            # 如果没有音频，检查是否有文本
            if not page.audio or not page.audio.exists():
                # 如果有文本但没有音频（可能是TTS失败），则跳过
                if page.text and page.text.strip():
                    logger.warning(f"跳过第 {page.page_number} 页：有文本但缺少音频")
                else:
                    # 如果既没有文本也没有音频（空白页面），使用默认时长
                    logger.debug(
                        f"第 {page.page_number} 页 无文本无音频，使用默认时长 3s"
                    )
                    image_clip = VideoComposer._image_clip(
                        page.slide_image, 3, config
                    )
                    clips.append(image_clip)
                continue

            # 检查音频文件是否有效（非空）
            if page.audio.stat().st_size == 0:
                logger.warning(f"跳过第 {page.page_number} 页：音频文件为空（TTS转换失败）")
                continue

            # 加载音频获取时长
            audio_clip = AudioFileClip(str(page.audio))
            duration = audio_clip.duration

            # 创建图像片段
            image_clip = VideoComposer._image_clip(
                page.slide_image,
                duration,
                config,
                audio_clip,
            )
            clips.append(image_clip)
            logger.debug(f"第 {page.page_number} 页 片段时长: {duration:.1f}s")

        if not clips:
            logger.error("没有可合成的片段")
            return

        logger.info(f"合并 {len(clips)} 个片段，输出 -> {output_path}")
        final = concatenate_videoclips(clips, method="compose")
        moviepy_logger = _MoviePyProgressLogger.create(
            progress_callback, cancel_check
        )
        try:
            final.write_videofile(
                str(output_path),
                fps=config.video_fps,
                codec=config.video_codec,
                audio_codec=config.audio_codec,
                audio_fps=config.audio_sample_rate,
                audio_bitrate=config.audio_bitrate,
                preset=config.video_preset,
                pixel_format=config.video_pixel_format,
                ffmpeg_params=VideoComposer.ffmpeg_params(config),
                logger=moviepy_logger,
            )
        finally:
            final.close()
            for clip in clips:
                clip.close()

        size_mb = output_path.stat().st_size / 1024 / 1024
        logger.info(f"视频生成完成：{output_path}  ({size_mb:.1f} MB)")
