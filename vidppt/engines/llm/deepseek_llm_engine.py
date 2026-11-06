"""DeepSeek LLM engine using its OpenAI-compatible Chat Completions API."""

import os
from typing import Optional

from .openai_llm_engine import OpenAILLMEngine


class DeepSeekLLMEngine(OpenAILLMEngine):
    DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
    DEFAULT_MODEL = "deepseek-v4-pro"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        resolved_key = os.getenv("DEEPSEEK_API_KEY") if api_key is None else api_key
        if not resolved_key:
            raise ValueError("DeepSeek API Key 未设置，请设置环境变量 DEEPSEEK_API_KEY")
        super().__init__(
            api_key=resolved_key,
            api_url=api_url or os.getenv("DEEPSEEK_API_URL") or self.DEFAULT_API_URL,
            model=model or os.getenv("DEEPSEEK_REVIEW_MODEL") or self.DEFAULT_MODEL,
            **kwargs,
        )

    def _build_request_payload(self, messages: list[dict], **kwargs) -> dict:
        payload = super()._build_request_payload(messages, **kwargs)
        # V4 thinking is controlled explicitly so JSON reviews do not spend
        # their output budget on reasoning before returning the review object.
        payload["thinking"] = {"type": "disabled"}
        return payload
