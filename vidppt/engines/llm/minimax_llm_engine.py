"""
MiniMax LLM 引擎实现
使用 MiniMax ChatCompletion API 进行文本摘要/改写
"""

import os
import time
from typing import Optional

from loguru import logger

from ...core.interfaces import LLMEngine


class MiniMaxLLMEngine(LLMEngine):
    """
    MiniMax LLM 引擎实现

    API 文档: https://platform.minimaxi.com/document/ChatCompletion%20v2

    使用方法：
        engine = MiniMaxLLMEngine(
            api_key="sk-cp-xxx",
        )

        result = engine.summarize("原始文本")
    """

    DEFAULT_API_URL = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    DEFAULT_MODEL = "MiniMax-M2.7"
    DEFAULT_SYSTEM_PROMPT = (
        "你是一位专业的文稿编辑，擅长将幻灯片（PPT）中的内容精简为适合语音播报的简短叙述。"
        "请将以下幻灯片内容摘要为流畅的口语化叙述，保持核心原意，"
        "去除项目符号、列表格式和冗余细节，使文本比原文更短。"
        "输出长度不超过原文的70%。"
        "直接输出摘要文本，不要添加任何前缀或解释。"
    )
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = DEFAULT_API_URL,
        model: str = DEFAULT_MODEL,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        **kwargs,
    ):
        # 从环境变量读取 API key
        if api_key is None:
            api_key = os.getenv("MINIMAX_API")
            assert api_key, (
                "MiniMax API key 未设置。请设置环境变量 MINIMAX_API。\n"
                "示例: export MINIMAX_API='sk-cp-xxxxxxxxxxxxxx'"
            )
        else:
            assert api_key, "MiniMax API key 不能为空字符串"

        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.options = kwargs

    def _call_api(self, messages: list[dict], **kwargs) -> str:
        """
        调用 MiniMax ChatCompletion API（同步，指数退避重试）

        参数:
            messages: 消息列表，如 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            **kwargs: 覆盖默认参数（temperature, max_tokens 等）

        返回:
            模型生成的文本内容
        """
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx 未安装。请运行: pip install httpx")

        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        last_exc: Exception = RuntimeError("未知错误")
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        self.api_url,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()

                    result = response.json()

                    # 检查 API 错误信息
                    base_resp = result.get("base_resp") or {}
                    if base_resp.get("status_code") and base_resp.get("status_code") != 0:
                        status_msg = base_resp.get("status_msg", "未知错误")
                        raise RuntimeError(
                            f"MiniMax API 返回错误 (code={base_resp['status_code']}): {status_msg}"
                        )

                    choices = result.get("choices") or []
                    if not choices:
                        raise ValueError(f"API 返回的内容为空。完整响应: {result}")

                    content = (
                        choices[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    if not content:
                        raise ValueError(f"API 返回的内容为空。完整响应: {result}")
                    return content

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = 2 ** (attempt - 1)
                    logger.warning(
                        f"LLM API 请求失败（第 {attempt}/{self.max_retries} 次）"
                        f"，{wait}s 后重试: {exc}"
                    )
                    time.sleep(wait)
                else:
                    raise
            except Exception:
                raise

        raise last_exc

    def summarize(self, text: str, **kwargs) -> str:
        """
        对单段文本进行摘要/改写

        参数:
            text: 原始文本
            **kwargs: 覆盖默认参数（system_prompt, temperature, max_tokens 等）

        返回:
            改写后的文本
        """
        system_prompt = kwargs.pop("system_prompt", self.system_prompt)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        return self._call_api(messages, **kwargs)

    def summarize_pages(self, pages: list[str], **kwargs) -> list[str]:
        """
        逐页摘要

        参数:
            pages: 每页的文本列表
            **kwargs: 覆盖默认参数

        返回:
            每页改写后的文本列表
        """
        results = []
        for i, text in enumerate(pages, 1):
            logger.debug(f"LLM 逐页摘要: 第 {i}/{len(pages)} 页")
            results.append(self.summarize(text, **kwargs))
        return results

    def summarize_document(self, pages: list[str], **kwargs) -> str:
        """
        对整个文档统一摘要

        将所有页内容拼接（标注页码），追加整文档摘要指令到 system_prompt 后调用 API

        参数:
            pages: 每页的文本列表
            **kwargs: 覆盖默认参数

        返回:
            整个文档的摘要文本
        """
        system_prompt = kwargs.pop("system_prompt", self.system_prompt)
        doc_system_prompt = (
            system_prompt
            + "\n\n以下内容是整个文档的所有页面，请对全部内容进行统一精简摘要，"
            "输出一段简洁的、适合语音播报的叙述文本，总长度不超过原文的50%。"
        )

        # 拼接所有页内容，标注页码
        pages_text = []
        for i, text in enumerate(pages, 1):
            pages_text.append(f"--- 第 {i} 页 ---\n{text}")
        full_text = "\n\n".join(pages_text)

        messages = [
            {"role": "system", "content": doc_system_prompt},
            {"role": "user", "content": full_text},
        ]
        return self._call_api(messages, **kwargs)
