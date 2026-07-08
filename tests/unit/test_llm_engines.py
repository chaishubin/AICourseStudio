"""
测试 LLM 文本摘要引擎

测试覆盖：
- LLMEngine 抽象接口
- APILLMEngine 基类
- OpenAILLMEngine 初始化与参数
- OpenAILLMEngine summarize / summarize_pages / summarize_document
- 环境变量处理
- API 调用与重试逻辑
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from vidppt.core.interfaces import LLMEngine
from vidppt.engines.llm.api_llm_engine import APILLMEngine
from vidppt.engines.llm.openai_llm_engine import OpenAILLMEngine


class TestLLMEngineInterface:
    """测试 LLMEngine 抽象接口"""

    def test_cannot_instantiate_abstract_engine(self):
        """测试不能直接实例化抽象引擎"""
        with pytest.raises(TypeError):
            LLMEngine()

    def test_must_implement_summarize(self):
        """测试必须实现 summarize 方法"""

        class IncompleteEngine(LLMEngine):
            def summarize_document(self, pages, **kwargs):
                pass

        with pytest.raises(TypeError):
            IncompleteEngine()

    def test_must_implement_summarize_document(self):
        """测试必须实现 summarize_document 方法"""

        class IncompleteEngine(LLMEngine):
            def summarize(self, text, **kwargs):
                pass

        with pytest.raises(TypeError):
            IncompleteEngine()

    def test_can_inherit_and_implement(self):
        """测试可以继承并实现接口"""

        class CustomLLMEngine(LLMEngine):
            def summarize(self, text, **kwargs):
                return f"摘要: {text}"

            def summarize_document(self, pages, **kwargs):
                return "文档摘要"

        engine = CustomLLMEngine()
        assert isinstance(engine, LLMEngine)
        assert engine.summarize("测试") == "摘要: 测试"
        assert engine.summarize_document(["a", "b"]) == "文档摘要"

    def test_summarize_pages_default_implementation(self):
        """测试 summarize_pages 默认实现（逐个调用 summarize）"""

        class CustomLLMEngine(LLMEngine):
            def summarize(self, text, **kwargs):
                return f"改写: {text}"

            def summarize_document(self, pages, **kwargs):
                return "文档摘要"

        engine = CustomLLMEngine()
        results = engine.summarize_pages(["第一页", "第二页"])
        assert results == ["改写: 第一页", "改写: 第二页"]

    def test_summarize_pages_can_be_overridden(self):
        """测试 summarize_pages 可以被覆写"""

        class CustomLLMEngine(LLMEngine):
            def summarize(self, text, **kwargs):
                return "单页"

            def summarize_pages(self, pages, **kwargs):
                return ["批量改写"] * len(pages)

            def summarize_document(self, pages, **kwargs):
                return "文档摘要"

        engine = CustomLLMEngine()
        results = engine.summarize_pages(["a", "b", "c"])
        assert results == ["批量改写", "批量改写", "批量改写"]


class TestAPILLMEngine:
    """测试 APILLMEngine 基类"""

    def test_init(self):
        """测试初始化"""
        engine = APILLMEngine(api_key="test-key", api_url="https://api.example.com")
        assert engine.api_key == "test-key"
        assert engine.api_url == "https://api.example.com"
        assert engine.options == {}

    def test_init_with_kwargs(self):
        """测试带额外参数初始化"""
        engine = APILLMEngine(
            api_key="test-key",
            api_url="https://api.example.com",
            timeout=30,
            retries=2,
        )
        assert engine.options["timeout"] == 30
        assert engine.options["retries"] == 2

    def test_summarize_raises_not_implemented(self):
        """测试 summarize 抛出 NotImplementedError"""
        engine = APILLMEngine(api_key="test-key", api_url="https://api.example.com")
        with pytest.raises(NotImplementedError, match="API LLM Engine"):
            engine.summarize("测试文本")

    def test_summarize_document_raises_not_implemented(self):
        """测试 summarize_document 抛出 NotImplementedError"""
        engine = APILLMEngine(api_key="test-key", api_url="https://api.example.com")
        with pytest.raises(NotImplementedError, match="API LLM Engine"):
            engine.summarize_document(["第一页", "第二页"])


class TestOpenAILLMEngineInit:
    """测试 OpenAILLMEngine 初始化"""

    def test_engine_initialization_with_explicit_key(self):
        """测试显式传入 api_key"""
        engine = OpenAILLMEngine(api_key="sk-testkey")
        assert engine.api_key == "sk-testkey"
        assert engine.model == OpenAILLMEngine.DEFAULT_MODEL
        assert engine.api_url == OpenAILLMEngine.DEFAULT_API_URL
        assert engine.temperature == OpenAILLMEngine.DEFAULT_TEMPERATURE
        assert engine.max_tokens == OpenAILLMEngine.DEFAULT_MAX_TOKENS
        assert engine.timeout == OpenAILLMEngine.DEFAULT_TIMEOUT
        assert engine.max_retries == OpenAILLMEngine.DEFAULT_MAX_RETRIES

    def test_engine_custom_config(self):
        """测试自定义配置"""
        engine = OpenAILLMEngine(
            api_key="test-key",
            model="custom-model",
            system_prompt="自定义提示词",
            temperature=0.3,
            max_tokens=2048,
            timeout=30.0,
            max_retries=5,
        )
        assert engine.model == "custom-model"
        assert engine.system_prompt == "自定义提示词"
        assert engine.temperature == 0.3
        assert engine.max_tokens == 2048
        assert engine.timeout == 30.0
        assert engine.max_retries == 5


class TestOpenAIEnvironmentVariable:
    """测试 OpenAI LLM 环境变量处理"""

    def test_api_key_from_environment_variable(self, monkeypatch):
        """测试从 OPENAI_API_KEY 环境变量读取 api_key"""
        monkeypatch.setenv("OPENAI_API_KEY", "env-api-key")
        engine = OpenAILLMEngine(api_key=None)
        assert engine.api_key == "env-api-key"

    def test_explicit_key_overrides_env(self, monkeypatch):
        """测试显式 api_key 优先于环境变量"""
        monkeypatch.setenv("OPENAI_API_KEY", "env-api-key")
        engine = OpenAILLMEngine(api_key="explicit-key")
        assert engine.api_key == "explicit-key"

    def test_missing_env_variable_raises(self, monkeypatch):
        """测试缺少环境变量抛出 ValueError"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAILLMEngine(api_key=None)

    def test_empty_env_variable_raises(self, monkeypatch):
        """测试空环境变量抛出 ValueError"""
        monkeypatch.setenv("OPENAI_API_KEY", "")
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAILLMEngine(api_key=None)

    def test_empty_string_api_key_raises(self):
        """测试空字符串 api_key 抛出 ValueError"""
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAILLMEngine(api_key="")


