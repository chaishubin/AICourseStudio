"""
视频合成工具

功能：
1. 遍历目录列表，每个目录包含背景图、文本（可选）、区域图片（可选）
2. 文本 -> TTS -> 音频 -> 人脸视频（通过API）
3. 背景图生成视频，叠加圆形遮罩的人脸视频
4. 所有目录的视频拼接，添加转场效果

目录结构示例：
input_dirs/
├── dir1/
│   ├── background.jpg (必须)
│   ├── text.txt (可选)
│   └── region.png (可选)
├── dir2/
│   └── ...
"""

import os
import asyncio
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass

import numpy as np
from PIL import Image

# 视频处理库
from moviepy import (
    VideoClip,
    ImageClip,
    CompositeVideoClip,
    AudioFileClip,
    concatenate_videoclips,
    ColorClip,
    VideoFileClip,
)
from moviepy.video.fx import FadeIn, FadeOut

# TTS 库
try:
    import edge_tts
except ImportError:
    print("请安装 edge-tts: pip install edge-tts")

# Provider 模块
from .providers import get_provider, list_providers, BaseFaceVideoProvider
from .tts_processors import ProcessorFactory, CompositeProcessor


@dataclass
class SegmentConfig:
    """每个视频段的配置"""

    background_image: Path  # 背景图片路径
    text_file: Optional[Path]  # 文本文件路径（可选）
    region_image: Optional[Path]  # 区域图片路径（可选）
    output_video: Path  # 输出视频路径


@dataclass
class VideoConfig:
    """全局视频配置"""

    width: int = 1920  # 视频宽度
    height: int = 1080  # 视频高度
    fps: int = 30  # 帧率
    face_position: str = (
        "bottom-right"  # 人脸位置：top-left/top-right/bottom-left/bottom-right
    )
    face_margin: int = 50  # 人脸距离边缘的边距（像素）
    face_size: int = 300  # 人脸圆形直径
    transition_duration: float = 1.0  # 转场时长（秒）
    tts_voice: str = "zh-CN-XiaoxiaoNeural"  # TTS 语音

    def get_face_position(self, face_width: int, face_height: int) -> Tuple[int, int]:
        """
        根据视频尺寸和人脸尺寸自动计算位置

        Args:
            face_width: 人脸视频宽度
            face_height: 人脸视频高度

        Returns:
            (x, y) 位置坐标
        """
        margin = self.face_margin
        positions = {
            "top-left": (margin, margin),
            "top-right": (self.width - face_width - margin, margin),
            "bottom-left": (margin, self.height - face_height - margin),
            "bottom-right": (
                self.width - face_width - margin,
                self.height - face_height - margin,
            ),
        }
        return positions.get(self.face_position, positions["bottom-right"])


class FaceVideoGenerator:
    """
    人脸视频生成器

    封装 Provider 模块，提供统一的接口
    """

    def __init__(
        self,
        provider_name: str,
        face_image_path: Path,
        provider_config: Dict[str, Any] = None,
    ):
        """
        初始化人脸视频生成器

        Args:
            provider_name: Provider 名称（如 "sadtalker", "heygen"）
            face_image_path: 人脸图像路径
            provider_config: Provider 配置参数
        """
        self.face_image_path = Path(face_image_path)
        self.provider = get_provider(provider_name, provider_config or {})

        # 验证人脸图像
        if not self.face_image_path.exists():
            raise FileNotFoundError(f"人脸图像不存在: {self.face_image_path}")

        print(f"[FaceVideo] 使用 Provider: {provider_name}")
        print(f"[FaceVideo] 可用 Provider: {list(list_providers().keys())}")

    def generate(self, audio_path: Path, output_path: Path, text: str = None) -> Path:
        """
        生成人脸视频

        Args:
            audio_path: 音频文件路径
            output_path: 输出视频路径
            text: 文本内容（部分 Provider 需要）

        Returns:
            生成的视频路径
        """
        result = self.provider.generate(
            face_image=self.face_image_path,
            text=text or "",
            output_path=output_path,
            audio_path=str(audio_path),
        )
        return result.video_path


