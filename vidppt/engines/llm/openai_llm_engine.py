"""OpenAI ChatGPT LLM engine using Chat Completions."""

import os
import time
from typing import Optional

from loguru import logger

from ...core.interfaces import LLMEngine


class OpenAILLMEngine(LLMEngine):
    DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_SYSTEM_PROMPT = (
        "你是一位专业的教学内容编辑。请将输入内容改写为准确、自然、"
        "适合课程讲解的中文口语稿，保留关键知识，不添加无依据的信息。"
    )
    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_MAX_TOKENS = 8192
    DEFAULT_TIMEOUT = 120.0
    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = DEFAULT_API_URL,
        model: Optional[str] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        **kwargs,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API Key 未设置，请设置环境变量 OPENAI_API_KEY")
        self.api_url = api_url.rstrip("/")
        if not self.api_url.endswith("/chat/completions"):
            self.api_url += "/chat/completions"
        self.model = model or os.getenv("OPENAI_LLM_MODEL") or self.DEFAULT_MODEL
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.options = kwargs

    def _call_api(self, messages: list[dict], **kwargs) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError("OpenAI 调用需要 httpx，请安装 api 依赖") from exc

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        self.api_url, headers=headers, json=payload
                    )
                    response.raise_for_status()
                    result = response.json()
                choices = result.get("choices") or []
                content = (
                    choices[0].get("message", {}).get("content", "")
                    if choices
                    else ""
                )
                if not content:
                    raise ValueError(f"OpenAI 返回内容为空: {result}")
                return content
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    raise
                wait = 2 ** (attempt - 1)
                logger.warning(
                    f"OpenAI 请求失败（{attempt}/{self.max_retries}），"
                    f"{wait}s 后重试: {exc}"
                )
                time.sleep(wait)
        raise last_error or RuntimeError("OpenAI 请求失败")

    def summarize(self, text: str, **kwargs) -> str:
        system_prompt = kwargs.pop("system_prompt", self.system_prompt)
        return self._call_api(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            **kwargs,
        )

    def summarize_document(self, pages: list[str], **kwargs) -> str:
        system_prompt = kwargs.pop("system_prompt", self.system_prompt)
        content = "\n\n".join(
            f"--- 第 {index} 页 ---\n{text}"
            for index, text in enumerate(pages, 1)
        )
        return self.summarize(
            content,
            system_prompt=(
                system_prompt
                + "\n请对整个文档统一分析和改写，不要遗漏跨页上下文。"
            ),
            **kwargs,
        )
