"""
视频合成工具
"""
import sys
from pathlib import Path

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
                print(
                    f"  [跳过] 第 {page.page_number} 页：缺少页面图像",
                    file=sys.stderr,
                )
                continue
            
            if not page.audio or not page.audio.exists():
                print(
                    f"  [跳过] 第 {page.page_number} 页：缺少音频",
                    file=sys.stderr,
                )
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
            print(f"  第 {page.page_number} 页 片段时长: {duration:.1f}s")
        
        if not clips:
            print("[错误] 没有可合成的片段", file=sys.stderr)
            return
        
        print(f"\n合并 {len(clips)} 个片段，输出 -> {output_path}")
        final = concatenate_videoclips(clips, method="compose")
        
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
        print(f"视频生成完成：{output_path}  ({size_mb:.1f} MB)")