class TTSGenerator:
    """文本转语音生成器

    支持策略模式处理多音字和停顿：

    示例：
        # 使用默认策略
        tts = TTSGenerator()

        # 组合多个策略
        tts = TTSGenerator(processor=CompositeProcessor()
            .add_processor(ProcessorFactory.get("jieba_segment"))
            .add_processor(ProcessorFactory.get("pinyin_annotation")))

        # 单一策略
        tts = TTSGenerator(processor_name="explicit_pause")
    """

    def __init__(
        self,
        voice: str = "zh-CN-XiaoxiaoNeural",
        processor_name: str = None,
        processor: CompositeProcessor = None,
    ):
        """
        Args:
            voice: 语音类型，可选：
                - zh-CN-XiaoxiaoNeural (女声，自然)
                - zh-CN-YunxiNeural (男声，自然)
                - zh-CN-YunyangNeural (男声，新闻播报风格)
            processor_name: 处理器名称（单一策略）
            processor: 处理器实例（组合策略）
        """
        self.voice = voice

        # 初始化处理器
        if processor is not None:
            self.processor = processor
        elif processor_name is not None:
            self.processor = ProcessorFactory.get(processor_name)
        else:
            # 默认：组合显式停顿和拼音标注
            self.processor = CompositeProcessor()
            self.processor.add_processor(ProcessorFactory.get("explicit_pause"))
            self.processor.add_processor(ProcessorFactory.get("pinyin_annotation"))

    async def generate_async(self, text: str, output_path: Path) -> Path:
        """异步生成语音"""
        processed_text = self.processor.process(text)
        communicate = edge_tts.Communicate(processed_text, self.voice)
        await communicate.save(str(output_path))
        return output_path

    def generate(self, text: str, output_path: Path) -> Path:
        """同步接口：文本转语音"""
        return asyncio.run(self.generate_async(text, output_path))


def create_circular_mask(height: int, width: int, radius: int) -> np.ndarray:
    """
    创建圆形遮罩

    Args:
        height: 遮罩高度
        width: 遮罩宽度
        radius: 圆形半径

    Returns:
        遮罩数组，圆形区域为 1.0，其他为 0.0
    """
    y, x = np.ogrid[:height, :width]
    center_x, center_y = width // 2, height // 2
    dist = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
    mask = (dist <= radius).astype(float)
    return mask


def create_circular_video_clip(video_path: Path, target_size: int) -> VideoClip:
    """
    创建带圆形遮罩的视频片段

    只保留圆形区域的人脸，其他区域透明

    Args:
        video_path: 视频路径
        target_size: 目标尺寸（直径）

    Returns:
        带透明圆形遮罩的视频片段
    """
    video = VideoFileClip(str(video_path))

    # 缩放到目标尺寸（保持比例，取较小的缩放比例）
    w, h = video.size
    scale = target_size / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    video = video.resized((new_w, new_h))

    def apply_circular_mask(get_frame, t):
        """对每一帧应用圆形遮罩"""
        frame = get_frame(t)
        h, w = frame.shape[:2]

        # 创建圆形遮罩，半径为目标尺寸的一半
        radius = min(w, h) // 2
        mask = create_circular_mask(h, w, radius)

        # 添加 alpha 通道
        if frame.shape[2] == 3:
            frame_rgba = np.dstack([frame, np.full((h, w), 255, dtype=np.uint8)])
        else:
            frame_rgba = frame.copy()

        # 应用遮罩到 alpha 通道：圆形区域不透明，其他区域透明
        frame_rgba[:, :, 3] = (mask * 255).astype(np.uint8)

        return frame_rgba

    masked_video = video.transform(apply_circular_mask, apply_to=["mask"])
    return masked_video


def create_image_clip(
    image_path: Path,
    duration: float,
    fps: int = 30,
    size: Tuple[int, int] = (1920, 1080),
) -> ImageClip:
    """
    创建静态图片视频片段

    Args:
        image_path: 图片路径
        duration: 视频时长（秒）
        fps: 帧率
        size: 视频尺寸 (width, height)

    Returns:
        静态图片视频片段
    """
    clip = ImageClip(str(image_path), duration=duration)
    clip = clip.resized(size)
    return clip


