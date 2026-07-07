"""
核心数据模型
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PageContent:
    """单页内容"""

    page_number: int
    text: str = ""
    images: list[Path] = field(default_factory=list)
    slide_image: Optional[Path] = None
    audio: Optional[Path] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class DocumentContent:
    """文档内容"""

    pages: list[PageContent]
    metadata: dict = field(default_factory=dict)

    @property
    def total_pages(self) -> int:
        return len(self.pages)


@dataclass
class ProcessConfig:
    """处理配置"""

    # 输入输出
    input_path: Path
    output_dir: Path

    # 功能开关
    enable_tts: bool = True
    enable_video: bool = True
    save_intermediate: bool = True  # 是否保存中间文件
    skip_existing: bool = True  # 输出文件已存在时跳过处理

    # TTS 配置
    tts_engine: str = "edge-tts"
    tts_voice: Optional[str] = (
        "zh-CN-XiaoxiaoNeural"  # 仅用于 edge-tts；minimax 时此字段为 None，voice 通过 tts_options["voice_id"] 配置
    )
    tts_rate: str = "+0%"
    tts_options: dict = field(
        default_factory=dict
    )  # TTS 引擎特定选项（minimax: voice_id, api_key, model 等）

    # 缓存配置
    enable_audio_cache: bool = True  # 是否启用音频缓存
    audio_cache_dir: Optional[Path] = None  # 音频缓存目录，默认为 ~/.cache/vidppt/audio
    audio_cache_expiry_days: int = 30  # 音频缓存过期天数

    # 渲染配置
    render_engine: str = "spire"  # "spire" 或 "libreoffice"

    # OCR 配置
    ocr_engine: str = "builtin"  # builtin, tesseract, api

    # LLM 配置
    llm_enabled: bool = False
    llm_engine: str = "qwen"
    llm_mode: str = "per-page"  # "per-page" 或 "whole-document"
    llm_options: dict = field(default_factory=dict)

    # 图像转换配置
    image_converter: str = "builtin"  # builtin, api

    # 视频配置
    video_width: int = 1920
    video_height: int = 1080
    video_fps: int = 24
    video_codec: str = "libx264"
    video_preset: str = "veryfast"
    video_crf: int = 21
    video_pixel_format: str = "yuv420p"
    video_gop_seconds: int = 2
    video_profile: str = "high"
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"
    audio_sample_rate: int = 48000
    audio_channels: int = 1
    audio_loudness_lufs: float = -16.0
    burn_subtitles: bool = True
    subtitle_x: int = 0
    subtitle_y: int = 976
    subtitle_width: int = 1920
    subtitle_height: int = 50
    subtitle_font_size: int = 50
    subtitle_font_name: str = "Noto Sans CJK SC"
    subtitle_color: str = "#FFFFFF"
    subtitle_background_color: str = "#333333"
    subtitle_background_opacity: float = 0.45
    subtitle_outline_width: float = 0.0
    subtitle_outline_color: str = "#000000"

    # 数字人配置（可选）
    enable_avatar: bool = False  # 是否启用数字人叠加
    avatar_face_image: Optional[Path] = None  # 人脸图片路径（启用数字人时必填）
    avatar_provider: str = "sadtalker"  # 数字人后端：sadtalker / heygen
    avatar_provider_config: dict = field(default_factory=dict)  # Provider 专属配置
    avatar_face_position: str = (
        "bottom-right"  # 人脸位置：top-left/top-right/bottom-left/bottom-right
    )
    avatar_face_size: int = 300  # 圆形人脸直径（像素）
    avatar_face_margin: int = 50  # 人脸距边缘边距（像素）
    avatar_transition_duration: float = 1.0  # 转场淡入淡出时长（秒）
    avatar_video_width: int = 1920  # 输出视频宽度
    avatar_video_height: int = 1080  # 输出视频高度

    def __post_init__(self):
        self.input_path = Path(self.input_path)
        self.output_dir = Path(self.output_dir)
        if self.avatar_face_image is not None:
            self.avatar_face_image = Path(self.avatar_face_image)
