"""
测试 MiniMax TTS 引擎实现

测试覆盖:
- MiniMaxTTSEngine 初始化
- 请求负载构建
- 语速解析
- 异步转换
- 环境变量处理
"""

import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from vidppt.engines.tts.api_tts_engine import MiniMaxTTSEngine, APITTSEngine


class TestMiniMaxTTSEngine:
    """测试 MiniMaxTTSEngine"""

    def test_engine_initialization(self):
        """测试引擎初始化"""
        engine = MiniMaxTTSEngine(api_key="test-key", model="speech-2.8-hd")

        assert engine.api_key == "test-key"
        assert engine.model == "speech-2.8-hd"
        assert engine.sample_rate == 32000
        assert engine.bitrate == 128000
        assert engine.audio_format == "mp3"
        assert engine.channel == 1
        assert engine.emotion == "neutral"

    def test_engine_custom_config(self):
        """测试自定义配置"""
        engine = MiniMaxTTSEngine(
            api_key="sk-cp-7HnzXk9RLCaGdV7s6RsQ-qKtwM4Pdoly4L1NG65iMZmAR-8XCg_9qEDxsKXhhcocnU90cq1lzwabZFBT3EVEgrTbwSg62c-AQ3IV_FFPU8FDn2fuBX2Ps4w",
            model="speech-2.8-hd",
            sample_rate=44100,
            bitrate=256000,
            audio_format="wav",
            channel=2,
            emotion="happy",
        )

        assert engine.sample_rate == 44100
        assert engine.bitrate == 256000
        assert engine.audio_format == "wav"
        assert engine.channel == 2
        assert engine.emotion == "happy"

    def test_invalid_emotion_defaults_to_neutral(self):
        """测试无效情感类型默认为中立"""
        engine = MiniMaxTTSEngine(api_key="test-key", emotion="invalid_emotion")

        assert engine.emotion == "neutral"


class TestEnvironmentVariableHandling:
    """测试环境变量处理"""

    def test_api_key_from_explicit_parameter(self):
        """测试显式传入 api_key"""
        engine = MiniMaxTTSEngine(api_key="explicit-key")
        assert engine.api_key == "explicit-key"

    def test_api_key_from_environment_variable(self, monkeypatch):
        """测试从 MINIMAX_API 环境变量读取 api_key"""
        monkeypatch.setenv("MINIMAX_API", "env-api-key")
        engine = MiniMaxTTSEngine(api_key=None)
        assert engine.api_key == "env-api-key"

    def test_empty_environment_variable_raises_assertion_error(self, monkeypatch):
        """测试空的环境变量会抛出 AssertionError"""
        monkeypatch.setenv("MINIMAX_API", "")
        with pytest.raises(AssertionError, match="MiniMax API key 未设置"):
            MiniMaxTTSEngine(api_key=None)

    def test_missing_environment_variable_raises_assertion_error(self, monkeypatch):
        """测试缺少环境变量会抛出 AssertionError"""
        monkeypatch.delenv("MINIMAX_API", raising=False)
        with pytest.raises(AssertionError, match="MiniMax API key 未设置"):
            MiniMaxTTSEngine(api_key=None)

    def test_empty_string_api_key_raises_assertion_error(self):
        """测试空字符串 api_key 会抛出 AssertionError"""
        with pytest.raises(AssertionError, match="MiniMax API key 不能为空字符串"):
            MiniMaxTTSEngine(api_key="")

    def test_explicit_api_key_overrides_environment_variable(self, monkeypatch):
        """测试显式传入的 api_key 优先于环境变量"""
        monkeypatch.setenv("MINIMAX_API", "env-api-key")
        engine = MiniMaxTTSEngine(api_key="explicit-key")
        assert engine.api_key == "explicit-key"

    def test_none_api_key_uses_environment_variable(self, monkeypatch):
        """测试 None api_key 时使用环境变量"""
        monkeypatch.setenv("MINIMAX_API", "from-env")
        engine = MiniMaxTTSEngine(api_key=None)
        assert engine.api_key == "from-env"

    def test_environment_variable_message_includes_export_example(self, monkeypatch):
        """测试错误消息包含环境变量设置示例"""
        monkeypatch.setenv("MINIMAX_API", "")
        try:
            MiniMaxTTSEngine(api_key=None)
        except AssertionError as e:
            assert "export MINIMAX_API" in str(e)


