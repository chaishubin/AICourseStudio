"""Course script review helpers for preview-stage quality checks."""

import json
import math
import os
import re
import time
from typing import Any

from ..engines.llm.openai_llm_engine import OpenAILLMEngine


class CourseReviewError(RuntimeError):
    """Raised when the review model cannot produce usable structured output."""


class CourseReviewer:
    PRICE_USD_PER_MILLION = {
        "gpt-5.4-mini": {"input": 0.375, "output": 2.25},
        "gpt-5.5": {"input": 2.50, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    }
    USD_TO_CNY = 7.2

    def __init__(self, model: str | None = None, engine: Any | None = None):
        self.model = (
            model
            or os.getenv("OPENAI_REVIEW_MODEL")
            or os.getenv("OPENAI_LLM_MODEL")
            or OpenAILLMEngine.DEFAULT_MODEL
        )
        self.engine = engine or OpenAILLMEngine(model=self.model)

    def review(self, preview: dict, mode: str = "sample") -> dict:
        if mode not in {"sample", "full"}:
            raise ValueError("不支持的审查模式")

        pages = self._select_pages(preview.get("pages", []), mode)
        if not pages:
            raise ValueError("没有可审查的讲稿页面")

        prompt = self._build_prompt(pages, mode)
        raw = self.engine.summarize(prompt, system_prompt=self._system_prompt(mode))
        parsed = self._parse_json(raw)
        review = self._normalize_review(parsed, pages, mode)
        review["model"] = self.model
        review["estimated_cost_cny"] = self.estimate_cost_cny(prompt, raw)
        review["created_at"] = time.time()
        return review

    def estimate_cost_cny(self, prompt: str, output: str) -> float:
        price = self.PRICE_USD_PER_MILLION.get(
            self.model,
            self.PRICE_USD_PER_MILLION.get(OpenAILLMEngine.DEFAULT_MODEL),
        )
        input_tokens = self._estimate_tokens(prompt)
        output_tokens = self._estimate_tokens(output)
        usd = (
            input_tokens / 1_000_000 * price["input"]
            + output_tokens / 1_000_000 * price["output"]
        )
        return round(usd * self.USD_TO_CNY, 4)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Conservative CJK-friendly estimate without adding tokenizer dependency.
        return max(1, math.ceil(len(text or "") * 0.9))

    def _select_pages(self, pages: list[dict], mode: str) -> list[dict]:
        normalized = [
            page for page in pages
            if str(page.get("script", "")).strip()
        ]
        if mode == "full":
            return normalized
        if len(normalized) <= 5:
            return normalized

        by_number = {
            int(page.get("page_number", index + 1)): page
            for index, page in enumerate(normalized)
        }
        selected_numbers = {
            min(by_number),
            max(by_number),
        }
        longest = sorted(
            by_number.values(),
            key=lambda page: len(str(page.get("script", ""))),
            reverse=True,
        )[:2]
        selected_numbers.update(
            int(page.get("page_number", 0)) for page in longest
        )
        unreviewed = next(
            (
                int(page.get("page_number", 0))
                for page in normalized
                if not page.get("reviewed")
            ),
            None,
        )
        if unreviewed:
            selected_numbers.add(unreviewed)
        return [
            by_number[number]
            for number in sorted(selected_numbers)
            if number in by_number
        ][:5]

    def _build_prompt(self, pages: list[dict], mode: str) -> str:
        payload = {
            "review_mode": mode,
            "requirements": [
                "检查课程结构是否连贯，是否有明显重复或断裂。",
                "检查讲稿是否自然口语化，适合 TTS 配音。",
                "检查每页讲稿是否过长、过短或缺少承上启下。",
                "只给审查建议，不要重写整套讲稿。",
            ],
            "pages": [
                {
                    "page_number": int(page.get("page_number", index + 1)),
                    "title": str(page.get("title", ""))[:120],
                    "script": str(page.get("script", "")),
                    "estimated_seconds": page.get("estimated_seconds"),
                }
                for index, page in enumerate(pages)
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _system_prompt(mode: str) -> str:
        mode_label = "全课二审" if mode == "full" else "抽检"
        return (
            f"你是在线课程内容质检专家，正在做{mode_label}。"
            "请只输出一个 JSON 对象，不要 Markdown，不要解释。"
            "JSON 字段必须包含 status、summary、findings。"
            "status 只能是 passed、warning、failed。"
            "findings 是数组，每项包含 page_number、level、category、message、suggestion；"
            "level 只能是 info、warning、critical。"
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        text = str(raw or "").strip()
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        if fence:
            text = fence.group(1)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CourseReviewError("审查模型返回的 JSON 无法解析") from exc
        if not isinstance(parsed, dict):
            raise CourseReviewError("审查模型返回格式不是对象")
        return parsed

    @staticmethod
    def _normalize_review(parsed: dict, pages: list[dict], mode: str) -> dict:
        status = str(parsed.get("status") or "warning").lower()
        if status not in {"passed", "warning", "failed"}:
            status = "warning"
        reviewed_pages = [
            int(page.get("page_number", index + 1))
            for index, page in enumerate(pages)
        ]
        findings = []
        for item in parsed.get("findings") or []:
            if not isinstance(item, dict):
                continue
            level = str(item.get("level") or "warning").lower()
            if level not in {"info", "warning", "critical"}:
                level = "warning"
            try:
                page_number = int(item.get("page_number") or 0)
            except (TypeError, ValueError):
                page_number = 0
            findings.append({
                "page_number": page_number,
                "level": level,
                "category": str(item.get("category") or "内容质量")[:40],
                "message": str(item.get("message") or "").strip()[:400],
                "suggestion": str(item.get("suggestion") or "").strip()[:400],
            })
        return {
            "status": status,
            "mode": mode,
            "summary": str(parsed.get("summary") or "").strip()[:800],
            "findings": findings,
            "reviewed_pages": reviewed_pages,
        }
