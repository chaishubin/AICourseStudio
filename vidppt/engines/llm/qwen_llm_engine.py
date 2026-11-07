"""阿里云百炼通义千问 LLM 引擎（OpenAI 兼容 Chat Completions）。"""

import os
import random
import time
from typing import Optional

from loguru import logger

from ...core.interfaces import LLMEngine


class QwenLLMEngine(LLMEngine):
    DEFAULT_API_URL = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    )
    DEFAULT_MODEL = "qwen3.7-plus"
    DEFAULT_SYSTEM_PROMPT = (
        "你是一位专业的教学内容编辑。请将输入内容改写为准确、自然、"
        "适合课程讲解的中文口语稿，保留关键知识，不添加无依据的信息。"
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        enable_thinking: bool = False,
        **kwargs,
    ):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "千问 API Key 未设置，请设置环境变量 DASHSCOPE_API_KEY"
            )
        self.api_url = (api_url or os.getenv("QWEN_API_URL") or self.DEFAULT_API_URL).rstrip("/")
        if not self.api_url.endswith("/chat/completions"):
            self.api_url += "/chat/completions"
        self.model = model or os.getenv("QWEN_MODEL") or self.DEFAULT_MODEL
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = float(timeout if timeout is not None else os.getenv("QWEN_TIMEOUT", "300"))
        self.max_retries = int(max_retries if max_retries is not None else os.getenv("QWEN_MAX_RETRIES", "4"))
        if self.timeout <= 0 or self.max_retries < 1:
            raise ValueError("千问 timeout 必须大于 0，max_retries 必须至少为 1")
        self.enable_thinking = enable_thinking
        self.options = kwargs

    def _call_api(self, messages: list[dict], **kwargs) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError("千问调用需要 httpx，请安装 api 依赖") from exc

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": False,
            "enable_thinking": kwargs.get("enable_thinking", self.enable_thinking),
        }
        if kwargs.get("response_format"):
            payload["response_format"] = kwargs["response_format"]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=min(30.0, self.timeout))) as client:
                    response = client.post(
                        self.api_url, headers=headers, json=payload
                    )
                    response.raise_for_status()
                    result = response.json()
                choices = result.get("choices") or []
                if choices and choices[0].get("finish_reason") == "length":
                    raise ValueError("千问输出被截断，请增加 max_tokens 或缩短输入")
                content = (
                    choices[0].get("message", {}).get("content", "")
                    if choices
                    else ""
                )
                if not content:
                    raise ValueError(f"千问返回内容为空: {result}")
                return content
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                    raise
                last_error = exc
                if attempt == self.max_retries:
                    raise
                wait = min(30.0, 2 ** attempt) + random.uniform(0, 1)
                if isinstance(exc, httpx.HTTPStatusError):
                    try:
                        wait = max(wait, min(60.0, float(exc.response.headers.get("Retry-After", "0"))))
                    except ValueError:
                        pass
                logger.warning(
                    f"千问请求失败（{attempt}/{self.max_retries}），"
                    f"{wait:.1f}s 后重试（model={payload['model']}）: {exc}"
                )
                time.sleep(wait)
        raise last_error or RuntimeError("千问请求失败")

    def summarize(self, text: str, **kwargs) -> str:
        system_prompt = kwargs.pop("system_prompt", self.system_prompt)
        return self._call_api(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            **kwargs,
        )

    def analyze_slide(self, text: str, image_path, **kwargs) -> str:
        from .vision import image_content
        system_prompt = kwargs.pop("system_prompt", self.system_prompt)
        kwargs.setdefault("model", self.options.get("vision_model") or os.getenv("QWEN_VISION_MODEL") or 'qwen3-vl-plus')
        return self._call_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": image_content(text, image_path)},
        ], **kwargs)

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
