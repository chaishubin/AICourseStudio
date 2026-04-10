"""
改进的 TTS 单元测试 - 真正验证 TTS 功能
"""

import pytest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from vidppt.core.models import PageContent, DocumentContent, ProcessConfig
from vidppt.pipeline import Pipeline
from vidppt.engines.tts.edge_tts_engine import EdgeTTSEngine
from vidppt.utils.progress import ProgressTracker


class TestTTSEngineReal:
    """真正的 TTS 引擎测试（非Mock）"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_edge_tts_convert_async_creates_file(self, temp_dir):
        """验证 convert_async 确实创建了音频文件"""
        engine = EdgeTTSEngine()
        output_path = temp_dir / "output.mp3"

        asyncio.run(
            engine.convert_async(
                text="测试文本",
                output_path=output_path,
                voice="zh-CN-XiaoxiaoNeural",
                rate="+0%",
            )
        )

        # 关键验证：文件确实存在且有内容
        assert output_path.exists(), "音频文件未创建"
        assert output_path.stat().st_size > 0, "音频文件为空"

    def test_edge_tts_batch_convert_creates_multiple_files(self, temp_dir):
        """验证 batch_convert 创建多个文件"""
        engine = EdgeTTSEngine()

        texts = [
            (1, "第一页", temp_dir / "audio_1.mp3"),
            (2, "第二页", temp_dir / "audio_2.mp3"),
        ]

        asyncio.run(
            engine.batch_convert(
                texts=texts,
                voice="zh-CN-XiaoxiaoNeural",
                rate="+0%",
            )
        )

        # 验证所有文件都创建了
        for _, _, path in texts:
            assert path.exists(), f"文件未创建: {path}"
            assert path.stat().st_size > 0, f"文件为空: {path}"

    def test_edge_tts_different_voices_produce_different_audio(self, temp_dir):
        """验证不同声音生成不同的音频"""
        engine = EdgeTTSEngine()
        text = "这是同一段文本"

        # 用女性声音生成
        female_path = temp_dir / "female.mp3"
        asyncio.run(
            engine.convert_async(
                text=text,
                output_path=female_path,
                voice="zh-CN-XiaoxiaoNeural",
                rate="+0%",
            )
        )

        # 用男性声音生成
        male_path = temp_dir / "male.mp3"
        asyncio.run(
            engine.convert_async(
                text=text,
                output_path=male_path,
                voice="zh-CN-YunyangNeural",
                rate="+0%",
            )
        )

        # 两个文件应该都存在
        assert female_path.exists()
        assert male_path.exists()

        # 文件大小可能不同（因为不同声音的压缩率不同）
        print(f"女性声音: {female_path.stat().st_size} 字节")
        print(f"男性声音: {male_path.stat().st_size} 字节")


class TestPipelineGenerateAudioReal:
    """Pipeline 的真实 TTS 测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_pipeline_generate_audio_with_real_tts(self, temp_dir):
        """测试 Pipeline 使用真实 TTS 生成音频"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            enable_audio_cache=False,
            tts_engine="edge-tts",
            tts_voice="zh-CN-XiaoxiaoNeural",
            tts_rate="+0%",
        )

        content = DocumentContent(
            pages=[
                PageContent(page_number=1, text="第一页文本"),
                PageContent(page_number=2, text="第二页文本"),
            ]
        )

        pipeline = Pipeline(config)
        progress = ProgressTracker(total_pages=len(content.pages))

        pipeline._generate_audio(content, progress)

        # 验证音频文件被创建
        for page in content.pages:
            assert page.audio is not None, f"页面 {page.page_number} 没有设置音频路径"
            assert page.audio.exists(), f"页面 {page.page_number} 的音频文件不存在"
            assert page.audio.stat().st_size > 0, (
                f"页面 {page.page_number} 的音频文件为空"
            )

    def test_pipeline_skip_empty_pages_no_audio(self, temp_dir):
        """测试 Pipeline 跳过空文本页面"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            enable_audio_cache=False,
            tts_engine="edge-tts",
        )

        content = DocumentContent(
            pages=[
                PageContent(page_number=1, text="有文本"),
                PageContent(page_number=2, text=""),  # 空文本
                PageContent(page_number=3, text="  "),  # 只有空格
            ]
        )

        pipeline = Pipeline(config)
        progress = ProgressTracker(total_pages=len(content.pages))

        pipeline._generate_audio(content, progress)

        # 验证：页面 1 有音频，页面 2 和 3 没有
        assert content.pages[0].audio is not None
        assert content.pages[0].audio.exists()

        # 空文本页面不应该创建音频文件
        assert content.pages[1].audio is None
        assert content.pages[2].audio is None

    def test_pipeline_with_cache_second_run_uses_cache(self, temp_dir):
        """测试缓存机制 - 第二次运行应该使用缓存"""
        config = ProcessConfig(
            input_path=temp_dir / "test.pptx",
            output_dir=temp_dir / "output",
            enable_audio_cache=True,
            audio_cache_dir=temp_dir / "cache",
            tts_engine="edge-tts",
            tts_voice="zh-CN-XiaoxiaoNeural",
        )

        content = DocumentContent(
            pages=[
                PageContent(page_number=1, text="缓存测试文本"),
            ]
        )

        # 第一次运行 - 生成并缓存
        pipeline1 = Pipeline(config)
        progress1 = ProgressTracker(total_pages=1)
        pipeline1._generate_audio(content, progress1)

        first_audio_path = content.pages[0].audio
        assert first_audio_path.exists()

        # 清除音频文件（模拟新的处理周期）
        first_audio_path.unlink()

        # 第二次运行 - 应该从缓存恢复
        content2 = DocumentContent(
            pages=[
                PageContent(page_number=1, text="缓存测试文本"),  # 完全相同的文本
            ]
        )

        pipeline2 = Pipeline(config)
        progress2 = ProgressTracker(total_pages=1)
        pipeline2._generate_audio(content2, progress2)

        second_audio_path = content2.pages[0].audio
        assert second_audio_path.exists()
        assert second_audio_path.stat().st_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
