"""
基于 API 的 LLM 引擎基类
"""

from ...core.interfaces import LLMEngine


class APILLMEngine(LLMEngine):
    """
    基于 API 的 LLM 文本摘要引擎基类
    可以对接各种云服务商的 LLM API，如：
    - MiniMax
    - OpenAI
    - 阿里云百炼
    等
    """

    def __init__(self, api_key: str, api_url: str, **kwargs):
        self.api_key = api_key
        self.api_url = api_url
        self.options = kwargs

    def summarize(self, text: str, **kwargs) -> str:
        """对单段文本进行摘要/改写"""
        raise NotImplementedError(
            "API LLM Engine 需要根据具体的 API 服务商实现。\n"
            "参考 QwenLLMEngine、OpenAILLMEngine 或其他具体实现类。"
        )

    def summarize_document(self, pages: list[str], **kwargs) -> str:
        """对整个文档统一摘要"""
        raise NotImplementedError(
            "API LLM Engine 需要根据具体的 API 服务商实现。\n"
            "参考 QwenLLMEngine、OpenAILLMEngine 或其他具体实现类。"
        )
