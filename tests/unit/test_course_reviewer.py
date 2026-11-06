import json

import pytest

from vidppt.engines.llm.deepseek_llm_engine import DeepSeekLLMEngine
from vidppt.review.course_reviewer import CourseReviewError, CourseReviewer


class FakeEngine:
    def summarize(self, prompt, **kwargs):
        payload = json.loads(prompt)
        assert payload["review_mode"] == "full"
        assert [page["script"] for page in payload["pages"]] == ["第一部分。", "应用环节。"]
        assert "replacement_script" in kwargs["system_prompt"]
        assert kwargs["response_format"] == {"type": "json_object"}
        return json.dumps({
            "review_completed": True,
            "reviewed_pages": [1, 2],
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
    assert result["review_completed"] is True
    assert result["reviewed_pages"] == [1, 2]
    assert result["findings"][0]["replacement_script"].startswith("理解了")


def test_course_reviewer_rejects_unknown_provider():
    with pytest.raises(ValueError, match="openai 或 deepseek"):
        CourseReviewer(provider="unknown", engine=FakeEngine())


@pytest.mark.parametrize("response", [
    # The screenshot's response must never be accepted as a completed review.
    {"status": "warning", "summary": "未提供课程页面内容，无法进行实际质检。", "findings": []},
    {"review_completed": False, "reviewed_pages": [], "status": "warning", "findings": []},
    {"review_completed": "true", "reviewed_pages": [1, 2], "status": "passed", "findings": []},
    {"review_completed": True, "reviewed_pages": [1], "status": "passed", "findings": []},
    {"review_completed": True, "reviewed_pages": [1, 3], "status": "passed", "findings": []},
    {"review_completed": True, "reviewed_pages": [1, 1, 2], "status": "passed", "findings": []},
    {"review_completed": True, "reviewed_pages": [True, 2], "status": "passed", "findings": []},
    {"review_completed": True, "reviewed_pages": [1, 2], "status": "warning", "findings": []},
    {"review_completed": True, "reviewed_pages": [1, 2], "status": "passed", "findings": {}},
    {"review_completed": True, "reviewed_pages": [1, 2], "status": "warning", "findings": ["invalid"]},
    {"review_completed": True, "reviewed_pages": [1, 2], "status": "warning",
     "findings": [{"page_number": 3, "message": "不属于本次提交的页面"}]},
])
def test_course_reviewer_rejects_unverified_or_inconsistent_results(response):
    class ResponseEngine:
        def summarize(self, prompt, **kwargs):
            return json.dumps(response, ensure_ascii=False)

    reviewer = CourseReviewer(engine=ResponseEngine())
    with pytest.raises(CourseReviewError):
        reviewer.review({"pages": [
            {"page_number": 1, "script": "第一部分。"},
            {"page_number": 2, "script": "应用环节。"},
        ]}, mode="full")


def test_course_reviewer_accepts_verified_pass_with_no_findings():
    class PassedEngine:
        def summarize(self, prompt, **kwargs):
            payload = json.loads(prompt)
            numbers = [page["page_number"] for page in payload["pages"]]
            assert len(numbers) <= 5
            return json.dumps({
                "review_completed": True, "reviewed_pages": list(reversed(numbers)),
                "status": "passed", "summary": "讲稿连贯。", "findings": [],
            })

    reviewer = CourseReviewer(engine=PassedEngine())
    result = reviewer.review({"pages": [
        {"page_number": number, "script": f"第 {number} 页讲稿。"}
        for number in range(1, 10)
    ]}, mode="sample")
    assert result["status"] == "passed"
    assert result["review_completed"] is True
    assert 1 in result["reviewed_pages"] and 9 in result["reviewed_pages"]


def test_course_reviewer_does_not_send_empty_scripts():
    class NeverCalledEngine:
        def summarize(self, *args, **kwargs):
            pytest.fail("没有讲稿时不应调用模型")

    reviewer = CourseReviewer(engine=NeverCalledEngine())
    with pytest.raises(ValueError, match="没有可审查"):
        reviewer.review({"pages": [{"script": None}, {"script": "  "}]})


def test_deepseek_engine_uses_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://gateway.example/v1")
    monkeypatch.setenv("DEEPSEEK_REVIEW_MODEL", "deepseek-v4-pro")

    engine = DeepSeekLLMEngine()

    assert engine.api_key == "test-key"
    assert engine.api_url == "https://gateway.example/v1/chat/completions"
    assert engine.model == "deepseek-v4-pro"