def add_transition(clips: List[VideoClip], duration: float = 1.0) -> VideoClip:
    """
    为视频列表添加转场效果并拼接

    Args:
        clips: 视频片段列表
        duration: 淡入淡出时长（秒）

    Returns:
        拼接后的视频
    """
    processed_clips = []

    for i, clip in enumerate(clips):
        # 第一段只添加淡出
        if i == 0:
            clip = clip.with_effects([FadeOut(duration)])
        # 最后一段只添加淡入
        elif i == len(clips) - 1:
            clip = clip.with_effects([FadeIn(duration)])
        # 中间段添加淡入和淡出
        else:
            clip = clip.with_effects([FadeIn(duration), FadeOut(duration)])

        processed_clips.append(clip)

    final_clip = concatenate_videoclips(processed_clips, method="compose")
    return final_clip


def scan_directory(directory: Path) -> SegmentConfig:
    """
    扫描目录，提取配置信息

    Args:
        directory: 目录路径

    Returns:
        段配置
    """
    # 查找背景图像（必须存在）
    bg_candidates = (
        list(directory.glob("background.*"))
        + list(directory.glob("bg.*"))
        + list(directory.glob("*.jpg"))
        + list(directory.glob("*.png"))
    )

    if not bg_candidates:
        raise FileNotFoundError(f"目录 {directory} 中未找到背景图像")

    background_image = bg_candidates[0]

    # 查找文本文件（可选）
    text_file = None
    text_candidates = list(directory.glob("*.txt"))
    if text_candidates:
        text_file = text_candidates[0]

    # 查找区域图片（可选）
    region_image = None
    region_candidates = list(directory.glob("region.*")) + list(
        directory.glob("crop.*")
    )
    if region_candidates:
        region_image = region_candidates[0]

    output_video = directory / "segment.mp4"

    return SegmentConfig(
        background_image=background_image,
        text_file=text_file,
        region_image=region_image,
        output_video=output_video,
    )


def process_segment(
    config: SegmentConfig,
    video_config: VideoConfig,
    face_generator: FaceVideoGenerator,
    tts: TTSGenerator,
    temp_dir: Path,
) -> VideoClip:
    """
    处理单个视频段

    Args:
        config: 段配置
        video_config: 视频配置
        face_generator: 人脸视频生成器
        tts: TTS 生成器
        temp_dir: 临时目录

    Returns:
        生成的视频片段
    """
    print(f"  处理背景: {config.background_image.name}")

    # Case 1: 只有背景图，没有文本
    if config.text_file is None:
        print("    无文本，生成静态背景视频")
        clip = create_image_clip(
            config.background_image,
            duration=5.0,
            fps=video_config.fps,
            size=(video_config.width, video_config.height),
        )
        return clip

    # Case 2: 有文本，需要 TTS 和人脸视频
    print(f"    文本文件: {config.text_file.name}")

    # 读取文本
    text_content = config.text_file.read_text(encoding="utf-8").strip()
    print(f"    文本内容: {text_content[:50]}...")

    # TTS 生成音频
    audio_path = temp_dir / f"{config.background_image.stem}_audio.mp3"
    print(f"    生成音频: {audio_path}")
    tts.generate(text_content, audio_path)

    # 获取音频时长
    audio_clip = AudioFileClip(str(audio_path))
    audio_duration = audio_clip.duration
    print(f"    音频时长: {audio_duration:.2f}s")

    # 生成人脸视频
    face_video_path = temp_dir / f"{config.background_image.stem}_face.mp4"
    print(f"    生成人脸视频: {face_video_path}")
    face_generator.generate(audio_path, face_video_path, text=text_content)

    # 创建背景视频（静音）
    bg_clip = create_image_clip(
        config.background_image,
        duration=audio_duration,
        fps=video_config.fps,
        size=(video_config.width, video_config.height),
    )

    # 创建圆形遮罩的人脸视频
    face_clip = create_circular_video_clip(face_video_path, video_config.face_size)

    # 自动计算人脸位置
    face_w, face_h = face_clip.size
    position = video_config.get_face_position(face_w, face_h)
    print(f"    人脸位置: {position}")
    face_clip = face_clip.with_position(position)

    # 合成视频
    final_clip = CompositeVideoClip(
        [bg_clip, face_clip], size=(video_config.width, video_config.height)
    )

    # 添加音频（来自人脸视频）
    face_video_with_audio = VideoFileClip(str(face_video_path))
    final_clip = final_clip.with_audio(face_video_with_audio.audio)

    return final_clip


