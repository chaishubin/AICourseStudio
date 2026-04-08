"""
VidPPT - 文档到视频转换工具

将 PPT、PDF、Word 等文档转换为配音讲解视频
"""

__version__ = "0.2.0"

from .core.interfaces import DocumentProcessor, TTSEngine, OCREngine, ImageConverter
from .core.models import DocumentContent, PageContent, ProcessConfig
from .core.registry import ProcessorRegistry, register_processor
from .pipeline import Pipeline

__all__ = [
    "DocumentProcessor",
    "TTSEngine",
    "OCREngine",
    "ImageConverter",
    "DocumentContent",
    "PageContent",
    "ProcessConfig",
    "ProcessorRegistry",
    "register_processor",
    "Pipeline",
]
