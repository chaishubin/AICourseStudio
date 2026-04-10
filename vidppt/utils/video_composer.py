"""
视频合成工具
"""

from pathlib import Path

from loguru import logger
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

from ..core.models import DocumentContent, ProcessConfig


class VideoComposer:
    """视频合成器"""

    @staticmethod
    def compose(
        content: DocumentContent,
        config: ProcessConfig,
        output_path: Path,
    ) -> None:
        """
        将页面内容合成为视频

        Args:
            content: 文档内容（包含每页的图片、音频路径）
            config: 处理配置
            output_path: 输出视频路径
        """
        clips = []

        for page in content.pages:
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
                    image_clip = (
                        ImageClip(str(page.slide_image)).with_duration(3)  # 默认显示3秒
                    )
                    clips.append(image_clip)
                continue

            # 加载音频获取时长
            audio_clip = AudioFileClip(str(page.audio))
            duration = audio_clip.duration

            # 创建图像片段
            image_clip = (
                ImageClip(str(page.slide_image))
                .with_duration(duration)
                .with_audio(audio_clip)
            )
            clips.append(image_clip)
            logger.debug(f"第 {page.page_number} 页 片段时长: {duration:.1f}s")

        if not clips:
            logger.error("没有可合成的片段")
            return

        logger.info(f"合并 {len(clips)} 个片段，输出 -> {output_path}")
        final = concatenate_videoclips(clips, method="compose")

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 输出视频
        final.write_videofile(
            str(output_path),
            fps=config.video_fps,
            codec=config.video_codec,
            audio_codec=config.audio_codec,
            logger="bar",
        )

        # 清理资源
        final.close()
        for clip in clips:
            clip.close()

        size_mb = output_path.stat().st_size / 1024 / 1024
        logger.info(f"视频生成完成：{output_path}  ({size_mb:.1f} MB)")