class TestRateParsing:
    """测试语速解析"""

    def test_parse_positive_percentage(self):
        """测试正百分比"""
        rate = MiniMaxTTSEngine._parse_rate("+20%")
        assert rate == 1.2

    def test_parse_negative_percentage(self):
        """测试负百分比"""
        rate = MiniMaxTTSEngine._parse_rate("-10%")
        assert rate == 0.9

    def test_parse_zero_percentage(self):
        """测试零百分比"""
        rate = MiniMaxTTSEngine._parse_rate("+0%")
        assert rate == 1.0

    def test_parse_direct_float(self):
        """测试直接浮点数"""
        rate = MiniMaxTTSEngine._parse_rate("1.5")
        assert rate == 1.5

    def test_parse_clamped_to_range(self):
        """测试范围限制"""
        # 超出上限
        rate = MiniMaxTTSEngine._parse_rate("+200%")
        assert rate == 2.0

        # 超出下限
        rate = MiniMaxTTSEngine._parse_rate("-60%")
        assert rate == 0.5

    def test_parse_percentage_without_percent_sign(self):
        """测试不带百分号的百分比"""
        rate = MiniMaxTTSEngine._parse_rate("+20")
        assert rate == 1.2

    def test_parse_invalid_defaults_to_one(self):
        """测试无效输入默认为 1.0"""
        rate = MiniMaxTTSEngine._parse_rate("invalid")
        assert rate == 1.0


class TestPayloadBuilding:
    """测试请求负载构建"""

    def test_basic_payload(self):
        """测试基本负载"""
        engine = MiniMaxTTSEngine(api_key="test-key")

        payload = engine._build_request_payload(
            text="测试文本", voice="male-qn-qingse", rate="+0%"
        )

        assert payload["model"] == "speech-2.8-hd"
        assert payload["text"] == "测试文本"
        assert payload["stream"] is False
        assert payload["voice_setting"]["voice_id"] == "male-qn-qingse"
        assert payload["voice_setting"]["speed"] == 1.0
        assert payload["audio_setting"]["sample_rate"] == 32000
        assert payload["audio_setting"]["format"] == "mp3"

    def test_payload_with_empty_text(self):
        """测试空文本处理"""
        engine = MiniMaxTTSEngine(api_key="test-key")

        payload = engine._build_request_payload(
            text="   ", voice="male-qn-qingse", rate="+0%"
        )

        assert payload["text"] == "此页无文字内容。"

    def test_payload_with_custom_emotion(self):
        """测试自定义情感"""
        engine = MiniMaxTTSEngine(api_key="test-key")

        payload = engine._build_request_payload(
            text="开心的文本", voice="male-qn-qingse", rate="+0%", emotion="happy"
        )

        assert payload["voice_setting"]["emotion"] == "happy"

    def test_payload_with_pronunciation_dict(self):
        """测试发音字典"""
        engine = MiniMaxTTSEngine(api_key="test-key")

        pron_dict = {"tone": ["处理/(chu3)(li3)", "危险/dangerous"]}

        payload = engine._build_request_payload(
            text="处理危险",
            voice="male-qn-qingse",
            rate="+0%",
            pronunciation_dict=pron_dict,
        )

        assert payload["pronunciation_dict"] == pron_dict

    def test_payload_with_rate_settings(self):
        """测试不同语速设置"""
        engine = MiniMaxTTSEngine(api_key="test-key")

        test_cases = [
            ("+20%", 1.2),
            ("-10%", 0.9),
            ("1.5", 1.5),
        ]

        for rate_input, expected_speed in test_cases:
            payload = engine._build_request_payload(
                text="测试", voice="male-qn-qingse", rate=rate_input
            )
            assert payload["voice_setting"]["speed"] == expected_speed