def main(
    input_dirs: List[Path],
    output_path: Path,
    face_image: Path,
    provider_name: str = "sadtalker",
    provider_config: Dict[str, Any] = None,
    video_config: VideoConfig = None,
):
    """
    主函数：处理所有目录并生成最终视频

    Args:
        input_dirs: 输入目录列表
        output_path: 最终输出视频路径
        face_image: 人脸图像路径
        provider_name: 人脸视频生成 Provider 名称
        provider_config: Provider 配置参数
        video_config: 视频配置
    """
    print("=" * 60)
    print("视频合成工具")
    print("=" * 60)

    # 配置
    if video_config is None:
        video_config = VideoConfig()

    face_generator = FaceVideoGenerator(
        provider_name=provider_name,
        face_image_path=face_image,
        provider_config=provider_config,
    )
    tts = TTSGenerator(voice=video_config.tts_voice)

    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix="video_composer_"))
    print(f"临时目录: {temp_dir}")

    # 收集所有视频片段
    all_clips = []

    try:
        for i, directory in enumerate(input_dirs):
            print(f"\n[{i + 1}/{len(input_dirs)}] 处理目录: {directory.name}")

            config = scan_directory(directory)
            clip = process_segment(config, video_config, face_generator, tts, temp_dir)
            all_clips.append(clip)

        # 添加转场并拼接
        print("\n拼接视频...")
        final_video = add_transition(all_clips, video_config.transition_duration)

        # 输出最终视频
        print(f"\n写入最终视频: {output_path}")
        final_video.write_videofile(
            str(output_path), fps=video_config.fps, codec="libx264", audio_codec="aac"
        )

        print(f"\n✓ 完成！输出路径: {output_path}")

    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)
        print("清理临时目录")


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="视频合成工具")
    parser.add_argument("input_dirs", nargs="+", help="输入目录列表")
    parser.add_argument("-o", "--output", default="output.mp4", help="输出视频路径")
    parser.add_argument("-f", "--face", required=True, help="人脸图像路径")
    parser.add_argument(
        "-p",
        "--position",
        default="bottom-right",
        choices=["top-left", "top-right", "bottom-left", "bottom-right"],
        help="人脸位置",
    )
    parser.add_argument(
        "--provider",
        default="sadtalker",
        choices=["sadtalker", "heygen"],
        help="人脸视频生成 Provider",
    )
    parser.add_argument(
        "--provider-config", type=str, default=None, help="Provider 配置 (JSON 格式)"
    )
    parser.add_argument(
        "--list-providers", action="store_true", help="列出所有可用的 Provider"
    )

    args = parser.parse_args()

    # 列出 Provider
    if args.list_providers:
        print("可用的 Provider:")
        for name, desc in list_providers().items():
            print(f"  - {name}: {desc}")
        exit(0)

    # 解析 Provider 配置
    provider_config = {}
    if args.provider_config:
        provider_config = json.loads(args.provider_config)

    # 配置视频
    video_config = VideoConfig(face_position=args.position)

    input_dirs = [Path(d) for d in args.input_dirs]
    output_path = Path(args.output)
    face_image = Path(args.face)

    main(
        input_dirs=input_dirs,
        output_path=output_path,
        face_image=face_image,
        provider_name=args.provider,
        provider_config=provider_config,
        video_config=video_config,
    )
