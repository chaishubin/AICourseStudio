"""使用 LLM 或确定性规则把教案转换为 Course。"""

import json
import re
from typing import Optional

from ..core.course import Course, CourseSection, KnowledgePoint
from ..core.interfaces import LLMEngine
from ..ingestion.models import SourceDocument


COURSE_PROMPT = """你是一名教学设计师。请把输入教案设计成适合授课的幻灯片课程。
只输出一个合法 JSON 对象，不要使用 Markdown 代码块。结构必须为：
{
  "title": "课程标题",
  "description": "课程简介",
  "audience": "适用对象",
  "learning_objectives": ["目标1"],
  "design_spec": {
    "theme": "industry|technology|culture|nature|education|business|health|public|finance",
    "mood": "整套课件的视觉气质",
    "density": "low|medium|high",
    "visual_language": "适合课程主题的图形、线条和构图语言"
  },
  "slides": [{
    "title": "页面标题",
    "section_title": "所属章节",
    "layout": "cover|section|title_and_content|two_column|comparison|process|timeline|framework|key_point|card_grid|summary",
    "bullets": ["页面可见要点，每项简短"],
    "script": "适合口语讲解的逐页讲稿，不要机械朗读要点",
    "notes": "给讲师的补充备注",
    "image_prompt": "适合本页、无文字插图的主体和场景描述；无需插图时留空"
  }]
}
要求：
1. 先理解课程主题、受众和表达目标，再确定整套课件的设计规范；
2. 每页 3-6 个要点，讲稿必须覆盖要点，包含封面、学习目标、正文和总结页；
3. 根据内容关系选择版式：对照关系用 comparison，步骤用 process，阶段演进用 timeline，
   体系结构用 framework，单一核心结论用 key_point，图文内容用 two_column；
4. 不要让所有正文页使用同一种版式，相邻页面应有合理的视觉节奏。
"""

REFINEMENT_INSTRUCTIONS = {
    "light": "轻度精炼：尽量保留原文信息和篇幅，只修正重复、病句和不自然表达。",
    "standard": "标准精炼：保留关键知识，合并重复信息，生成清晰自然、详略适中的讲稿。",
    "strong": "高度精炼：只保留核心结论、关键依据和必要过渡，讲稿简洁有力。",
}


class CourseBuilder:
    def __init__(
        self,
        llm_engine: Optional[LLMEngine] = None,
        refinement_level: str = "standard",
    ):
        self.llm_engine = llm_engine
        if refinement_level not in REFINEMENT_INSTRUCTIONS:
            raise ValueError(f"不支持的精炼程度: {refinement_level}")
        self.refinement_level = refinement_level

    def build(self, document: SourceDocument) -> Course:
        if self.llm_engine:
            raw = self.llm_engine.summarize(
                document.full_text,
                system_prompt=(
                    COURSE_PROMPT
                    + "\n"
                    + REFINEMENT_INSTRUCTIONS[self.refinement_level]
                ),
                temperature=0.3,
            )
            return self._from_llm_json(raw, document)
        return self._build_draft(document)

    def _from_llm_json(self, raw: str, document: SourceDocument) -> Course:
        payload = json.loads(_extract_json(raw))
        slides = payload.get("slides")
        if not isinstance(slides, list) or not slides:
            raise ValueError("AI 返回的课程 JSON 缺少非空 slides")

        sections = []
        for index, slide in enumerate(slides, 1):
            title = str(slide.get("title", "")).strip()
            if not title:
                raise ValueError(f"AI 返回的第 {index} 页缺少标题")
            bullets = [str(item).strip() for item in slide.get("bullets", []) if str(item).strip()]
            sections.append(
                CourseSection(
                    id=f"slide-{index}",
                    title=title,
                    script=str(slide.get("script", "")).strip(),
                    notes=str(slide.get("notes", "")).strip(),
                    image_prompt=str(slide.get("image_prompt", "")).strip() or None,
                    bullets=bullets,
                    layout=str(slide.get("layout", "title_and_content")),
                    section_title=str(slide.get("section_title", "")).strip(),
                    knowledge_points=[
                        KnowledgePoint(
                            id=f"slide-{index}-point-{point_index}",
                            title=bullet,
                            order=point_index,
                        )
                        for point_index, bullet in enumerate(bullets, 1)
                    ],
                )
            )

        return Course(
            title=str(payload.get("title") or document.title),
            description=str(payload.get("description", "")),
            audience=str(payload.get("audience", "")),
            learning_objectives=[
                str(item).strip()
                for item in payload.get("learning_objectives", [])
                if str(item).strip()
            ],
            sections=sections,
            source_type="lesson_plan",
            source_path=document.source_path,
            metadata={
                "generator": "llm",
                "design_spec": _normalize_design_spec(payload.get("design_spec")),
            },
        )

    def _build_draft(self, document: SourceDocument) -> Course:
        """无 API 时生成可编辑草稿，保证摄取与渲染链路可离线验证。"""
        slides = [
            CourseSection(
                id="slide-1",
                title=document.title,
                layout="cover",
                script=f"大家好，欢迎学习《{document.title}》。",
                notes="课程封面",
            )
        ]
        for source in document.sections:
            bullets = _paragraphs_to_bullets(source.paragraphs)
            if not bullets:
                continue
            index = len(slides) + 1
            slides.append(
                CourseSection(
                    id=f"slide-{index}",
                    title=source.title,
                    section_title=source.title,
                    bullets=bullets,
                    script="。".join(bullet.rstrip("。") for bullet in bullets) + "。",
                    notes=source.text,
                    knowledge_points=[
                        KnowledgePoint(
                            id=f"slide-{index}-point-{i}",
                            title=bullet,
                            order=i,
                        )
                        for i, bullet in enumerate(bullets, 1)
                    ],
                )
            )
        return Course(
            title=document.title,
            sections=slides,
            source_type="lesson_plan",
            source_path=document.source_path,
            metadata={"generator": "draft"},
        )


def _extract_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI 返回内容中没有 JSON 对象")
    return text[start : end + 1]


def _normalize_design_spec(value) -> dict:
    allowed_themes = {
        "industry", "technology", "culture", "nature", "education",
        "business", "health", "public", "finance",
    }
    allowed_densities = {"low", "medium", "high"}
    value = value if isinstance(value, dict) else {}
    theme = str(value.get("theme", "")).strip().lower()
    density = str(value.get("density", "medium")).strip().lower()
    return {
        "theme": theme if theme in allowed_themes else "auto",
        "mood": str(value.get("mood", "")).strip()[:100],
        "density": density if density in allowed_densities else "medium",
        "visual_language": str(value.get("visual_language", "")).strip()[:200],
    }


def _paragraphs_to_bullets(paragraphs: list[str], limit: int = 6) -> list[str]:
    bullets = []
    for paragraph in paragraphs:
        for part in re.split(r"[；;]\s*|\n+", paragraph):
            item = part.strip().lstrip("•·-— ")
            if item:
                bullets.append(item[:100])
            if len(bullets) >= limit:
                return bullets
    return bullets
