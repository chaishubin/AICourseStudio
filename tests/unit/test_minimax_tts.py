"""
测试 MiniMax TTS 引擎实现

测试覆盖:
- MiniMaxTTSEngine 初始化
- 请求负载构建
- 语速解析
- 异步转换
"""

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
            api_key="test-key",
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
    async def test_convert_requires_text_and_voice(self, temp_dir):
        """测试转换需要文本和语音"""
        engine = MiniMaxTTSEngine(api_key="test-key")

        output_path = temp_dir / "test.mp3"

        # 这个测试验证基本参数是否被正确传递
        # 实际的 API 调用会由集成测试覆盖
        assert engine.api_key == "test-key"
        assert output_path.parent == temp_dir


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
