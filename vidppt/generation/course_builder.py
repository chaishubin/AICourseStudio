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
    "focus_cues": [{"text": "讲稿中的连续讲解片段", "anchor": "title|bullet-1|bullet-2", "action": "switch|continue|clear", "teaching_stage": "引入|解释|举例|比较|推导|总结|过渡", "knowledge_point_id": "本页要点ID或空"}],
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
5. focus_cues 必须覆盖整页讲稿，anchor 必须引用本页稳定内容锚点：title 或 bullet-N；
   即使讲稿是概括、过渡或举例，也要选择最相关锚点，不要自行复述可见文字或输出空目标。
6. 每个 focus_cue 同时标注教学阶段、对应知识点序号（bullet-N）和焦点动作；同一对象延续时用 continue，转向对象用 switch，无可定位内容时用 clear。
"""

SUBTITLE_SAFE_AREA_PROMPT = """视频会烧录字幕，PPT 设计必须预留字幕安全区：
1. 不要把正文、页脚之外的说明、图表关键标签或重要插图主体放在画面底部约 15% 区域；
2. 正文页优先采用上中部信息布局，底部仅保留留白、弱装饰或不影响理解的背景元素；
3. 若页面信息较多，应减少可见要点数量或拆页，避免让字幕遮盖课程内容。
"""

REFINEMENT_INSTRUCTIONS = {
    "light": "轻度精炼：尽量保留原文信息和篇幅，只修正重复、病句和不自然表达。",
    "standard": "标准精炼：保留关键知识，合并重复信息，生成清晰自然、详略适中的讲稿。",
    "strong": "高度精炼：只保留核心结论、关键依据和必要过渡，讲稿简洁有力。",
}

NARRATION_STYLE_INSTRUCTIONS = {
    "faithful": "原稿保真：保持原文表达顺序，只做必要的口语化整理，不新增例子。",
    "lecture": (
        "教师讲授：不要逐句复述原文或机械朗读页面要点。先讲清结论，再解释原因、关系或方法；"
        "可用一个贴近原文的解释性例子帮助理解，并用自然过渡衔接前后页。"
    ),
    "plain": "通俗解释：用容易理解的语言解释专业内容，必要时使用类比，但保留专业术语和准确含义。",
    "case": "案例引导：优先用问题或简短情境引出知识点，再回到原文结论；不得虚构具体数据、政策或事实。",
    "micro": "简洁微课：开门见山说明本页核心结论，只保留必要解释和过渡，避免寒暄与重复总结。",
}


class CourseBuilder:
    def __init__(
        self,
        llm_engine: Optional[LLMEngine] = None,
        refinement_level: str = "standard",
        narration_style: str = "lecture",
        target_duration_minutes: int = 0,
    ):
        self.llm_engine = llm_engine
        if refinement_level not in REFINEMENT_INSTRUCTIONS:
            raise ValueError(f"不支持的精炼程度: {refinement_level}")
        self.refinement_level = refinement_level
        if narration_style not in NARRATION_STYLE_INSTRUCTIONS:
            raise ValueError(f"不支持的讲解风格: {narration_style}")
        if target_duration_minutes < 0 or target_duration_minutes > 180:
            raise ValueError("目标时长必须在 0 到 180 分钟之间")
        self.narration_style = narration_style
        self.target_duration_minutes = target_duration_minutes

    def build(
        self,
        document: SourceDocument,
        *,
        reserve_subtitle_area: bool = False,
    ) -> Course:
        if self.llm_engine:
            prompt_parts = [
                COURSE_PROMPT,
                REFINEMENT_INSTRUCTIONS[self.refinement_level],
                NARRATION_STYLE_INSTRUCTIONS[self.narration_style],
                (
                    "口播稿负责解释页面要点之间的关系，不要逐项念标题和项目符号。"
                    "专业术语、法规条款、公式、数字和结论必须忠于原文；"
                    "不得增加原文无依据的事实。每页只讲本页内容，避免与相邻页重复。"
                ),
            ]
            if self.target_duration_minutes:
                minimum = self.target_duration_minutes * 220
                maximum = self.target_duration_minutes * 260
                prompt_parts.append(
                    f"整套课程口播目标约 {self.target_duration_minutes} 分钟，"
                    f"全部页面讲稿合计控制在约 {minimum}-{maximum} 个汉字；"
                    "按各页知识量合理分配，不要平均硬凑字数。"
                )
            if reserve_subtitle_area:
                prompt_parts.append(SUBTITLE_SAFE_AREA_PROMPT)
            raw = self.llm_engine.summarize(
                document.full_text,
                system_prompt="\n".join(prompt_parts),
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
                    metadata={
                        "focus_cues": _normalize_llm_focus_cues(
                            slide.get("focus_cues"), title, bullets
                        ),
                    },
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
                    script=_build_offline_narration(source.title, bullets),
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


def _build_offline_narration(title: str, bullets: list[str]) -> str:
    """无模型时生成可听的讲授草稿，避免把页面项目符号直接拼成逐字稿。"""
    if not bullets:
        return f"这一部分我们重点理解{title}。"
    lead = f"这一部分我们来理解{title}。"
    if len(bullets) == 1:
        return f"{lead}核心是{bullets[0].rstrip('。')}。理解这一点，有助于把握本节的主要内容。"
    middle = "；".join(
        f"{label}{bullet.rstrip('。')}"
        for label, bullet in zip(
            ("首先，", "其次，", "接着，", "同时，", "最后，", "还需要注意，"),
            bullets,
        )
    )
    return f"{lead}{middle}。这些内容相互关联，需要结合起来理解。"


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


def _normalize_llm_focus_cues(
    value, title: str, bullets: list[str]
) -> list[dict]:
    if not isinstance(value, list):
        return []
    cues = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        anchor = str(item.get("anchor") or "").strip().lower()
        target_text = title if anchor == "title" else ""
        match = re.fullmatch(r"bullet-(\d+)", anchor)
        if match:
            index = int(match.group(1)) - 1
            target_text = bullets[index] if 0 <= index < len(bullets) else ""
        if not target_text:
            target_text = str(
                item.get("target_text") or item.get("target") or ""
            ).strip()
        if text and target_text:
            cue = {
                "text": text,
                "anchor": anchor or "legacy",
                "target_text": target_text,
            }
            action = str(item.get("action") or "").strip().lower()
            stage = str(item.get("teaching_stage") or item.get("stage") or "").strip()
            point_id = str(item.get("knowledge_point_id") or "").strip()
            if action:
                cue["action"] = action
            if stage:
                cue["teaching_stage"] = stage
            if point_id:
                cue["knowledge_point_id"] = point_id
            cues.append(cue)
    return cues


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
