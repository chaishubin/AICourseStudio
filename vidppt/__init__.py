"""
AI Course Studio - AI 课程生产平台

从教案（Word/PDF）或演示文稿（PPT）出发，经 AI 文档理解与知识建模，
生成课程视频（MP4）、教学幻灯片（PPTX）、互动网页（HTML）三路输出。

路线 A ——教案输入：Docling/MinerU 理解教案结构 → Course JSON → 三路渲染器
路线 B ——PPT 输入：保留原内容和样式 → Course JSON → 视频渲染器（保持原视觉设计）
"""

__version__ = "0.3.0"

from .core.interfaces import DocumentProcessor, TTSEngine, OCREngine, ImageConverter
from .core.models import DocumentContent, PageContent, ProcessConfig
from .core.course import Course, CourseSection, KnowledgePoint
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
    "Course",
    "CourseSection",
    "KnowledgePoint",
    "ProcessorRegistry",
    "register_processor",
    "Pipeline",
]
