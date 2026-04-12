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

    # OCR 配置
    ocr_engine: str = "builtin"  # builtin, tesseract, api

    # 图像转换配置
    image_converter: str = "builtin"  # builtin, api

    # 视频配置
    video_fps: int = 24
    video_codec: str = "libx264"
    audio_codec: str = "aac"

    def __post_init__(self):
        self.input_path = Path(self.input_path)
        self.output_dir = Path(self.output_dir)
