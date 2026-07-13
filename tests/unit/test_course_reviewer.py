import json

import pytest

from vidppt.engines.llm.deepseek_llm_engine import DeepSeekLLMEngine
from vidppt.review.course_reviewer import CourseReviewer


class FakeEngine:
    def summarize(self, prompt, **kwargs):
        payload = json.loads(prompt)
        assert payload["review_mode"] == "full"
        assert "replacement_script" in kwargs["system_prompt"]
        assert kwargs["response_format"] == {"type": "json_object"}
        return json.dumps({
            "status": "warning",
            "summary": "第 2 页衔接生硬",
            "findings": [{
                "page_number": 2,
                "level": "warning",
                "category": "衔接",
                "message": "缺少过渡",
                "suggestion": "增加过渡句",
                "replacement_script": "理解了基本概念后，下面进入应用环节。",
            }],
        }, ensure_ascii=False)


def test_course_reviewer_supports_deepseek_and_fix_payload():
    reviewer = CourseReviewer(
        provider="deepseek",
        model="deepseek-v4-pro",
        engine=FakeEngine(),
    )

    result = reviewer.review({"pages": [
        {"page_number": 1, "script": "第一部分。"},
        {"page_number": 2, "script": "应用环节。"},
    ]}, mode="full")

    assert result["provider"] == "deepseek"
    assert result["model"] == "deepseek-v4-pro"
    assert result["findings"][0]["replacement_script"].startswith("理解了")


def test_course_reviewer_rejects_unknown_provider():
    with pytest.raises(ValueError, match="openai 或 deepseek"):
        CourseReviewer(provider="unknown", engine=FakeEngine())


def test_deepseek_engine_uses_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://gateway.example/v1")
    monkeypatch.setenv("DEEPSEEK_REVIEW_MODEL", "deepseek-v4-pro")

    engine = DeepSeekLLMEngine()

    assert engine.api_key == "test-key"
    assert engine.api_url == "https://gateway.example/v1/chat/completions"
    assert engine.model == "deepseek-v4-pro"
