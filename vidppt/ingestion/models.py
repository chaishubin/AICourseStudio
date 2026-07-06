"""摄取层内部模型，不与最终课程展示结构耦合。"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SourceSection:
    title: str
    level: int = 1
    paragraphs: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs).strip()


@dataclass
class SourceDocument:
    title: str
    source_path: Path
    sections: list[SourceSection] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        chunks = []
        for section in self.sections:
            chunks.append(f"# {section.title}\n{section.text}".strip())
        return "\n\n".join(chunks)