class TestOpenAICallApi:
    """测试 OpenAILLMEngine._call_api"""

    def test_call_api_success(self):
        """测试成功调用 API"""
        engine = OpenAILLMEngine(api_key="test-key")
        mock_httpx, mock_client, _ = self._make_mock_httpx()

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = engine._call_api(
                [{"role": "user", "content": "原始文本"}]
            )
            assert result == "改写后的文本"
            mock_client.post.assert_called_once()

    def test_call_api_empty_content_raises(self):
        """测试 API 返回空内容抛出 ValueError"""
        engine = OpenAILLMEngine(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": ""}}]
        }

        mock_httpx, mock_client, _ = self._make_mock_httpx()
        mock_client.post.return_value = mock_response

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            with pytest.raises(ValueError, match="OpenAI 返回内容为空"):
                engine._call_api([{"role": "user", "content": "原始文本"}])

    def test_call_api_missing_choices_raises(self):
        """测试 API 返回空 choices 列表抛出 ValueError"""
        engine = OpenAILLMEngine(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": []}

        mock_httpx, mock_client, _ = self._make_mock_httpx()
        mock_client.post.return_value = mock_response

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            with pytest.raises(ValueError, match="OpenAI 返回内容为空"):
                engine._call_api([{"role": "user", "content": "原始文本"}])

    def test_call_api_builds_correct_payload(self):
        """测试 _call_api 构建正确的请求参数"""
        engine = OpenAILLMEngine(
            api_key="test-key",
            model="test-model",
            temperature=0.5,
            max_tokens=1024,
        )
        mock_httpx, mock_client, _ = self._make_mock_httpx()

        messages = [
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "用户文本"},
        ]

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            engine._call_api(messages)
            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["json"]["model"] == "test-model"
            assert call_kwargs["json"]["messages"] == messages
            assert call_kwargs["json"]["temperature"] == 0.5
            assert call_kwargs["json"]["max_tokens"] == 1024
            assert "Bearer test-key" in call_kwargs["headers"]["Authorization"]

    def _make_mock_httpx(self):
        """创建 mock httpx 模块，异常类继承 BaseException"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "改写后的文本"}}]
        }

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        mock_httpx = MagicMock()
        mock_httpx.Client = MagicMock(return_value=mock_client)
        # 确保 httpx.TimeoutException 和 httpx.NetworkError 继承 BaseException
        mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
        mock_httpx.NetworkError = type("NetworkError", (Exception,), {})

        return mock_httpx, mock_client, mock_response


class TestOpenAISummarize:
    """测试 OpenAILLMEngine.summarize"""

    def test_summarize_builds_correct_messages(self):
        """测试 summarize 构建正确的消息格式"""
        engine = OpenAILLMEngine(api_key="test-key")

        with patch.object(engine, "_call_api", return_value="改写结果") as mock_call:
            result = engine.summarize("原始PPT文本")

            assert result == "改写结果"
            call_args = mock_call.call_args
            messages = call_args[0][0]
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "原始PPT文本"

    def test_summarize_with_custom_system_prompt(self):
        """测试自定义系统提示词"""
        engine = OpenAILLMEngine(api_key="test-key")

        with patch.object(engine, "_call_api", return_value="结果") as mock_call:
            engine.summarize("文本", system_prompt="自定义提示")

            messages = mock_call.call_args[0][0]
            assert messages[0]["content"] == "自定义提示"

    def test_summarize_with_kwargs_override(self):
        """测试 kwargs 覆盖默认参数"""
        engine = OpenAILLMEngine(api_key="test-key")

        with patch.object(engine, "_call_api", return_value="结果") as mock_call:
            engine.summarize("文本", temperature=0.1, max_tokens=512)

            # _call_api 的 kwargs 应包含 temperature 和 max_tokens
            call_kwargs = mock_call.call_args[1]
            assert call_kwargs.get("temperature") == 0.1
            assert call_kwargs.get("max_tokens") == 512


class TestOpenAISummarizePages:
    """测试 OpenAILLMEngine.summarize_pages"""

    def test_summarize_pages_sequential(self):
        """测试逐页摘要"""
        engine = OpenAILLMEngine(api_key="test-key")

        with patch.object(engine, "summarize", side_effect=["摘要1", "摘要2", "摘要3"]) as mock_s:
            results = engine.summarize_pages(["第一页", "第二页", "第三页"])

            assert results == ["摘要1", "摘要2", "摘要3"]
            assert mock_s.call_count == 3


class TestOpenAISummarizeDocument:
    """测试 OpenAILLMEngine.summarize_document"""

    def test_summarize_document_concatenates_pages(self):
        """测试整文档摘要拼接所有页"""
        engine = OpenAILLMEngine(api_key="test-key")

        with patch.object(engine, "_call_api", return_value="整文档摘要") as mock_call:
            result = engine.summarize_document(["第一页内容", "第二页内容", "第三页内容"])

            assert result == "整文档摘要"
            messages = mock_call.call_args[0][0]
            user_content = messages[1]["content"]
            assert "--- 第 1 页 ---" in user_content
            assert "--- 第 2 页 ---" in user_content
            assert "--- 第 3 页 ---" in user_content
            assert "第一页内容" in user_content
            assert "第二页内容" in user_content

    def test_summarize_document_appends_instruction(self):
        """测试整文档摘要追加指令到 system_prompt"""
        engine = OpenAILLMEngine(api_key="test-key")

        with patch.object(engine, "_call_api", return_value="摘要") as mock_call:
            engine.summarize_document(["内容"])

            system_content = mock_call.call_args[0][0][0]["content"]
            assert "统一分析和改写" in system_content

    def test_summarize_document_with_custom_system_prompt(self):
        """测试整文档摘要使用自定义系统提示词"""
        engine = OpenAILLMEngine(api_key="test-key")

        with patch.object(engine, "_call_api", return_value="摘要") as mock_call:
            engine.summarize_document(["内容"], system_prompt="自定义提示")

            system_content = mock_call.call_args[0][0][0]["content"]
            assert "自定义提示" in system_content
            assert "统一分析和改写" in system_content


class TestOpenAILLMIntegration:
    """测试 OpenAI LLM 集成场景"""

    def test_full_per_page_workflow(self):
        """测试逐页摘要完整工作流"""
        engine = OpenAILLMEngine(api_key="test-key")

        pages = [
            "• 要点1\n• 要点2",
            "• 要点3\n• 要点4",
        ]

        with patch.object(engine, "_call_api", side_effect=["改写1", "改写2"]):
            results = engine.summarize_pages(pages)
            assert results == ["改写1", "改写2"]

    def test_full_whole_document_workflow(self):
        """测试整文档摘要完整工作流"""
        engine = OpenAILLMEngine(api_key="test-key")

        with patch.object(engine, "_call_api", return_value="整文档摘要文本"):
            result = engine.summarize_document(["第一页", "第二页"])
            assert result == "整文档摘要文本"

    def test_httpx_not_installed(self, monkeypatch):
        """测试 httpx 未安装时抛出 ImportError"""
        engine = OpenAILLMEngine(api_key="test-key")

        # 模拟 import httpx 失败
        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def mock_import(name, *args, **kwargs):
            if name == "httpx":
                raise ImportError("No module named 'httpx'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="OpenAI 调用需要 httpx"):
                engine._call_api([{"role": "user", "content": "test"}])