class TestMiniMaxConvertAsync:
    """测试异步转换"""

    @pytest.mark.asyncio
    async def test_convert_async_with_mock_httpx(self, temp_dir):
        """测试 convert_async 方法的核心逻辑（用 Mock 模拟 httpx）"""
        import asyncio

        engine = MiniMaxTTSEngine(api_key="test-key")
        output_path = temp_dir / "test.mp3"

        # Mock 的音频数据（十六进制编码）
        mock_audio_hex = "FFD8FFE0"  # 简单的JPEG头部作示例
        mock_response_data = {"data": {"audio": mock_audio_hex}}

        # Mock httpx
        with patch("httpx.AsyncClient") as mock_client_class:
            # 配置 mock
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value=mock_response_data)
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # 调用 convert_async
            await engine.convert_async(
                text="测试文本",
                output_path=output_path,
                voice="male-qn-qingse",
                rate="+0%",
            )

            # 验证：
            # 1. httpx.AsyncClient 被创建
            mock_client_class.assert_called_once()

            # 2. client.post 被调用了正确的参数
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["timeout"] == 30.0
            assert "headers" in call_kwargs
            assert "json" in call_kwargs

            # 3. 文件被创建
            assert output_path.exists()
            # 4. 文件内容正确（十六进制数据被转换为字节）
            file_data = output_path.read_bytes()
            assert file_data == bytes.fromhex(mock_audio_hex)

    @pytest.mark.asyncio
    async def test_convert_async_handles_empty_text(self, temp_dir):
        """测试 convert_async 处理空文本"""
        engine = MiniMaxTTSEngine(api_key="test-key")
        output_path = temp_dir / "empty.mp3"

        mock_audio_hex = "FFFF"
        mock_response_data = {"data": {"audio": mock_audio_hex}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value=mock_response_data)
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # 空文本
            await engine.convert_async(
                text="", output_path=output_path, voice="male-qn-qingse", rate="+0%"
            )

            # 验证请求中的文本被设置为默认值
            call_kwargs = mock_client.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload["text"] == "此页无文字内容。"  # 默认值

    @pytest.mark.asyncio
    async def test_convert_async_with_emotion(self, temp_dir):
        """测试 convert_async 带情感参数"""
        engine = MiniMaxTTSEngine(api_key="test-key")
        output_path = temp_dir / "emotion.mp3"

        mock_audio_hex = "FFFF"
        mock_response_data = {"data": {"audio": mock_audio_hex}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value=mock_response_data)
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # 带情感
            await engine.convert_async(
                text="开心的文本",
                output_path=output_path,
                voice="female-qn-nana",
                rate="+10%",
                emotion="happy",
            )

            # 验证请求中的情感被设置
            call_kwargs = mock_client.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload["voice_setting"]["emotion"] == "happy"
            assert payload["voice_setting"]["speed"] == 1.1  # +10%

    @pytest.mark.asyncio
    async def test_convert_async_missing_audio_data_raises_error(self, temp_dir):
        """测试 convert_async 处理缺失音频数据"""
        engine = MiniMaxTTSEngine(api_key="test-key")
        output_path = temp_dir / "missing.mp3"

        # 缺失 audio 字段
        mock_response_data = {"data": {}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value=mock_response_data)
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # 应该抛出 ValueError
            with pytest.raises(ValueError, match="API 返回的音频数据为空"):
                await engine.convert_async(
                    text="测试",
                    output_path=output_path,
                    voice="male-qn-qingse",
                    rate="+0%",
                )

    @pytest.mark.asyncio
    async def test_batch_convert_calls_multiple_convert_async(self, temp_dir):
        """测试 batch_convert 调用多个 convert_async"""
        engine = MiniMaxTTSEngine(api_key="test-key")

        texts = [
            (1, "第一页", temp_dir / "page1.mp3"),
            (2, "第二页", temp_dir / "page2.mp3"),
        ]

        mock_audio_hex = "FFFF"
        mock_response_data = {"data": {"audio": mock_audio_hex}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value=mock_response_data)
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # 批量转换
            await engine.batch_convert(
                texts=texts, voice="male-qn-qingse", rate="+0%", batch_size=2
            )

            # 验证 client.post 被调用了 2 次（一次一个文本）
            assert mock_client.post.call_count == 2

            # 验证文件被创建
            assert (temp_dir / "page1.mp3").exists()
            assert (temp_dir / "page2.mp3").exists()


class TestAPITTSEngineAbstract:
    """测试 APITTSEngine 抽象类"""

    def test_minimax_implements_interface(self):
        """测试 MiniMax 实现了接口"""
        engine = MiniMaxTTSEngine(api_key="test")

        assert hasattr(engine, "convert_async")
        assert hasattr(engine, "batch_convert")


class TestMiniMaxIntegration:
    """测试 MiniMax 集成场景"""

    def test_multiple_voices(self):
        """测试多种语音"""
        engine = MiniMaxTTSEngine(api_key="test-key")

        voices = [
            "male-qn-qingse",
            "female-qn-nana",
        ]

        for voice in voices:
            payload = engine._build_request_payload(
                text="测试", voice=voice, rate="+0%"
            )
            assert payload["voice_setting"]["voice_id"] == voice

    def test_all_emotions(self):
        """测试所有情感类型"""
        engine = MiniMaxTTSEngine(api_key="test-key")

        for emotion in MiniMaxTTSEngine.EMOTIONS:
            payload = engine._build_request_payload(
                text="测试", voice="male-qn-qingse", rate="+0%", emotion=emotion
            )
            assert payload["voice_setting"]["emotion"] == emotion
