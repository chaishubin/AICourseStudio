"""
Course 知识模型 —— AI Course Studio 的核心数据结构

描述一门课程的结构化知识，同时服务于两条输入路线和三个输出渲染器。

路线 A（教案输入）：
  Word/PDF → Docling/MinerU 文档理解 → Course → Renderers

路线 B（PPT 直接输入）：
  PPT → PPT Parser（保留内容+样式截图）→ Course → Video Renderer

渲染器共享同一个 Course 数据：
  - PPTX Renderer  → 可编辑的教学幻灯片
  - Video Renderer → 配音讲解视频（现有 pipeline 能力）
  - Web Renderer   → 交互式 HTML 课程
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class KnowledgePoint:
    """单个知识点"""

    id: str
    title: str
    content: str = ""
    order: int = 0


@dataclass
class CourseSection:
    """课程章节 / 页面

    路线 A 中对应教案的一个「节」；
    路线 B 中对应 PPT 的一「页」。
    """

    id: str
    title: str = ""
    script: str = ""  # 讲解脚本 / 逐字稿
    knowledge_points: list[KnowledgePoint] = field(default_factory=list)

    # 视觉素材
    slide_image: Optional[Path] = None  # 幻灯片截图（路线 B 保留原设计）
    audio: Optional[Path] = None  # 配音音频
    duration: float = 0.0  # 预估时长（秒）

    metadata: dict = field(default_factory=dict)


@dataclass
class Course:
    """课程知识模型 —— 整个平台的核心数据

    从输入文档（教案 / PPT）中提取的结构化知识表示，
    被三个渲染器消费以生成不同格式的课程产出。
    """

    title: str = ""
    description: str = ""
    sections: list[CourseSection] = field(default_factory=list)

    # 来源信息
    source_type: str = ""  # "lesson_plan" | "presentation"
    source_path: Optional[Path] = None

    metadata: dict = field(default_factory=dict)

    @property
    def total_sections(self) -> int:
        return len(self.sections)

    def add_section(self, section: CourseSection) -> None:
        self.sections.append(section)

    def to_dict(self) -> dict:
        """序列化为可 JSON 序列化的字典"""
        return {
            "title": self.title,
            "description": self.description,
            "sections": [
                {
                    "id": s.id,
                    "title": s.title,
                    "script": s.script,
                    "knowledge_points": [
                        {"id": kp.id, "title": kp.title, "content": kp.content, "order": kp.order}
                        for kp in s.knowledge_points
                    ],
                    "slide_image": str(s.slide_image) if s.slide_image else None,
                    "audio": str(s.audio) if s.audio else None,
                    "duration": s.duration,
                    "metadata": s.metadata,
                }
                for s in self.sections
            ],
            "source_type": self.source_type,
            "source_path": str(self.source_path) if self.source_path else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Course":
        """从字典反序列化"""
        sections = []
        for s in data.get("sections", []):
            kps = [
                KnowledgePoint(
                    id=kp["id"],
                    title=kp["title"],
                    content=kp.get("content", ""),
                    order=kp.get("order", 0),
                )
                for kp in s.get("knowledge_points", [])
            ]
            section = CourseSection(
                id=s["id"],
                title=s.get("title", ""),
                script=s.get("script", ""),
                knowledge_points=kps,
                slide_image=Path(s["slide_image"]) if s.get("slide_image") else None,
                audio=Path(s["audio"]) if s.get("audio") else None,
                duration=s.get("duration", 0.0),
                metadata=s.get("metadata", {}),
            )
            sections.append(section)

        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            sections=sections,
            source_type=data.get("source_type", ""),
            source_path=Path(data["source_path"]) if data.get("source_path") else None,
            metadata=data.get("metadata", {}),
        )
