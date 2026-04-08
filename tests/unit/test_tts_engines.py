"""
测试 TTS 引擎

测试覆盖：
- EdgeTTSEngine 实现
- TTSEngine 接口
- 异步转换功能
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from vidppt.engines.tts.edge_tts_engine import EdgeTTSEngine
from vidppt.core.interfaces import TTSEngine


class TestEdgeTTSEngine:
    """测试 EdgeTTSEngine"""

    @pytest.mark.asyncio
    async def test_convert_async_with_text(self, temp_dir):
        """测试异步转换文本为音频"""
        engine = EdgeTTSEngine()
        text = "这是测试文本"
        output_path = temp_dir / "test_audio.mp3"
        voice = "zh-CN-XiaoxiaoNeural"
        rate = "+0%"

        # Mock edge_tts.Communicate
        with patch(
            "vidppt.engines.tts.edge_tts_engine.edge_tts.Communicate"
        ) as mock_communicate_class:
            mock_communicate = AsyncMock()
            mock_communicate_class.return_value = mock_communicate

            await engine.convert_async(text, output_path, voice, rate)

            # 验证调用
            mock_communicate_class.assert_called_once_with(text, voice, rate=rate)
            mock_communicate.save.assert_called_once_with(str(output_path))

    @pytest.mark.asyncio
    async def test_convert_async_with_empty_text(self, temp_dir):
        """测试转换空文本（应使用默认文本）"""
        engine = EdgeTTSEngine()
        text = "   "  # 空白文本
        output_path = temp_dir / "empty_audio.mp3"
        voice = "zh-CN-XiaoxiaoNeural"
        rate = "+0%"

        with patch(
            "vidppt.engines.tts.edge_tts_engine.edge_tts.Communicate"
        ) as mock_communicate_class:
            mock_communicate = AsyncMock()
            mock_communicate_class.return_value = mock_communicate

            await engine.convert_async(text, output_path, voice, rate)

            # 应该使用默认文本
            call_args = mock_communicate_class.call_args[0]
            assert call_args[0] == "此页无文字内容。"

    @pytest.mark.asyncio
    async def test_convert_async_strips_whitespace(self, temp_dir):
        """测试转换时去除首尾空白"""
        engine = EdgeTTSEngine()
        text = "  测试文本  \n"
        output_path = temp_dir / "test_audio.mp3"
        voice = "zh-CN-XiaoxiaoNeural"
        rate = "+0%"

        with patch(
            "vidppt.engines.tts.edge_tts_engine.edge_tts.Communicate"
        ) as mock_communicate_class:
            mock_communicate = AsyncMock()
            mock_communicate_class.return_value = mock_communicate

            await engine.convert_async(text, output_path, voice, rate)

            # 验证文本已去除空白
            call_args = mock_communicate_class.call_args[0]
            assert call_args[0] == "测试文本"

    @pytest.mark.asyncio
    async def test_convert_async_with_different_voices(self, temp_dir):
        """测试不同的语音配置"""
        engine = EdgeTTSEngine()

        test_cases = [
            ("zh-CN-XiaoxiaoNeural", "+0%"),
            ("zh-CN-YunyangNeural", "+20%"),
            ("zh-CN-XiaoyiNeural", "-10%"),
        ]

        for voice, rate in test_cases:
            output_path = temp_dir / f"audio_{voice}.mp3"

            with patch(
                "vidppt.engines.tts.edge_tts_engine.edge_tts.Communicate"
            ) as mock_communicate_class:
                mock_communicate = AsyncMock()
                mock_communicate_class.return_value = mock_communicate

                await engine.convert_async("测试", output_path, voice, rate)

                # 验证参数
                call_args = mock_communicate_class.call_args
                assert call_args[0][1] == voice
                assert call_args[1]["rate"] == rate


class TestTTSEngineInterface:
    """测试 TTSEngine 接口"""

    @pytest.mark.asyncio
    async def test_batch_convert_basic(self, temp_dir):
        """测试批量转换基本功能"""

        # 创建测试引擎
        class TestTTSEngine(TTSEngine):
            def __init__(self):
                self.converted = []

            async def convert_async(self, text, output_path, voice, rate):
                # 记录转换
                self.converted.append((text, str(output_path)))
                await asyncio.sleep(0.01)  # 模拟异步操作

        engine = TestTTSEngine()

        texts = [
            (1, "第一页文本", temp_dir / "page1.mp3"),
            (2, "第二页文本", temp_dir / "page2.mp3"),
            (3, "第三页文本", temp_dir / "page3.mp3"),
        ]

        await engine.batch_convert(texts, "zh-CN-XiaoxiaoNeural", "+0%")

        # 验证所有文本都已转换
        assert len(engine.converted) == 3
        assert ("第一页文本", str(temp_dir / "page1.mp3")) in engine.converted
        assert ("第二页文本", str(temp_dir / "page2.mp3")) in engine.converted
        assert ("第三页文本", str(temp_dir / "page3.mp3")) in engine.converted

    @pytest.mark.asyncio
    async def test_batch_convert_with_batching(self, temp_dir):
        """测试批量转换的分批处理"""

        class TestTTSEngine(TTSEngine):
            def __init__(self):
                self.call_order = []
                self.concurrent_count = 0
                self.max_concurrent = 0

            async def convert_async(self, text, output_path, voice, rate):
                self.concurrent_count += 1
                self.max_concurrent = max(self.max_concurrent, self.concurrent_count)
                self.call_order.append(text)
                await asyncio.sleep(0.01)
                self.concurrent_count -= 1

        engine = TestTTSEngine()

        # 创建10个任务
        texts = [(i, f"文本{i}", temp_dir / f"page{i}.mp3") for i in range(10)]

        # 使用batch_size=3
        await engine.batch_convert(texts, "test-voice", "+0%", batch_size=3)

        # 验证所有任务都已完成
        assert len(engine.call_order) == 10

    @pytest.mark.asyncio
    async def test_batch_convert_empty_list(self, temp_dir):
        """测试空列表的批量转换"""

        class TestTTSEngine(TTSEngine):
            def __init__(self):
                self.converted = []

            async def convert_async(self, text, output_path, voice, rate):
                self.converted.append(text)

        engine = TestTTSEngine()

        await engine.batch_convert([], "zh-CN-XiaoxiaoNeural", "+0%")

        # 空列表应该不调用任何转换
        assert len(engine.converted) == 0


class TestTTSEngineIntegration:
    """测试 TTS 引擎的集成场景"""

    @pytest.mark.asyncio
    async def test_multiple_pages_conversion(self, temp_dir):
        """测试多页面转换场景"""
        engine = EdgeTTSEngine()

        pages_data = [
            (1, "欢迎来到第一页，这是开场白。", temp_dir / "page1.mp3"),
            (2, "第二页包含详细内容。", temp_dir / "page2.mp3"),
            (3, "第三页是总结部分。", temp_dir / "page3.mp3"),
        ]

        with patch(
            "vidppt.engines.tts.edge_tts_engine.edge_tts.Communicate"
        ) as mock_communicate_class:
            mock_communicate = AsyncMock()
            mock_communicate_class.return_value = mock_communicate

            await engine.batch_convert(
                pages_data, voice="zh-CN-XiaoxiaoNeural", rate="+0%", batch_size=2
            )

            # 验证调用次数
            assert mock_communicate_class.call_count == 3
            assert mock_communicate.save.call_count == 3

    @pytest.mark.asyncio
    async def test_error_handling_in_conversion(self, temp_dir):
        """测试转换中的错误处理"""
        engine = EdgeTTSEngine()

        with patch(
            "vidppt.engines.tts.edge_tts_engine.edge_tts.Communicate"
        ) as mock_communicate_class:
            mock_communicate = AsyncMock()
            mock_communicate.save.side_effect = Exception("TTS服务错误")
            mock_communicate_class.return_value = mock_communicate

            # 应该抛出异常
            with pytest.raises(Exception) as exc_info:
                await engine.convert_async(
                    "测试文本", temp_dir / "test.mp3", "zh-CN-XiaoxiaoNeural", "+0%"
                )

            assert "TTS服务错误" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_different_rate_settings(self, temp_dir):
        """测试不同的语速设置"""
        engine = EdgeTTSEngine()

        rate_settings = ["+0%", "+20%", "+50%", "-20%", "-50%"]

        for rate in rate_settings:
            with patch(
                "vidppt.engines.tts.edge_tts_engine.edge_tts.Communicate"
            ) as mock_communicate_class:
                mock_communicate = AsyncMock()
                mock_communicate_class.return_value = mock_communicate

                await engine.convert_async(
                    "测试文本",
                    temp_dir
                    / f"audio_{rate.replace('%', '').replace('+', 'plus').replace('-', 'minus')}.mp3",
                    "zh-CN-XiaoxiaoNeural",
                    rate,
                )

                # 验证rate参数正确传递
                call_kwargs = mock_communicate_class.call_args[1]
                assert call_kwargs["rate"] == rate


class TestTTSEngineAbstract:
    """测试 TTSEngine 抽象类"""

    def test_cannot_instantiate_abstract_engine(self):
        """测试不能直接实例化抽象引擎"""
        with pytest.raises(TypeError):
            TTSEngine()

    def test_must_implement_convert_async(self):
        """测试必须实现 convert_async 方法"""

        class IncompleteEngine(TTSEngine):
            pass

        with pytest.raises(TypeError):
            IncompleteEngine()

    def test_can_inherit_and_implement(self):
        """测试可以继承并实现接口"""

        class CustomTTSEngine(TTSEngine):
            async def convert_async(self, text, output_path, voice, rate):
                # 简单实现
                pass

        # 应该可以实例化
        engine = CustomTTSEngine()
        assert isinstance(engine, TTSEngine)
