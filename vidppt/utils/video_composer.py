"""
视频合成工具
"""

from pathlib import Path
from typing import Callable, Optional

from loguru import logger
from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)

from ..core.models import DocumentContent, ProcessConfig
from .focus_guidance import focus_timeline


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
                # MoviePy 会依次报告音频 chunk 和视频 frame_index。
                # 音频条会更早到达 100%，不能拿它冒充视频编码进度。
                if bar != "frame_index" or attr != "index":
                    return
                state = self.bars.get(bar, {})
                total = state.get("total")
                if progress_callback and total:
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
        metadata: dict | None = None,
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
        layers = [image]
        if metadata and metadata.get("focus_highlight", True):
            from ..core.cue_timeline import select_focus_events

            layers.extend(
                VideoComposer._focus_layers(
                    metadata.get("focus_targets", []),
                    select_focus_events(
                        metadata.get("focus_events", metadata.get("focus_cues", [])),
                        metadata.get("focus_mode", "auto"),
                    ),
                    duration,
                    width,
                    height,
                    (config.video_width - width) // 2,
                    (config.video_height - height) // 2,
                    metadata.get("focus_highlight_style", "underline"),
                    metadata.get("focus_highlight_color", "#FFAE1F"),
                    metadata.get("focus_highlight_width", 2),
                )
            )
        clip = CompositeVideoClip(
            layers,
            size=(config.video_width, config.video_height),
            bg_color=(0, 0, 0),
        ).with_duration(duration)
        if audio_clip is not None:
            clip = clip.with_audio(audio_clip)
        return clip

    @staticmethod
    def _focus_layers(
        targets: list[dict],
        cues: list[dict],
        duration: float,
        image_width: int,
        image_height: int,
        image_left: int,
        image_top: int,
        style: str = "underline",
        color: str = "#FFAE1F",
        line_width: int = 2,
    ) -> list:
        """Create time-bound outline, spotlight, or underline focus layers."""
        from .focus_style import focus_appearance
        appearance = focus_appearance({'focus_highlight_color': color, 'focus_highlight_width': line_width})
        color = appearance['focus_highlight_color']
        rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        targets_by_id = {str(target.get("id")): target for target in targets}
        timeline = focus_timeline(cues, duration)
        from ..core.cue_timeline import focus_events_from_cues

        merged = focus_events_from_cues(timeline)
        layers = []
        expanded = []
        for cue in merged:
            selected = [targets_by_id[target_id] for target_id in cue.get("target_ids", [])
                        if target_id in targets_by_id]
            if style == "spotlight" and len(selected) > 1:
                left = min(float(target.get("x", 0)) for target in selected)
                top = min(float(target.get("y", 0)) for target in selected)
                right = max(float(target.get("x", 0)) + float(target.get("width", 0)) for target in selected)
                bottom = max(float(target.get("y", 0)) + float(target.get("height", 0)) for target in selected)
                expanded.append((cue, {"x": left, "y": top, "width": right - left, "height": bottom - top}))
            else:
                expanded.extend((cue, target) for target in selected)

        for cue, target in expanded:
            padding = 0 if style == "underline" else 10
            x = image_left + round(float(target.get("x", 0)) * image_width) - padding
            y = image_top + round(float(target.get("y", 0)) * image_height) - padding
            width = round(float(target.get("width", 0)) * image_width) + padding * 2
            height = round(float(target.get("height", 0)) * image_height) + padding * 2
            x = max(image_left, min(image_left + image_width - 2, x))
            y = max(image_top, min(image_top + image_height - 2, y))
            width = max(2, min(image_left + image_width - x, width))
            height = max(2, min(image_top + image_height - y, height))
            start = max(0.0, float(cue["start"]))
            cue_duration = float(cue["end"]) - start

            def focus_clip(size, color, opacity, position):
                return (
                    ColorClip(size=size, color=color)
                    .with_opacity(opacity)
                    .with_start(start)
                    .with_duration(cue_duration)
                    .with_position(position)
                )

            border = max(1, round(appearance["focus_highlight_width"] * image_height / 1080))
            if style == "spotlight":
                shade = (8, 15, 28)
                regions = [
                    ((image_width, max(0, y - image_top)), (image_left, image_top)),
                    (
                        (image_width, max(0, image_top + image_height - (y + height))),
                        (image_left, y + height),
                    ),
                    ((max(0, x - image_left), height), (image_left, y)),
                    (
                        (max(0, image_left + image_width - (x + width)), height),
                        (x + width, y),
                    ),
                ]
                layers.extend(
                    focus_clip(size, shade, 0.48, position)
                    for size, position in regions
                    if size[0] > 0 and size[1] > 0
                )
                layers.append(focus_clip(
                    (width, border), (255, 255, 255), 0.88,
                    (x, y + height - border),
                ))
            elif style == "underline":
                thickness = min(height, border)
                layers.append(focus_clip(
                    (width, thickness), rgb, 1.0,
                    (x, y + height - thickness),
                ))
            else:
                layers.append(focus_clip((width, height), (255, 190, 30), 0.13, (x, y)))
                layers.append(focus_clip((width, border), rgb, 0.92, (x, y)))
                layers.append(focus_clip((width, border), rgb, 0.92, (x, y + height - border)))
                layers.append(focus_clip((border, height), rgb, 0.92, (x, y)))
                layers.append(focus_clip((border, height), rgb, 0.92, (x + width - border, y)))
        return layers

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
                page.metadata,
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
