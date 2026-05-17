"""
MiniMax LLM 真实集成测试

仅当设置了 MINIMAX_API 环境变量时才会运行。
注意：这会真实调用 MiniMax API，可能产生费用。
"""

import os
import pytest

from vidppt.engines.llm.minimax_llm_engine import MiniMaxLLMEngine

pytestmark = pytest.mark.skipif(
    not os.getenv("MINIMAX_API"),
    reason="需要设置 MINIMAX_API 环境变量才能运行真实集成测试",
)


class TestMiniMaxLLMRealAPI:
    """MiniMax LLM 真实 API 集成测试"""

    def test_summarize_real_api(self):
        """测试逐页摘要真实 API 调用"""
        import httpx

        engine = MiniMaxLLMEngine()
        # 先直接调用 API 查看完整响应
        messages = [
            {"role": "system", "content": engine.system_prompt},
            {"role": "user", "content": "• 核心要点1\n• 核心要点2\n• 核心要点3"},
        ]
        headers = {
            "Authorization": f"Bearer {engine.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": engine.model,
            "messages": messages,
            "temperature": engine.temperature,
            "max_tokens": engine.max_tokens,
        }
        with httpx.Client(timeout=engine.timeout) as client:
            response = client.post(engine.api_url, headers=headers, json=payload)
            print(f"\n状态码: {response.status_code}")
            print(f"响应体: {response.text}")
        response.raise_for_status()

        result = engine.summarize("• 核心要点1\n• 核心要点2\n• 核心要点3")
        assert result
        assert "•" not in result
        print(f"\n改写结果: {result}")

    def test_summarize_document_real_api(self):
        """测试整文档摘要真实 API 调用"""
        engine = MiniMaxLLMEngine()
        result = engine.summarize_document(["第一页：技术背景介绍", "第二页：应用场景分析"])
        assert result
        print(f"\n文档摘要: {result}")

    def test_summarize_pages_real_api(self):
        """测试逐页批量摘要真实 API 调用"""
        engine = MiniMaxLLMEngine()
        pages = [
            "• 人工智能发展趋势\n• 大语言模型的应用",
            "• 多模态融合技术\n• 强化学习新突破",
        ]
        results = engine.summarize_pages(pages)
        assert len(results) == 2
        for r in results:
            assert r
            print(f"\n逐页结果: {r}")
